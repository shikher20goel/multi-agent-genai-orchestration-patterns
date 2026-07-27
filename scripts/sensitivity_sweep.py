"""Sensitivity sweep over study parameters n and rho (reviewer response, R2-4).

Reviewer 2 of the IEEE Access submission asked why n = 500 requests per
condition and rho = 0.70 offered utilization are adequate choices, and how
sensitive the study's conclusions are to them. This script answers by
measurement: it re-runs the FULL production study path
(``agentorch.study.run_study.run_study`` -> ``build_fit_matrix``) under six
single-parameter variants around the baseline,

    n   in {250, 1000, 2000}   at rho = 0.70   (baseline n = 500)
    rho in {0.50, 0.60, 0.80}  at n   = 500    (baseline rho = 0.70)

with every other parameter, and the master seed, identical to
``configs/default.yaml``. Variant overlay files live in ``configs/sweep/``.

For each variant it reports, against the baseline run:

1. FIT-GRADE STABILITY - per-cell agreement of the computed 21-cell
   fit-for-purpose matrix (the pre-registered rule of docs/FIT_RULE.md),
   with every moving cell named (from -> to).
2. ORDERING STABILITY - Kendall tau between the variant's and the
   baseline's median-latency ordering of the seven patterns, per
   (platform, scenario) family (6 families), plus the mean.
3. HEADLINE CONTRASTS - whether the paper's emergent directional claims
   hold: (a) P2 p99(S2) > p99(S1) on both platforms (additive stages);
   (b) P6 has the highest p99 in every condition (human-step-bound);
   (c) P3's S3/S1 p99 inflation is smaller than P1's and P2's on both
   platforms (burst absorption); (d) P1 has the highest mean per-request
   cost in every (platform, scenario) (fan-out cost).

Nothing here tunes the rig: the sweep only re-executes the released
pipeline under different (n, rho) and reports what comes out. Outputs:

- ``figures/sensitivity_sweep.csv``    - per-variant per-cell grades
- ``figures/sensitivity_summary.json`` - all comparisons, machine-readable
- stdout                               - human-readable summary

Usage::

    python -m scripts.sensitivity_sweep [--out-root results_sweep/]
        [--figures figures/] [--quick] [--only VARIANT]

``--quick`` shrinks n per variant (smoke/CI only; not the reported sweep).
"""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

import pandas as pd
from scipy.stats import kendalltau

from agentorch.config import Config, load_config
from agentorch.study.make_fit_matrix import build_fit_matrix
from agentorch.study.run_study import run_study

REPO_ROOT = Path(__file__).resolve().parents[1]
SWEEP_CONFIG_DIR = REPO_ROOT / "configs" / "sweep"

PATTERNS = [f"P{i}" for i in range(1, 8)]
PLATFORMS = ["agentforce", "bedrock"]
SCENARIOS = ["S1", "S2", "S3"]

# Variant names; each has a committed single-parameter overlay file in
# configs/sweep/<name>.yaml applied on top of configs/default.yaml. The
# baseline is configs/default.yaml unmodified (n=500, rho=0.70).
VARIANTS: tuple[str, ...] = ("n250", "n1000", "n2000",
                             "rho050", "rho060", "rho080")


def _overlay(name: str) -> dict:
    import yaml
    with open(SWEEP_CONFIG_DIR / f"{name}.yaml") as f:
        return yaml.safe_load(f)


def _deep_merge(base: dict, overlay: dict) -> dict:
    for key, value in overlay.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value
    return base


def variant_override(name: str) -> dict:
    """Flat {dotted.path: value} view of a variant's overlay (reporting)."""
    def flatten(d: dict, prefix: str = "") -> dict:
        out: dict = {}
        for k, v in d.items():
            key = f"{prefix}{k}"
            if isinstance(v, dict):
                out.update(flatten(v, key + "."))
            else:
                out[key] = v
        return out
    return flatten(_overlay(name))


def variant_config(name: str, quick: bool = False) -> Config:
    """Baseline config with the variant's committed overlay applied (or
    nothing for ``baseline``). Master seed and all other parameters
    untouched."""
    data = copy.deepcopy(load_config().to_dict())
    if name != "baseline":
        _deep_merge(data, _overlay(name))
    if quick:  # smoke/CI only
        data["study"]["n_items"] = min(60, int(data["study"]["n_items"]))
        data["faults"]["campaign"]["n_requests"] = 8
    return Config(data)


def _median_latencies(results_dir: Path) -> pd.DataFrame:
    lat = pd.read_csv(results_dir / "latency.csv")
    base = lat[lat["mode"] == "baseline"]
    return (base.groupby(["platform", "scenario", "pattern"])["latency_ms"]
            .median().rename("p50_ms").reset_index())


def _p99(med_src: pd.DataFrame, platform: str, scenario: str,
         pattern: str) -> float:
    row = med_src[(med_src["platform"] == platform)
                  & (med_src["scenario"] == scenario)
                  & (med_src["pattern"] == pattern)]
    return float(row["p99_ms"].iloc[0])


def _p99_frame(results_dir: Path) -> pd.DataFrame:
    lat = pd.read_csv(results_dir / "latency.csv")
    base = lat[lat["mode"] == "baseline"]
    return (base.groupby(["platform", "scenario", "pattern"])["latency_ms"]
            .quantile(0.99).rename("p99_ms").reset_index())


def _mean_costs(results_dir: Path) -> pd.DataFrame:
    cost = pd.read_csv(results_dir / "cost.csv")
    return (cost.groupby(["platform", "scenario", "pattern"])["cost_units"]
            .mean().rename("mean_cost").reset_index())


def headline_contrasts(results_dir: Path) -> dict[str, bool]:
    """The paper's emergent directional claims, evaluated on one run."""
    p99 = _p99_frame(results_dir)
    costs = _mean_costs(results_dir)
    checks: dict[str, bool] = {}
    # (a) Pipeline additive: P2 p99(S2) > p99(S1), both platforms.
    checks["pipeline_additive"] = all(
        _p99(p99, pl, "S2", "P2") > _p99(p99, pl, "S1", "P2")
        for pl in PLATFORMS)
    # (b) HITL human-step-bound: P6 p99 highest in every condition.
    checks["hitl_tail_dominant"] = all(
        _p99(p99, pl, sc, "P6") == max(_p99(p99, pl, sc, p)
                                       for p in PATTERNS)
        for pl in PLATFORMS for sc in SCENARIOS)
    # (c) Burst absorption: P3 S3/S1 p99 inflation < P1's and < P2's.
    def inflation(pl: str, p: str) -> float:
        return _p99(p99, pl, "S3", p) / _p99(p99, pl, "S1", p)
    checks["choreography_burst_absorption"] = all(
        inflation(pl, "P3") < inflation(pl, "P1")
        and inflation(pl, "P3") < inflation(pl, "P2") for pl in PLATFORMS)
    # (d) Supervisor fan-out cost: P1 mean cost highest per condition.
    def mean_cost(pl: str, sc: str, p: str) -> float:
        row = costs[(costs["platform"] == pl) & (costs["scenario"] == sc)
                    & (costs["pattern"] == p)]
        return float(row["mean_cost"].iloc[0])
    checks["supervisor_costliest"] = all(
        mean_cost(pl, sc, "P1") == max(mean_cost(pl, sc, p)
                                       for p in PATTERNS)
        for pl in PLATFORMS for sc in SCENARIOS)
    return checks


def compare_orderings(base_med: pd.DataFrame,
                      var_med: pd.DataFrame) -> dict[str, float]:
    """Kendall tau between baseline and variant median-latency orderings
    of the 7 patterns, per (platform, scenario) family."""
    taus: dict[str, float] = {}
    for pl in PLATFORMS:
        for sc in SCENARIOS:
            def vec(df: pd.DataFrame) -> list[float]:
                sub = df[(df["platform"] == pl) & (df["scenario"] == sc)]
                by = sub.set_index("pattern")["p50_ms"]
                return [float(by[p]) for p in PATTERNS]
            tau, _ = kendalltau(vec(base_med), vec(var_med))
            taus[f"{pl}:{sc}"] = round(float(tau), 4)
    fam = list(taus.values())
    taus["mean"] = round(sum(fam) / len(fam), 4)
    return taus


def compare_grades(base_fit: pd.DataFrame,
                   var_fit: pd.DataFrame) -> dict:
    """Per-cell agreement of computed fit grades, variant vs baseline."""
    b = base_fit.set_index(["pattern", "scenario"])["fit_grade"]
    v = var_fit.set_index(["pattern", "scenario"])["fit_grade"]
    moving = []
    agree = 0
    for key in b.index:
        if str(b[key]) == str(v[key]):
            agree += 1
        else:
            moving.append({"pattern": key[0], "scenario": key[1],
                           "baseline": str(b[key]), "variant": str(v[key])})
    return {"cells_agree": agree, "cells_total": int(len(b.index)),
            "moving_cells": moving}


def run_sweep(out_root: Path, figures_dir: Path, only: str | None = None,
              quick: bool = False, force: bool = False) -> dict:
    from agentorch.study.run_study import _config_hash
    out_root.mkdir(parents=True, exist_ok=True)
    figures_dir.mkdir(parents=True, exist_ok=True)
    names = ["baseline"] + list(VARIANTS)
    if only:
        names = ["baseline", only] if only != "baseline" else ["baseline"]

    fits: dict[str, pd.DataFrame] = {}
    meds: dict[str, pd.DataFrame] = {}
    heads: dict[str, dict[str, bool]] = {}
    manifests: dict[str, dict] = {}
    for name in names:
        cfg = variant_config(name, quick=quick)
        rdir = out_root / name
        manifest_path = rdir / "manifest.json"
        # Idempotent reuse: the study is deterministic (fixed master seed),
        # so an existing run with an IDENTICAL config hash is byte-equivalent
        # to a fresh one and may be reused. Any config change forces a rerun.
        if manifest_path.exists() and not force:
            with open(manifest_path) as f:
                existing = json.load(f)
            if existing.get("config_hash") == _config_hash(cfg):
                manifests[name] = existing
            else:
                manifests[name] = run_study(cfg, rdir)
        else:
            manifests[name] = run_study(cfg, rdir)
        # The computed fit matrix is likewise deterministic given the
        # results; cache it beside them (same reuse rule as above).
        fit_path = rdir / "fit_matrix.csv"
        if fit_path.exists() and not force:
            fits[name] = pd.read_csv(fit_path)
        else:
            fits[name] = build_fit_matrix(rdir, cfg)
            fits[name].to_csv(fit_path, index=False)
        meds[name] = _median_latencies(rdir)
        heads[name] = headline_contrasts(rdir)

    summary: dict = {
        "baseline": {"n_items": 500, "utilization_target": 0.70,
                     "headline_contrasts": heads["baseline"]},
        "variants": {},
        "quick": quick,
    }
    rows = []
    for name in names:
        fit = fits[name]
        for _, r in fit.iterrows():
            rows.append({"variant": name, "pattern": r["pattern"],
                         "scenario": r["scenario"],
                         "fit_grade": r["fit_grade"]})
        if name == "baseline":
            continue
        summary["variants"][name] = {
            "override": variant_override(name),
            "fit_vs_baseline": compare_grades(fits["baseline"], fit),
            "kendall_tau_median_latency": compare_orderings(
                meds["baseline"], meds[name]),
            "headline_contrasts": heads[name],
            # Wall-clock time is intentionally NOT persisted here: it is
            # machine-dependent and would break the bit-identical
            # reproducibility the study guarantees (reviewer R2-4's
            # determinism check). Per-run timing is still recorded in
            # results_sweep/<variant>/manifest.json for diagnostics.
        }

    pd.DataFrame(rows).to_csv(figures_dir / "sensitivity_sweep.csv",
                              index=False)
    with open(figures_dir / "sensitivity_summary.json", "w") as f:
        json.dump(summary, f, indent=2)
    return summary


def _print_summary(summary: dict) -> None:
    print("== Sensitivity sweep (variant vs baseline computed fit matrix) ==")
    for name, s in summary["variants"].items():
        fit = s["fit_vs_baseline"]
        taus = s["kendall_tau_median_latency"]
        hold = all(s["headline_contrasts"].values())
        print(f"{name:8s} override={s['override']} "
              f"grades {fit['cells_agree']}/{fit['cells_total']} agree; "
              f"mean tau {taus['mean']}; headline contrasts "
              f"{'ALL HOLD' if hold else 'CHECK: ' + str(s['headline_contrasts'])}")
        for mc in fit["moving_cells"]:
            print(f"         moving cell {mc['pattern']}/{mc['scenario']}: "
                  f"{mc['baseline']} -> {mc['variant']}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Sensitivity sweep over n and rho (reviewer R2-4)")
    parser.add_argument("--out-root", default="results_sweep/")
    parser.add_argument("--figures", default="figures/")
    parser.add_argument("--only", default=None,
                        choices=[None, *VARIANTS], help="single variant")
    parser.add_argument("--quick", action="store_true",
                        help="reduced n (smoke/CI only)")
    parser.add_argument("--force", action="store_true",
                        help="rerun variants even if cached results match")
    args = parser.parse_args(argv)
    summary = run_sweep(Path(args.out_root), Path(args.figures),
                        only=args.only, quick=args.quick, force=args.force)
    _print_summary(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
