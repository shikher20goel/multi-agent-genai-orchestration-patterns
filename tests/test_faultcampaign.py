"""Task 029: fault campaign (Algorithm 2) contained/propagated classification."""
from agentorch.config import load_config
from agentorch.rig.faultcampaign import classify_cell, run_campaign, run_cell
from agentorch.telemetry import TelemetrySink
from agentorch.types import Component, FaultType, PatternId, Platform, ScenarioId


def test_classify_contained_when_only_traversing_fail() -> None:
    per_request = [(True, False)] * 5 + [(True, True)] * 5 + [(False, True)] * 10
    out = classify_cell(Component.TOOL, FaultType.ERROR, per_request, 0.95)
    assert out.contained
    assert out.requests_affected == 5
    assert out.non_traversing_success_rate == 1.0


def test_classify_propagated_when_non_traversing_fails() -> None:
    per_request = [(True, False)] * 5 + [(False, False)] * 2 + [(False, True)] * 13
    out = classify_cell(Component.TOOL, FaultType.ERROR, per_request, 0.95)
    assert not out.contained
    assert out.requests_affected == 7


def test_gateway_pattern_contains_tool_faults() -> None:
    """P5's per-tool bulkheads: a TOOL outage must be contained."""
    cfg = load_config()
    sink = TelemetrySink()
    out = run_cell(PatternId.GATEWAY, Platform.BEDROCK, ScenarioId.S1,
                   Component.TOOL, FaultType.OUTAGE, cfg, sink,
                   n=30, probability=1.0)
    assert out.contained
    assert len(sink.faults) == 1
    assert sink.faults[0].contained


def test_model_backend_outage_propagates_in_pipeline() -> None:
    """P2 has no fallback for the model backend: outage at p=1 fails every
    request that traverses it; with all requests traversing, containment
    still holds formally, so use a record-level check instead: the cell
    reports every request affected."""
    cfg = load_config()
    sink = TelemetrySink()
    out = run_cell(PatternId.PIPELINE, Platform.BEDROCK, ScenarioId.S1,
                   Component.MODEL_BACKEND, FaultType.OUTAGE, cfg, sink,
                   n=20, probability=1.0)
    assert out.n_traversing == 20
    assert out.requests_affected == 20


def test_campaign_emits_record_per_cell_and_is_deterministic() -> None:
    cfg = load_config()
    s1, s2 = TelemetrySink(), TelemetrySink()
    o1 = run_campaign(PatternId.GATEWAY, Platform.BEDROCK, ScenarioId.S1,
                      cfg, s1, n=6)
    o2 = run_campaign(PatternId.GATEWAY, Platform.BEDROCK, ScenarioId.S1,
                      cfg, s2, n=6)
    n_cells = (len(cfg.faults.campaign.components)
               * len(cfg.faults.campaign.fault_types))
    assert len(o1) == n_cells
    assert len(s1.faults) == n_cells
    assert [(o.component, o.fault, o.contained, o.requests_affected) for o in o1] \
        == [(o.component, o.fault, o.contained, o.requests_affected) for o in o2]
