"""Task 036: study orchestrator smoke-run writes all results files."""
import json

import pandas as pd

from agentorch.config import load_config
from agentorch.study.run_study import run_study


def test_smoke_run_writes_results(tmp_path) -> None:
    cfg = load_config()
    manifest = run_study(cfg, tmp_path, smoke=True)
    for name in ("latency.csv", "cost.csv", "faults.csv", "manifest.json"):
        assert (tmp_path / name).exists(), name
    lat = pd.read_csv(tmp_path / "latency.csv")
    n = int(cfg.study.smoke_n_items)
    # 42 baseline conditions + fault-mode records on top.
    assert (lat["mode"] == "baseline").sum() == 42 * n
    assert (lat["mode"] == "fault").sum() > 0
    cost = pd.read_csv(tmp_path / "cost.csv")
    assert len(cost) == 42 * n  # baseline-only cost capture
    faults = pd.read_csv(tmp_path / "faults.csv")
    # 7 patterns x 2 platforms x 6 components x 4 fault types.
    assert len(faults) == 7 * 2 * 6 * 4
    assert set(faults["contained"].unique()) <= {True, False}
    with open(tmp_path / "manifest.json") as f:
        m = json.load(f)
    assert m["seed"] == 42
    assert m == manifest


def test_smoke_run_deterministic(tmp_path) -> None:
    cfg = load_config()
    run_study(cfg, tmp_path / "a", smoke=True)
    run_study(cfg, tmp_path / "b", smoke=True)
    for name in ("latency.csv", "cost.csv", "faults.csv"):
        assert (tmp_path / "a" / name).read_text() == \
            (tmp_path / "b" / name).read_text(), name
