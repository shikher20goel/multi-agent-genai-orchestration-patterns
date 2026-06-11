"""Supplementary per-platform quality table (task 038; rewritten under
Phase 2 task 106, HUMAN-gated; renamed to table4_supplementary under
Phase 3 task 204).

THIS TABLE IS NOT THE PAPER'S FIT-FOR-PURPOSE MATRIX (the paper's
Table 4). The paper's Table 4 is the platform-independent
Weak/Moderate/Strong matrix computed by ``make_fit_matrix.py`` ->
``figures/fit_matrix.csv`` under the pre-registered rule of
``docs/FIT_RULE.md``. This module instead produces a RICHER
SUPPLEMENTARY per-platform quality view — A/B/C equivalence-group
grades on four dimensions (latency / reliability / cost / oversight)
per (pattern, platform, scenario).

Reads ONLY ``results/`` and writes ``figures/table4_supplementary.csv``
with one row
per (pattern, platform, scenario) carrying letter grades on three
measured dimensions plus a metadata-derived oversight grade and an
overall grade. EVERY grade is COMPUTED from the calibrated study data
through the pre-committed Mann-Whitney/Holm comparison machinery
(``stats/compare.py`` + ``stats/correction.py``) — no hand rules.

GRADE FUNCTION (task 106; also documented in docs/GRADES.md):

Within each (platform, scenario) condition the seven patterns are
compared pairwise (21 pairs = the pre-committed family) with two-sided
Mann-Whitney U tests, Holm-corrected at ``stats.alpha``. Pattern X is
"significantly dominated by" pattern Y on an endpoint when the
corrected test rejects AND the Hodges-Lehmann shift X-Y > 0 (X worse:
higher latency / higher error indicator / higher cost). The Holm
machinery induces statistical equivalence groups:

  A — X is in the BEST Holm-significant equivalence group: X is not
      significantly dominated by ANY other pattern (statistically
      indistinguishable from the best performer);
  C — X is significantly dominated by MOST others (>= 4 of the 6) —
      the worst group;
  B — otherwise.

Endpoints per column (per-request samples from results/):
  latency_grade     — TAIL latency, the paper's primary endpoint
                      (p99): each pattern's per-request baseline
                      latencies restricted to the condition's slowest
                      decile (the p90-p100 order statistics containing
                      p99). Pairwise MWU on these conditional tail
                      samples tests stochastic tail dominance, so the
                      grade follows the p99 ordering rather than the
                      median (essential for P6, whose median is fast
                      but whose tail is human-decision-dominated);
  reliability_grade — per-request failure indicator (1 - success)
                      under the FAULT campaign for the same
                      pattern/platform (mode == "fault"; campaign runs
                      on S1, so the column is scenario-invariant —
                      fault response is a structural property);
  cost_grade        — per-request cost_units (USD per request under
                      configs/costs.yaml dated assumptions) within the
                      same (platform, scenario).

  oversight_grade   — derived from PATTERN CAPABILITY METADATA
                      (``Pattern.meta()``), independent of latency:
      A — the pattern's structural mechanism contains a human decision
          point (the words "human" in the catalog ``solution``/
          ``intent``: P6's pause -> human queue -> resume);
      B — the catalog ``governance_hooks`` include an inline policy
          gate/check ("policy" hook: P1, P2, P4, P5, P7);
      C — audit-trail-only hooks (P3).

  overall_grade     — worst (max) of latency, reliability, and cost;
      the oversight column is reported separately because the paper's
      fit-for-purpose matrix treats oversight as a capability axis,
      not a performance axis.

Ties in MWU on the binary failure indicator are handled by the normal
approximation with tie correction (scipy default), which is the
appropriate two-sample proportion-shift test in this rank framework.

Usage: ``python -m agentorch.study.make_table4 [--results results/]
[--out figures/table4_supplementary.csv]``.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from agentorch.config import load_config
from agentorch.stats.compare import compare
from agentorch.stats.correction import holm

GRADE_ORDER = {"A": 0, "B": 1, "C": 2}
PATTERNS = [f"P{i}" for i in range(1, 8)]
TAIL_FRACTION = 0.10  # slowest decile = the p90-p100 region holding p99
# Significantly-dominated-by count thresholds (out of 6 possible
# dominators): A = 0 (best equivalence group), C >= worst-group floor.
WORST_GROUP_MIN_DOMINATORS = 4


def _dominated_grades(samples: dict[str, np.ndarray],
                      alpha: float) -> dict[str, str]:
    """Holm-corrected pairwise MWU -> equivalence-group letter grades.

    ``samples`` maps pattern -> per-request endpoint values where HIGHER
    is WORSE. Returns pattern -> grade by the documented A/B/C rule.
    """
    patterns = sorted(samples)
    pairs = [(a, b) for i, a in enumerate(patterns) for b in patterns[i + 1:]]
    results = []
    testable = []
    for a, b in pairs:
        xa, xb = samples[a], samples[b]
        # Degenerate identical-constant samples (e.g. zero failures on
        # both sides) are equivalence by definition: no domination.
        if np.all(xa == xa[0]) and np.all(xb == xb[0]) and xa[0] == xb[0]:
            continue
        testable.append((a, b))
        results.append(compare(xa, xb))
    dominated = {p: 0 for p in patterns}
    if results:
        corrected = holm([r.p for r in results], alpha=alpha)
        for (a, b), res, rej in zip(testable, results, corrected.rejected):
            if not rej:
                continue
            if res.hodges_lehmann > 0:
                dominated[a] += 1          # a is worse than b
            elif res.hodges_lehmann < 0:
                dominated[b] += 1
            else:
                # HL == 0 with a rejected test (heavy ties): direction
                # from the rank-biserial sign.
                if res.rank_biserial > 0:
                    dominated[a] += 1
                elif res.rank_biserial < 0:
                    dominated[b] += 1
    grades = {}
    for p in patterns:
        d = dominated[p]
        grades[p] = ("A" if d == 0
                     else "C" if d >= WORST_GROUP_MIN_DOMINATORS else "B")
    return grades


def _tail(x: np.ndarray, fraction: float = TAIL_FRACTION) -> np.ndarray:
    """Slowest-``fraction`` order statistics of a latency sample."""
    k = max(2, int(np.ceil(len(x) * fraction)))
    return np.sort(x)[-k:]


def _latency_grades(base: pd.DataFrame, alpha: float) -> dict[tuple, str]:
    out: dict[tuple, str] = {}
    for (platform, scenario), grp in base.groupby(["platform", "scenario"]):
        samples = {p: _tail(g["latency_ms"].to_numpy(dtype=float))
                   for p, g in grp.groupby("pattern")}
        for p, g in _dominated_grades(samples, alpha).items():
            out[(p, platform, scenario)] = g
    return out


def _cost_grades(base: pd.DataFrame, cost: pd.DataFrame,
                 alpha: float) -> dict[tuple, str]:
    if "scenario" in cost.columns:
        merged = cost
    else:  # legacy cost files without the scenario column
        merged = base.merge(
            cost[["request_id", "pattern", "platform", "cost_units"]],
            on=["request_id", "pattern", "platform"], how="inner")
    out: dict[tuple, str] = {}
    for (platform, scenario), grp in merged.groupby(["platform", "scenario"]):
        samples = {p: g["cost_units"].to_numpy(dtype=float)
                   for p, g in grp.groupby("pattern")}
        for p, g in _dominated_grades(samples, alpha).items():
            out[(p, platform, scenario)] = g
    return out


def _reliability_grades(fault_lat: pd.DataFrame,
                        alpha: float) -> dict[tuple, str]:
    """Per-request failure indicator under the fault campaign; the
    campaign runs on one scenario, so the grade is per (pattern,
    platform) and applied to every scenario row."""
    out: dict[tuple, str] = {}
    for platform, grp in fault_lat.groupby("platform"):
        samples = {p: (1.0 - g["success"].astype(float)).to_numpy()
                   for p, g in grp.groupby("pattern")}
        for p, g in _dominated_grades(samples, alpha).items():
            out[(p, platform)] = g
    return out


def _oversight_grades() -> dict[str, str]:
    """Capability-metadata-derived oversight grades (latency-independent)."""
    from agentorch.patterns.registry import REGISTRY
    out: dict[str, str] = {}
    for pid, cls in REGISTRY.items():
        meta = cls.meta()
        text = (str(meta.get("solution", "")) + " "
                + str(meta.get("intent", ""))).lower()
        hooks = " ".join(str(h) for h in meta.get("governance_hooks", [])).lower()
        if "human" in text:
            out[pid.value] = "A"
        elif "policy" in hooks:
            out[pid.value] = "B"
        else:
            out[pid.value] = "C"
    return out


def build_table4(results_dir: str | Path, cfg=None) -> pd.DataFrame:
    cfg = cfg or load_config()
    results = Path(results_dir)
    lat = pd.read_csv(results / "latency.csv")
    cost = pd.read_csv(results / "cost.csv")
    base = lat[lat["mode"] == "baseline"]
    fault_lat = lat[lat["mode"] == "fault"]
    alpha = float(cfg.stats.alpha)

    lat_g = _latency_grades(base, alpha)
    cost_g = _cost_grades(base, cost, alpha)
    rel_g = _reliability_grades(fault_lat, alpha)
    ovs_g = _oversight_grades()

    rows = []
    for key in sorted(lat_g):
        pattern, platform, scenario = key
        lg = lat_g[key]
        cg = cost_g[key]
        rg = rel_g[(pattern, platform)]
        og = ovs_g[pattern]
        overall = max((lg, rg, cg), key=lambda g: GRADE_ORDER[g])
        rows.append({"pattern": pattern, "platform": platform,
                     "scenario": scenario, "latency_grade": lg,
                     "reliability_grade": rg, "cost_grade": cg,
                     "oversight_grade": og, "overall_grade": overall})
    return pd.DataFrame(rows)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write figures/table4_supplementary.csv")
    parser.add_argument("--results", default="results/")
    parser.add_argument("--out", default="figures/table4_supplementary.csv")
    args = parser.parse_args(argv)
    table = build_table4(args.results)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    table.to_csv(out, index=False)
    print(f"wrote {out} ({len(table)} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
