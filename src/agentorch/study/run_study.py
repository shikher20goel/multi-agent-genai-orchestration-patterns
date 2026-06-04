"""Full measurement-study orchestrator (task 036).

Runs the 7 patterns x 2 platforms x 3 scenarios baseline grid, then the
fault-injection campaign (Algorithm 2) per (pattern, platform), with
per-request cost capture throughout. Writes:

- ``results/latency.csv``  — one row per request (baseline + fault mode)
- ``results/cost.csv``     — one CostRecord per baseline request
- ``results/faults.csv``   — one row per campaign cell, with pattern/platform
- ``results/manifest.json``— seed, config hash, n, git rev, timestamp

Usage: ``python -m agentorch.study.run_study [--smoke] [--out results/]
[--config configs/default.yaml]``.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import time
from pathlib import Path

import pandas as pd

from agentorch.config import Config, load_config
from agentorch.rig.faultcampaign import run_campaign
from agentorch.rig.loadgen import run_condition
from agentorch.telemetry import TelemetrySink
from agentorch.types import PatternId, Platform, ScenarioId

FAULT_SCENARIO = ScenarioId.S1  # campaign workload (single-step, isolates the fault)


def _git_rev() -> str:
    try:
        out = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True,
                             text=True, check=True, timeout=10)
        return out.stdout.strip()
    except Exception:
        return "unknown"


def _config_hash(cfg: Config) -> str:
    blob = json.dumps(cfg.to_dict(), sort_keys=True, default=str).encode()
    return hashlib.sha256(blob).hexdigest()


def run_study(cfg: Config, out_dir: str | Path, smoke: bool = False) -> dict:
    """Execute the study; returns the manifest dict."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    n = int(cfg.study.smoke_n_items if smoke else cfg.study.n_items)
    campaign_n = int(cfg.faults.campaign.smoke_n_requests if smoke
                     else cfg.faults.campaign.n_requests)
    t_start = time.time()

    sink = TelemetrySink()
    n_conditions = 0
    for pattern_id in PatternId:
        for platform in Platform:
            for scenario in ScenarioId:
                run_condition(pattern_id, platform, scenario, n=n,
                              cfg=cfg, sink=sink)
                n_conditions += 1

    fault_rows: list[dict] = []
    for pattern_id in PatternId:
        for platform in Platform:
            outcomes = run_campaign(pattern_id, platform, FAULT_SCENARIO,
                                    cfg, sink, n=campaign_n)
            for o in outcomes:
                fault_rows.append({
                    "pattern": pattern_id.value,
                    "platform": platform.value,
                    "scenario": FAULT_SCENARIO.value,
                    "component": o.component.value,
                    "fault": o.fault.value,
                    "contained": o.contained,
                    "requests_affected": o.requests_affected,
                    "n_traversing": o.n_traversing,
                    "n_non_traversing": o.n_non_traversing,
                    "non_traversing_success_rate": o.non_traversing_success_rate,
                    "traversing_success_rate": o.traversing_success_rate,
                })

    sink.to_dataframe("latency").to_csv(out / "latency.csv", index=False)
    sink.to_dataframe("cost").to_csv(out / "cost.csv", index=False)
    pd.DataFrame(fault_rows).to_csv(out / "faults.csv", index=False)

    manifest = {
        "seed": int(cfg.to_dict().get("seed", 0)),
        "config_hash": _config_hash(cfg),
        "n_per_condition": n,
        "n_baseline_conditions": n_conditions,
        "fault_campaign_n_per_cell": campaign_n,
        "fault_campaign_cells": len(fault_rows),
        "fault_campaign_scenario": FAULT_SCENARIO.value,
        "smoke": smoke,
        "git_rev": _git_rev(),
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "wall_time_s": round(time.time() - t_start, 3),
        "n_latency_records": len(sink.latency),
        "n_cost_records": len(sink.cost),
    }
    with open(out / "manifest.json", "w") as f:
        json.dump(manifest, f, indent=2)
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the agentorch measurement study")
    parser.add_argument("--smoke", action="store_true",
                        help="reduced-n smoke run")
    parser.add_argument("--out", default="results/", help="output directory")
    parser.add_argument("--config", default=None, help="config YAML path")
    args = parser.parse_args(argv)
    cfg = load_config(args.config)
    manifest = run_study(cfg, args.out, smoke=args.smoke)
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
