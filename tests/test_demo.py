"""Smoke test for demo.sh (task 056)."""
from __future__ import annotations

import os
import pathlib
import subprocess

REPO = pathlib.Path(__file__).resolve().parents[1]


def test_demo_runs_end_to_end(tmp_path):
    results = tmp_path / "results_demo"
    figures = tmp_path / "figures_demo"
    proc = subprocess.run(
        ["bash", str(REPO / "demo.sh")],
        capture_output=True, text=True, timeout=40,
        env={**os.environ,
             "DEMO_RESULTS": str(results), "DEMO_FIGURES": str(figures),
             "MPLBACKEND": "Agg"},
        cwd=str(REPO),
    )
    assert proc.returncode == 0, proc.stderr
    # smoke study outputs
    for f in ("latency.csv", "cost.csv", "faults.csv", "manifest.json"):
        assert (results / f).is_file(), f
    # demo figure
    assert (figures / "p99_ci.png").is_file()
    # printed summary table covers all seven patterns and both platforms
    out = proc.stdout
    for pat in ("P1", "P2", "P3", "P4", "P5", "P6", "P7"):
        assert pat in out
    assert "agentforce" in out and "bedrock" in out
    assert "demo complete" in out
