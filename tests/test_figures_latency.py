"""Task 039 (HUMAN-gated): latency figures generated from results/ only."""
import pandas as pd
import pytest

from agentorch.config import load_config
from agentorch.study.figures_latency import make_ccdf, make_p99_ci
from agentorch.study.run_study import run_study


@pytest.fixture(scope="module")
def smoke_results(tmp_path_factory):
    out = tmp_path_factory.mktemp("resfig")
    run_study(load_config(), out, smoke=True)
    return out


def test_figures_written_nonempty(smoke_results, tmp_path) -> None:
    cfg = load_config()
    lat = pd.read_csv(smoke_results / "latency.csv")
    base = lat[lat["mode"] == "baseline"]
    ccdf = tmp_path / "ccdf.png"
    p99 = tmp_path / "p99_ci.png"
    make_ccdf(base, ccdf)
    make_p99_ci(base, p99, cfg)
    assert ccdf.exists() and ccdf.stat().st_size > 10_000
    assert p99.exists() and p99.stat().st_size > 10_000
    # PNG magic bytes.
    for p in (ccdf, p99):
        assert p.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
