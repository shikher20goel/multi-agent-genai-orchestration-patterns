"""Task 037 (HUMAN-gated): Table 3 built from results/ only, CI sanity."""
import numpy as np
import pandas as pd
import pytest

from agentorch.config import load_config
from agentorch.study.make_table3 import build_table3
from agentorch.study.run_study import run_study


@pytest.fixture(scope="module")
def smoke_results(tmp_path_factory):
    out = tmp_path_factory.mktemp("res")
    cfg = load_config()
    run_study(cfg, out, smoke=True)
    return out


@pytest.fixture(scope="module")
def table3(smoke_results):
    return build_table3(smoke_results)


def test_table3_covers_all_42_conditions(table3) -> None:
    df = table3
    assert len(df) == 42
    assert set(df["pattern"]) == {f"P{i}" for i in range(1, 8)}
    assert set(df["platform"]) == {"agentforce", "bedrock"}
    assert set(df["scenario"]) == {"S1", "S2", "S3"}


def test_table3_values_trace_to_raw_results(smoke_results, table3) -> None:
    """Spot-check: p50 equals np.percentile of the raw baseline rows."""
    df = table3
    lat = pd.read_csv(smoke_results / "latency.csv")
    base = lat[lat["mode"] == "baseline"]
    row = df[(df["pattern"] == "P2") & (df["platform"] == "bedrock")
             & (df["scenario"] == "S1")].iloc[0]
    raw = base[(base["pattern"] == "P2") & (base["platform"] == "bedrock")
               & (base["scenario"] == "S1")]["latency_ms"].to_numpy()
    assert row["p50_ms"] == pytest.approx(np.percentile(raw, 50))
    assert row["n"] == len(raw)
    assert 0.0 <= row["error_rate"] <= 1.0
    assert row["cost_per_request"] > 0


def test_table3_cis_bracket_point_estimates(table3) -> None:
    df = table3
    for p in (50, 95, 99):
        assert (df[f"p{p}_ci_lo"] <= df[f"p{p}_ms"] + 1e-9).all()
        assert (df[f"p{p}_ci_hi"] >= df[f"p{p}_ms"] - 1e-9).all()
    # Percentile ordering.
    assert (df["p50_ms"] <= df["p95_ms"]).all()
    assert (df["p95_ms"] <= df["p99_ms"]).all()
