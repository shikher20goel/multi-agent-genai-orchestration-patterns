"""Task 040 (HUMAN-gated): cost figure + ledger generated from results/."""
import pandas as pd
import pytest

from agentorch.config import load_config
from agentorch.rig.costcapture import aggregate_ledger
from agentorch.study.figures_cost import make_cost_per_1k
from agentorch.study.run_study import run_study


@pytest.fixture(scope="module")
def smoke_results(tmp_path_factory):
    out = tmp_path_factory.mktemp("rescost")
    run_study(load_config(), out, smoke=True)
    return out


def test_cost_outputs(smoke_results, tmp_path) -> None:
    cost = pd.read_csv(smoke_results / "cost.csv")
    ledger = aggregate_ledger(cost)
    # 7 patterns x 2 platforms.
    assert len(ledger) == 14
    png = tmp_path / "cost_per_1k.png"
    make_cost_per_1k(ledger, png)
    assert png.exists() and png.stat().st_size > 10_000
    assert png.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
    # Ledger traces to raw rows: total = sum of cost_units per group.
    one = ledger.iloc[0]
    raw = cost[(cost["pattern"] == one["pattern"])
               & (cost["platform"] == one["platform"])]["cost_units"]
    assert one["total_cost_units"] == pytest.approx(raw.sum())
