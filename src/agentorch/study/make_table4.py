"""Fit-for-purpose matrix — paper Table 4 (task 038, HUMAN-gated).

Reads ONLY ``results/`` and writes ``figures/table4.csv`` with one row per
(pattern, platform, scenario) carrying letter grades on three dimensions
plus an overall grade.

GRADING RULES (explicit, pre-committed; every grade derives from these
rules applied to the executed study data — no judgment calls):

Within each (platform, scenario) condition the seven patterns are
compared. For LATENCY, the 21 pairwise two-sided Mann-Whitney U tests
on per-request latency are Holm-corrected (alpha from configs
``stats.alpha``); pattern X is "significantly slower than" pattern Y
when the corrected test rejects AND the Hodges-Lehmann shift X-Y > 0.

1. latency_grade:
   A — the pattern is not significantly slower than ANY other pattern
       in the condition (it is in the fastest statistical group);
   B — significantly slower than at most 3 of the 6 other patterns;
   C — significantly slower than 4 or more other patterns.

2. cost_grade (mean cost-units per request within the condition):
   A — mean cost <= 1.5x the cheapest pattern's mean cost;
   B — mean cost <= 4x the cheapest;
   C — otherwise.

3. reliability_grade (baseline error rate + fault campaign for the same
   pattern/platform; a cell is "robust" when it is contained AND the
   requests directly hit by the fault still succeed at >= 95%
   (traversing_success_rate >= 0.95) — i.e. the pattern absorbs faults
   rather than merely failing the hit requests). Over the exercised
   cells (n_traversing > 0):
   A — error_rate == 0 AND >= 50% of exercised cells robust;
   B — error_rate <= 0.02 AND all cells contained;
   C — otherwise (errors in baseline, or any propagated cell).

4. overall_grade: the worst (max) of the three letter grades.

Usage: ``python -m agentorch.study.make_table4 [--results results/]
[--out figures/table4.csv]``.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from agentorch.config import load_config
from agentorch.stats.compare import compare
from agentorch.stats.correction import holm

GRADE_ORDER = {"A": 0, "B": 1, "C": 2}


def _latency_grades(base: pd.DataFrame, alpha: float) -> dict[tuple, str]:
    """Holm-corrected pairwise Mann-Whitney slower-than counts -> grades."""
    grades: dict[tuple, str] = {}
    for (platform, scenario), grp in base.groupby(["platform", "scenario"]):
        samples = {p: g["latency_ms"].to_numpy(dtype=float)
                   for p, g in grp.groupby("pattern")}
        patterns = sorted(samples)
        pairs = [(a, b) for i, a in enumerate(patterns)
                 for b in patterns[i + 1:]]
        results = [compare(samples[a], samples[b]) for a, b in pairs]
        corrected = holm([r.p for r in results], alpha=alpha)
        slower_count = {p: 0 for p in patterns}
        for (a, b), res, rej in zip(pairs, results, corrected.rejected):
            if not rej:
                continue
            if res.hodges_lehmann > 0:
                slower_count[a] += 1
            elif res.hodges_lehmann < 0:
                slower_count[b] += 1
        for p in patterns:
            c = slower_count[p]
            grades[(p, platform, scenario)] = ("A" if c == 0
                                               else "B" if c <= 3 else "C")
    return grades


def _cost_grades(base: pd.DataFrame, cost: pd.DataFrame) -> dict[tuple, str]:
    merged = base.merge(cost[["request_id", "pattern", "platform", "cost_units"]],
                        on=["request_id", "pattern", "platform"], how="inner")
    grades: dict[tuple, str] = {}
    for (platform, scenario), grp in merged.groupby(["platform", "scenario"]):
        means = grp.groupby("pattern")["cost_units"].mean()
        cheapest = means.min()
        for p, m in means.items():
            ratio = m / cheapest if cheapest > 0 else float("inf")
            grades[(p, platform, scenario)] = ("A" if ratio <= 1.5
                                               else "B" if ratio <= 4.0 else "C")
    return grades


def _reliability_grades(base: pd.DataFrame,
                        faults: pd.DataFrame) -> dict[tuple, str]:
    grades: dict[tuple, str] = {}
    exercised = faults[faults["n_traversing"] > 0].copy()
    exercised["robust"] = (exercised["contained"]
                           & (exercised["traversing_success_rate"] >= 0.95))
    robust_frac = exercised.groupby(["pattern", "platform"])["robust"].mean()
    contained_all = faults.groupby(["pattern", "platform"])["contained"].all()
    for (pattern, platform, scenario), grp in base.groupby(
            ["pattern", "platform", "scenario"]):
        err = 1.0 - grp["success"].mean()
        rf = float(robust_frac.get((pattern, platform), 0.0))
        all_contained = bool(contained_all.get((pattern, platform), False))
        if err == 0.0 and rf >= 0.50:
            g = "A"
        elif err <= 0.02 and all_contained:
            g = "B"
        else:
            g = "C"
        grades[(pattern, platform, scenario)] = g
    return grades


def build_table4(results_dir: str | Path, cfg=None) -> pd.DataFrame:
    cfg = cfg or load_config()
    results = Path(results_dir)
    lat = pd.read_csv(results / "latency.csv")
    cost = pd.read_csv(results / "cost.csv")
    faults = pd.read_csv(results / "faults.csv")
    base = lat[lat["mode"] == "baseline"]
    alpha = float(cfg.stats.alpha)

    lat_g = _latency_grades(base, alpha)
    cost_g = _cost_grades(base, cost)
    rel_g = _reliability_grades(base, faults)

    rows = []
    for key in sorted(lat_g):
        pattern, platform, scenario = key
        lg, cg, rg = lat_g[key], cost_g[key], rel_g[key]
        overall = max((lg, cg, rg), key=lambda g: GRADE_ORDER[g])
        rows.append({"pattern": pattern, "platform": platform,
                     "scenario": scenario, "latency_grade": lg,
                     "cost_grade": cg, "reliability_grade": rg,
                     "overall_grade": overall})
    return pd.DataFrame(rows)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write figures/table4.csv")
    parser.add_argument("--results", default="results/")
    parser.add_argument("--out", default="figures/table4.csv")
    args = parser.parse_args(argv)
    table = build_table4(args.results)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    table.to_csv(out, index=False)
    print(f"wrote {out} ({len(table)} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
