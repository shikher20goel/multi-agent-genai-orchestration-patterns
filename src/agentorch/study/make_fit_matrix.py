"""Platform-independent fit-for-purpose matrix -- paper Table 4
(Phase 3 task 201).

Implements EXACTLY the pre-registered rule of ``docs/FIT_RULE.md``
(written before this module first ran). Reads ONLY ``results/``
(latency.csv, cost.csv) plus pattern capability metadata
(``Pattern.capabilities()``) and writes ``figures/fit_matrix.csv``:
ONE grade per (pattern, scenario) cell in {Weak, Moderate, Strong},
21 cells.

Rule summary (authoritative text in docs/FIT_RULE.md):

- Per-platform STANDING on each stressed-property endpoint via the
  pre-committed Holm-corrected pairwise Mann-Whitney machinery
  (reusing ``make_table4._dominated_grades``): TOP = best equivalence
  group (0 dominators), BOTTOM = dominated by >= 4 of 6, MID otherwise.
- Stressed property per scenario:
    S1: per-request S1 latency (latency-derived throughput) AND
        per-request S1 cost; pessimistic composite.
    S2: per-request S2 latency / own S1 median latency AND
        per-request S2 cost / own S1 mean cost (growth over stages);
        pessimistic composite; capability gate adaptive_decomposition.
    S3: slowest-decile S3 latencies / own S1 p99 (tail-inflation
        samples); capability gate selective_human_routing OR
        event_absorption.
- Pooling: same standing on BOTH platforms -> that standing; mixed ->
  MID. Base grade: TOP -> Strong, MID -> Moderate, BOTTOM -> Weak.
- Capability gate (S2/S3): capability PRESENT upgrades one level
  (max Strong); absence never downgrades.

The computed grade is NEVER hand-edited; disagreements with the
paper's published Table 4 are recorded in docs/FIT_DISCREPANCIES.md.

Usage: ``python -m agentorch.study.make_fit_matrix
[--results results/] [--out figures/fit_matrix.csv]``.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from agentorch.config import load_config
from agentorch.study.make_table4 import _dominated_grades, _tail

PATTERNS = [f"P{i}" for i in range(1, 8)]
PLATFORMS = ["agentforce", "bedrock"]
SCENARIOS = ["S1", "S2", "S3"]

# Standing order: lower = better. The pessimistic composite takes max.
STANDING_ORDER = {"TOP": 0, "MID": 1, "BOTTOM": 2}
GRADE_OF_STANDING = {"TOP": "Strong", "MID": "Moderate", "BOTTOM": "Weak"}
UPGRADE = {"Weak": "Moderate", "Moderate": "Strong", "Strong": "Strong"}

# Required-capability gate per scenario (docs/FIT_RULE.md).
CAPABILITY_GATE = {
    "S1": (),
    "S2": ("adaptive_decomposition",),
    "S3": ("selective_human_routing", "event_absorption"),
}

_GRADE_TO_STANDING = {"A": "TOP", "B": "MID", "C": "BOTTOM"}


def _standings(samples: dict[str, np.ndarray], alpha: float) -> dict[str, str]:
    """Per-pattern TOP/MID/BOTTOM standing on one endpoint family.

    Reuses the pre-committed dominated-count machinery of make_table4
    (A = 0 dominators, C = >= 4 of 6, B otherwise) and maps letters to
    the standing vocabulary of docs/FIT_RULE.md.
    """
    return {p: _GRADE_TO_STANDING[g]
            for p, g in _dominated_grades(samples, alpha).items()}


def _pessimistic(a: str, b: str) -> str:
    """Worse of two standings (TOP < MID < BOTTOM)."""
    return a if STANDING_ORDER[a] >= STANDING_ORDER[b] else b


def _pool(per_platform: dict[str, str]) -> str:
    """Platform pooling: same extreme on both platforms keeps it;
    anything mixed is MID (docs/FIT_RULE.md)."""
    vals = [per_platform[pl] for pl in PLATFORMS]
    return vals[0] if vals[0] == vals[1] else "MID"


def _capabilities() -> dict[str, dict[str, bool]]:
    from agentorch.patterns.registry import REGISTRY
    return {pid.value: cls.capabilities() for pid, cls in REGISTRY.items()}


def _latency_samples(base: pd.DataFrame, platform: str,
                     scenario: str) -> dict[str, np.ndarray]:
    grp = base[(base["platform"] == platform)
               & (base["scenario"] == scenario)]
    return {p: g["latency_ms"].to_numpy(dtype=float)
            for p, g in grp.groupby("pattern")}


def _cost_samples(cost: pd.DataFrame, platform: str,
                  scenario: str) -> dict[str, np.ndarray]:
    grp = cost[(cost["platform"] == platform)
               & (cost["scenario"] == scenario)]
    return {p: g["cost_units"].to_numpy(dtype=float)
            for p, g in grp.groupby("pattern")}


def build_fit_matrix(results_dir: str | Path, cfg=None) -> pd.DataFrame:
    """Compute the 21-cell platform-independent fit matrix."""
    cfg = cfg or load_config()
    alpha = float(cfg.stats.alpha)
    results = Path(results_dir)
    lat = pd.read_csv(results / "latency.csv")
    cost = pd.read_csv(results / "cost.csv")
    base = lat[lat["mode"] == "baseline"]
    caps = _capabilities()

    # Per-platform endpoint standings, per docs/FIT_RULE.md.
    standing: dict[tuple[str, str, str], dict[str, str]] = {}
    for platform in PLATFORMS:
        lat_s1 = _latency_samples(base, platform, "S1")
        cost_s1 = _cost_samples(cost, platform, "S1")
        s1_median_lat = {p: float(np.median(x)) for p, x in lat_s1.items()}
        s1_mean_cost = {p: float(np.mean(x)) for p, x in cost_s1.items()}
        s1_p99_lat = {p: float(np.percentile(x, 99))
                      for p, x in lat_s1.items()}

        # S1: per-request latency (throughput proxy) + per-request cost.
        standing[("S1", "latency", platform)] = _standings(lat_s1, alpha)
        standing[("S1", "cost", platform)] = _standings(cost_s1, alpha)

        # S2: growth over stages relative to own S1 level.
        lat_s2 = _latency_samples(base, platform, "S2")
        cost_s2 = _cost_samples(cost, platform, "S2")
        lat_growth = {p: x / s1_median_lat[p] for p, x in lat_s2.items()}
        cost_growth = {p: x / s1_mean_cost[p] for p, x in cost_s2.items()}
        standing[("S2", "latency", platform)] = _standings(lat_growth, alpha)
        standing[("S2", "cost", platform)] = _standings(cost_growth, alpha)

        # S3: slowest-decile tail inflation vs own S1 p99.
        lat_s3 = _latency_samples(base, platform, "S3")
        tail_inflation = {p: _tail(x) / s1_p99_lat[p]
                          for p, x in lat_s3.items()}
        standing[("S3", "tail_inflation", platform)] = _standings(
            tail_inflation, alpha)

    rows = []
    for pattern in PATTERNS:
        for scenario in SCENARIOS:
            row: dict = {"pattern": pattern, "scenario": scenario}
            per_platform: dict[str, str] = {}
            if scenario in ("S1", "S2"):
                for platform in PLATFORMS:
                    sl = standing[(scenario, "latency", platform)][pattern]
                    sc = standing[(scenario, "cost", platform)][pattern]
                    per_platform[platform] = _pessimistic(sl, sc)
                    row[f"{platform}_latency_standing"] = sl
                    row[f"{platform}_cost_standing"] = sc
            else:  # S3
                for platform in PLATFORMS:
                    st = standing[("S3", "tail_inflation",
                                   platform)][pattern]
                    per_platform[platform] = st
                    row[f"{platform}_latency_standing"] = st
                    row[f"{platform}_cost_standing"] = ""
            for platform in PLATFORMS:
                row[f"{platform}_standing"] = per_platform[platform]
            pooled = _pool(per_platform)
            grade = GRADE_OF_STANDING[pooled]
            gate = CAPABILITY_GATE[scenario]
            has_cap = any(caps[pattern][c] for c in gate)
            if has_cap:
                grade = UPGRADE[grade]
            row["pooled_standing"] = pooled
            row["capability_applied"] = bool(has_cap)
            row["fit_grade"] = grade
            rows.append(row)
    cols = ["pattern", "scenario", "fit_grade", "pooled_standing",
            "capability_applied",
            "agentforce_standing", "bedrock_standing",
            "agentforce_latency_standing", "agentforce_cost_standing",
            "bedrock_latency_standing", "bedrock_cost_standing"]
    return pd.DataFrame(rows)[cols]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Write figures/fit_matrix.csv (paper Table 4)")
    parser.add_argument("--results", default="results/")
    parser.add_argument("--out", default="figures/fit_matrix.csv")
    args = parser.parse_args(argv)
    table = build_fit_matrix(args.results)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    table.to_csv(out, index=False)
    print(f"wrote {out} ({len(table)} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
