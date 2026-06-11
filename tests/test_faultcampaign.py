"""Task 029/104: fault campaign (Algorithm 2) — outage windows,
structural-unit faults, and the four-way classification."""
from agentorch.config import load_config
from agentorch.rig.faultcampaign import (
    ABSORBED,
    ISOLATED,
    NOT_EXERCISED,
    PROPAGATED,
    classify_cell,
    relevant_components,
    run_campaign,
    run_cell,
)
from agentorch.telemetry import TelemetrySink
from agentorch.types import Component, FaultType, PatternId, Platform, ScenarioId


def test_classify_propagated_when_hit_requests_fail() -> None:
    """A fault that kills the requests traversing it escaped its component."""
    per_request = ([(True, False, False, 1.0)] * 8
                   + [(True, True, False, 1.0)] * 2
                   + [(False, True, False, 1.0)] * 10)
    out = classify_cell(Component.MODEL_BACKEND, FaultType.OUTAGE,
                        per_request, 0.95)
    assert out.classification == PROPAGATED
    assert not out.contained
    assert out.requests_affected == 8


def test_classify_isolated_when_hit_requests_degrade_only() -> None:
    """Bulkhead semantics: hit requests succeed but lose the faulted unit."""
    per_request = ([(True, True, True, 1.0)] * 6
                   + [(False, True, False, 1.0)] * 14)
    out = classify_cell(Component.TOOL, FaultType.OUTAGE, per_request, 0.95)
    assert out.classification == ISOLATED
    assert out.contained
    assert out.traversing_degraded_rate == 1.0


def test_classify_absorbed_when_only_latency_rises() -> None:
    per_request = ([(True, True, False, 9.0)] * 5
                   + [(False, True, False, 1.0)] * 15)
    out = classify_cell(Component.EVENT_BUS, FaultType.OUTAGE, per_request, 0.95)
    assert out.classification == ABSORBED
    assert out.contained
    assert out.fault_mean_latency_s == 9.0


def test_classify_not_exercised_without_traversals() -> None:
    per_request = [(False, True, False, 1.0)] * 10
    out = classify_cell(Component.HUMAN_QUEUE, FaultType.ERROR, per_request, 0.95)
    assert out.classification == NOT_EXERCISED


def test_gateway_pattern_isolates_single_tool_outage() -> None:
    """P5's per-tool bulkheads: ONE tool's outage window degrades only
    that tool's contribution; the requests still succeed (task 104)."""
    cfg = load_config()
    sink = TelemetrySink()
    out = run_cell(PatternId.GATEWAY, Platform.BEDROCK, ScenarioId.S1,
                   Component.TOOL, FaultType.OUTAGE, cfg, sink,
                   n=40, probability=1.0, rate_rps=1.5)
    assert out.classification == ISOLATED
    assert out.n_traversing > 0
    assert out.traversing_success_rate >= 0.95
    assert len(sink.faults) == 1
    assert sink.faults[0].contained


def test_pipeline_stage_outage_propagates_downstream() -> None:
    """P2 SPOF-along-chain: a model-backend outage window blocks the
    stage and every downstream stage — window requests fail outright."""
    cfg = load_config()
    sink = TelemetrySink()
    out = run_cell(PatternId.PIPELINE, Platform.BEDROCK, ScenarioId.S1,
                   Component.MODEL_BACKEND, FaultType.OUTAGE, cfg, sink,
                   n=40, probability=1.0, rate_rps=2.0)
    assert out.classification == PROPAGATED
    assert out.n_traversing > 0
    assert out.traversing_success_rate < 0.5


def test_supervisor_and_blackboard_outages_are_spof() -> None:
    """P1 supervisor outage and P4 store outage are single points of
    failure: every window request fails (task 104 / paper Table 3)."""
    cfg = load_config()
    for pid, comp, rate in ((PatternId.SUPERVISOR, Component.MODEL_BACKEND, 0.6),
                            (PatternId.BLACKBOARD, Component.MEMORY_STORE, 0.7)):
        sink = TelemetrySink()
        out = run_cell(pid, Platform.BEDROCK, ScenarioId.S1, comp,
                       FaultType.OUTAGE, cfg, sink, n=40,
                       probability=1.0, rate_rps=rate)
        assert out.classification == PROPAGATED, (pid, comp)


def test_choreography_bus_outage_absorbed_with_latency_rise() -> None:
    """P3 durable bus: events published into the outage window are
    buffered and redelivered — success preserved, latency up."""
    cfg = load_config()
    sink = TelemetrySink()
    out = run_cell(PatternId.CHOREOGRAPHY, Platform.AGENTFORCE, ScenarioId.S1,
                   Component.EVENT_BUS, FaultType.OUTAGE, cfg, sink,
                   n=40, probability=1.0, rate_rps=0.6)
    assert out.classification == ABSORBED
    assert out.n_traversing > 0
    # Degradation assertion (task 104): the fault must visibly raise
    # latency for the requests it touches.
    assert out.fault_mean_latency_s > out.baseline_mean_latency_s


def test_relevance_map_marks_structural_paths() -> None:
    cfg = load_config()
    rel = relevant_components(PatternId.PIPELINE, Platform.BEDROCK, cfg)
    assert Component.MODEL_BACKEND in rel
    assert Component.HUMAN_QUEUE not in rel
    rel6 = relevant_components(PatternId.HITL, Platform.BEDROCK, cfg)
    assert Component.HUMAN_QUEUE in rel6


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
    # Cells on the pattern's structural path run and emit exactly one
    # FaultRecord each; structurally irrelevant cells are skipped.
    rel = relevant_components(PatternId.GATEWAY, Platform.BEDROCK, cfg)
    n_ran = sum(1 for o in o1 if o.component in rel)
    assert len(s1.faults) == n_ran
    assert [(o.component, o.fault, o.classification, o.requests_affected)
            for o in o1] == \
        [(o.component, o.fault, o.classification, o.requests_affected)
         for o in o2]


def test_faults_degrade_the_affected_condition() -> None:
    """Task 104 exit: an injected fault raises error rate or latency for
    the affected pattern versus its clean baseline."""
    cfg = load_config()
    sink = TelemetrySink()
    outcomes = run_campaign(PatternId.PIPELINE, Platform.AGENTFORCE,
                            ScenarioId.S1, cfg, sink, n=20)
    exercised = [o for o in outcomes if o.classification != NOT_EXERCISED
                 and o.n_traversing > 0]
    assert exercised, "campaign must exercise some cells"
    for o in exercised:
        degraded = (o.traversing_success_rate < 1.0
                    or o.fault_mean_latency_s > o.baseline_mean_latency_s)
        assert degraded, (o.component, o.fault)
