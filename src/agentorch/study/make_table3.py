"""Synoptic comparison table — paper Table 3 (task 037, HUMAN-gated).

Reads ONLY ``results/`` (latency.csv, cost.csv, manifest.json) and writes
``figures/table3.csv`` with one row per (pattern, platform, scenario)
baseline condition:

    n, p50/p95/p99 latency (ms) each with a 95% BCa bootstrap CI,
    error_rate, throughput_rps, mean cost_units per request.

Every number is computed from the executed study results; nothing is
hard-coded. Usage:
``python -m agentorch.study.make_table3 [--results results/] [--out figures/table3.csv]``
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from agentorch.config import load_config
from agentorch.stats.bootstrap import bca_ci
from agentorch.stats.percentiles import percentiles

PCTLS = (50, 95, 99)


def build_table3(results_dir: str | Path, cfg=None) -> pd.DataFrame:
    cfg = cfg or load_config()
    results = Path(results_dir)
    lat = pd.read_csv(results / "latency.csv")
    cost = pd.read_csv(results / "cost.csv")
    base = lat[lat["mode"] == "baseline"]

    alpha = float(cfg.stats.alpha)
    n_resamples = int(cfg.stats.n_resamples)

    rows: list[dict] = []
    for (pattern, platform, scenario), grp in base.groupby(
            ["pattern", "platform", "scenario"], sort=True):
        x = grp["latency_ms"].to_numpy(dtype=float)
        n = len(x)
        row: dict = {"pattern": pattern, "platform": platform,
                     "scenario": scenario, "n": n}
        pt = percentiles(x, ps=PCTLS)
        for p in PCTLS:
            rng = cfg.get_rng(f"table3:{pattern}:{platform}:{scenario}:p{p}")
            lo, hi = bca_ci(x, lambda a, p=p: float(np.percentile(a, p)),
                            alpha=alpha, n_resamples=n_resamples, rng=rng)
            row[f"p{p}_ms"] = pt[float(p)]
            row[f"p{p}_ci_lo"] = lo
            row[f"p{p}_ci_hi"] = hi
        row["error_rate"] = 1.0 - grp["success"].mean()
        window = grp["complete_ts"].max() - grp["submit_ts"].min()
        row["throughput_rps"] = n / window if window > 0 else float("nan")
        crows = cost[(cost["pattern"] == pattern)
                     & (cost["platform"] == platform)
                     & (cost["request_id"].isin(grp["request_id"]))]
        row["cost_per_request"] = (crows["cost_units"].mean()
                                   if not crows.empty else float("nan"))
        rows.append(row)
    return pd.DataFrame(rows)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write figures/table3.csv")
    parser.add_argument("--results", default="results/")
    parser.add_argument("--out", default="figures/table3.csv")
    args = parser.parse_args(argv)
    table = build_table3(args.results)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    table.to_csv(out, index=False)
    print(f"wrote {out} ({len(table)} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
