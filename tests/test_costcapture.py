"""Task 030 (HUMAN-gated): cost-capture harness + per-pattern ledger."""
import pytest

from agentorch.clients.context import CallContext
from agentorch.config import load_config
from agentorch.cost import CostModel
from agentorch.domain import WorkItem
from agentorch.patterns.registry import build
from agentorch.rig.costcapture import aggregate_ledger, capture_request_cost, write_ledger
from agentorch.rig.loadgen import run_condition
from agentorch.telemetry import TelemetrySink
from agentorch.types import PatternId, Platform, ScenarioId


def test_capture_matches_cost_model_recomputation() -> None:
    """The captured cost must equal CostModel.request_cost recomputed from
    the same counters (no hidden constants)."""
    cfg = load_config()
    sink = TelemetrySink()
    ctx = CallContext.build(cfg, sink=sink)
    pattern = build(PatternId.GATEWAY, Platform.BEDROCK, ctx, cfg)
    item = WorkItem(id="c1", scenario=ScenarioId.S1, payload={"task": "x"})
    pattern.run(item)
    rec = capture_request_cost(ctx, sink, item.id, PatternId.GATEWAY,
                               Platform.BEDROCK)
    model = CostModel(cfg)
    expected = model.request_cost(Platform.BEDROCK,
                                  model_invocations=ctx.model_invocations,
                                  tokens_in=ctx.tokens_in,
                                  tokens_out=ctx.tokens_out,
                                  service_calls=list(ctx.services_called))
    assert rec.cost_units == pytest.approx(expected)
    assert rec.cost_units > 0
    assert sink.cost[-1] is rec


def test_loadgen_emits_cost_records() -> None:
    cfg = load_config()
    sink = TelemetrySink()
    run_condition(PatternId.SUPERVISOR, Platform.BEDROCK, ScenarioId.S1,
                  n=12, cfg=cfg, sink=sink)
    assert len(sink.cost) == 12
    assert all(r.cost_units > 0 for r in sink.cost)
    assert all(r.model_invocations >= 1 for r in sink.cost)


def test_ledger_aggregates_per_pattern_platform(tmp_path) -> None:
    cfg = load_config()
    sink = TelemetrySink()
    for pid in (PatternId.SUPERVISOR, PatternId.PIPELINE):
        for plat in (Platform.BEDROCK, Platform.AGENTFORCE):
            run_condition(pid, plat, ScenarioId.S1, n=5, cfg=cfg, sink=sink)
    ledger = write_ledger(sink, tmp_path / "cost_ledger.csv")
    assert len(ledger) == 4  # 2 patterns x 2 platforms
    assert (ledger["n_requests"] == 5).all()
    # mean * n == total (consistency of the aggregation).
    assert (ledger["mean_cost_units"] * ledger["n_requests"]).round(10).equals(
        ledger["total_cost_units"].round(10))
    assert (tmp_path / "cost_ledger.csv").exists()


def test_ledger_empty_frame() -> None:
    import pandas as pd
    ledger = aggregate_ledger(pd.DataFrame())
    assert ledger.empty
    assert "mean_cost_units" in ledger.columns


def test_cost_capture_deterministic() -> None:
    cfg = load_config()
    s1, s2 = TelemetrySink(), TelemetrySink()
    run_condition(PatternId.BRIDGE, Platform.AGENTFORCE, ScenarioId.S2,
                  n=8, cfg=cfg, sink=s1)
    run_condition(PatternId.BRIDGE, Platform.AGENTFORCE, ScenarioId.S2,
                  n=8, cfg=cfg, sink=s2)
    assert [r.cost_units for r in s1.cost] == [r.cost_units for r in s2.cost]


# ----------------------------------------------------------------------
# Task 105 (HUMAN-gated): cost-sanity assertions on the executed study.
# ----------------------------------------------------------------------

def test_no_zero_cost_condition(smoke_results) -> None:
    """Task 105: NO request bills zero — Agentforce Agent Script action
    paths consume Flex-credit/conversation cost even without an LLM call,
    so the zero-billed-Script artifact cannot reappear."""
    import pandas as pd
    cost = pd.read_csv(smoke_results / "cost.csv")
    assert (cost["cost_units"] > 0).all(), "zero-billed request found"
    # And every (pattern, platform, scenario) condition has nonzero mean.
    means = cost.groupby(["pattern", "platform", "scenario"])["cost_units"].mean()
    assert len(means) == 42
    assert (means > 0).all()


def test_multi_step_s2_costs_more_than_s1_per_pattern(smoke_results) -> None:
    """Task 105: relative-cost sanity — the multi-step scenario S2 costs
    MORE per request than single-step S1 for EVERY pattern on BOTH
    platforms (multi-step content scales token volume on Bedrock and
    per-step Flex-credit actions on Agentforce)."""
    import pandas as pd
    cost = pd.read_csv(smoke_results / "cost.csv")
    means = cost.groupby(["pattern", "platform", "scenario"])["cost_units"].mean()
    for pattern in [f"P{i}" for i in range(1, 8)]:
        for platform in ("agentforce", "bedrock"):
            s1 = means[(pattern, platform, "S1")]
            s2 = means[(pattern, platform, "S2")]
            assert s2 > s1, (pattern, platform, s1, s2)


def test_fanout_p1_costs_more_than_single_chain_p2(smoke_results) -> None:
    """Task 105: P1 supervisor fan-out (plan + k collaborators + synthesis)
    costs more per request than the P2 single-step chain in S1, on both
    platforms — fan-out multiplies model invocations per step count."""
    import pandas as pd
    cost = pd.read_csv(smoke_results / "cost.csv")
    means = cost.groupby(["pattern", "platform", "scenario"])["cost_units"].mean()
    for platform in ("agentforce", "bedrock"):
        assert means[("P1", platform, "S1")] > means[("P2", platform, "S1")], platform


def test_scenario_resolved_ledger(smoke_results, tmp_path) -> None:
    """Task 105: the ledger carries the scenario dimension (42 rows) so
    per-scenario cost claims trace to an aggregated artifact."""
    import pandas as pd
    cost = pd.read_csv(smoke_results / "cost.csv")
    ledger = aggregate_ledger(cost, by_scenario=True)
    assert len(ledger) == 42
    assert "scenario" in ledger.columns
    assert (ledger["mean_cost_units"] > 0).all()
