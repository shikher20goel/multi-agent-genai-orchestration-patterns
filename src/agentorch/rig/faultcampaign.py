"""Fault-injection campaign (Algorithm 2, task 029; realism task 104).

For each pattern, only the components on that pattern's STRUCTURAL PATH
are exercised (a clean probe records the components the pattern
actually traverses); ``NOT_EXERCISED`` is reserved for structurally
irrelevant component x pattern pairs.

Fault modes:

- **OUTAGE** cells use a cross-request outage WINDOW: the component is
  down for ``faults.campaign.outage_window_fraction`` of the run,
  centred mid-run on the simulated arrival timeline, and every request
  traversing it during the window is affected (cross-request fault
  state at the injector).
- **TIMEOUT / ERROR / THROTTLE** cells remain per-call probabilistic
  faults at ``faults.campaign.probability``.

Structural-role units (task 104): the generic component is mapped onto
the pattern's structural role where the paper implies a finer unit —
P5's TOOL fault targets ONE tool behind the gateway bulkhead, and P7's
cluster-outage cell targets the REMOTE cluster (unit="remote").

Classification (matches the paper's Table 3 consequences):

- ``PROPAGATED``  — requests that traversed the faulted component fail
  outright: the fault escaped its component and took the request (and
  any downstream stages / fan-in work) with it. P1 supervisor outage
  and P4 store outage are SPOFs; a P2 stage fault blocks downstream.
- ``ISOLATED``    — traversing requests complete but DEGRADED: only the
  faulted unit's work is lost (P5 bulkhead, P7 bridged work).
- ``ABSORBED``    — traversing requests complete fully (success rate >=
  ``faults.containment_threshold``) with elevated latency only (P3
  buffered redelivery, P6 deferred human decisions, throttles).
- ``NOT_EXERCISED`` — the pattern never traverses the component.

``contained`` (back-compat boolean) is ``classification != PROPAGATED``.
One FaultRecord per cell is emitted into the sink.
"""
from __future__ import annotations

from dataclasses import dataclass

from agentorch.clients.context import CallContext
from agentorch.config import Config
from agentorch.patterns.registry import build
from agentorch.rig.loadgen import run_open_loop
from agentorch.scenarios import generate
from agentorch.telemetry import FaultRecord, TelemetrySink
from agentorch.types import Component, FaultType, Mode, PatternId, Platform, ScenarioId

PROPAGATED = "propagated"
ISOLATED = "isolated"
ABSORBED = "absorbed"
NOT_EXERCISED = "not_exercised"


@dataclass
class CellOutcome:
    """Classification of one (component, fault_type) campaign cell."""

    component: Component
    fault: FaultType
    classification: str
    contained: bool
    requests_affected: int
    n_traversing: int
    n_non_traversing: int
    non_traversing_success_rate: float
    traversing_success_rate: float
    traversing_degraded_rate: float = 0.0
    baseline_mean_latency_s: float = 0.0
    fault_mean_latency_s: float = 0.0


def structural_unit(pattern_id: PatternId, platform: Platform,
                    component: Component, cfg: Config) -> str | None:
    """Map a generic component onto the pattern's structural role unit.

    - P5 x TOOL: fault ONE tool behind the gateway (bulkhead test); on
      Agentforce the gated tools are actions named ``tool_<name>``.
    - P7 x MODEL_BACKEND: fault the REMOTE cluster (unit="remote") —
      the paper's platform-outage-containment claim is about the
      federated cluster, not the local one.
    Everything else faults the whole component.
    """
    if pattern_id is PatternId.GATEWAY and component is Component.TOOL:
        first_tool = str(list(cfg.patterns.p5.tools)[0])
        return (first_tool if platform is Platform.BEDROCK
                else f"tool_{first_tool}")
    if pattern_id is PatternId.BRIDGE and component is Component.MODEL_BACKEND:
        return "remote"
    return None


def relevant_components(pattern_id: PatternId, platform: Platform,
                        cfg: Config) -> set[Component]:
    """Components on the pattern's structural path, from a clean probe.

    NOT_EXERCISED cells are exactly the complement of this set (the
    structurally irrelevant component x pattern pairs).
    """
    sink = TelemetrySink()
    stream = f"relevance:{pattern_id.value}:{platform.value}"
    ctx = CallContext.build(cfg, sink=sink, stream_prefix=stream)
    pattern = build(pattern_id, platform, ctx, cfg)
    # S1 items carry the hitl_review_fraction confidence draws, so a P6
    # probe of this size adjudicates with near-certainty.
    items = generate(ScenarioId.S1, 24, cfg.get_rng(f"items:{stream}"), cfg)
    touched: set[Component] = set()
    for item in items:
        pattern.run(item)
        touched |= set(ctx.components_touched)
        if hasattr(pattern, "remote_ctx"):
            touched |= set(pattern.remote_ctx.components_touched)
    return touched


def classify_cell(component: Component, fault: FaultType,
                  per_request: list[tuple[bool, bool, bool, float]],
                  threshold: float,
                  baseline_mean_latency_s: float = 0.0) -> CellOutcome:
    """Classify from per-request (traversed, success, degraded, latency_s).

    traversed = the injected fault actually fired on at least one of the
    request's boundary calls to the faulted component.
    """
    traversing = [r for r in per_request if r[0]]
    non_traversing = [r for r in per_request if not r[0]]
    affected = sum(1 for r in traversing if not r[1] or r[2])
    nt_failures = sum(1 for r in non_traversing if not r[1])
    nt_success = (1.0 - nt_failures / len(non_traversing)
                  if non_traversing else 1.0)
    t_success = (sum(1 for r in traversing if r[1]) / len(traversing)
                 if traversing else 1.0)
    t_degraded = (sum(1 for r in traversing if r[2]) / len(traversing)
                  if traversing else 0.0)
    fault_mean_lat = (sum(r[3] for r in traversing) / len(traversing)
                      if traversing else 0.0)

    if not traversing:
        classification = NOT_EXERCISED
    elif t_success < threshold:
        classification = PROPAGATED   # the fault took whole requests down
    elif t_degraded > 0.0:
        classification = ISOLATED     # only the faulted unit's work lost
    else:
        classification = ABSORBED     # success preserved; latency-only hit

    return CellOutcome(
        component=component,
        fault=fault,
        classification=classification,
        contained=classification != PROPAGATED,
        requests_affected=affected + nt_failures,
        n_traversing=len(traversing),
        n_non_traversing=len(non_traversing),
        non_traversing_success_rate=nt_success,
        traversing_success_rate=t_success,
        traversing_degraded_rate=t_degraded,
        baseline_mean_latency_s=baseline_mean_latency_s,
        fault_mean_latency_s=fault_mean_lat,
    )


def run_cell(pattern_id: PatternId, platform: Platform, scenario: ScenarioId,
             component: Component, fault: FaultType, cfg: Config,
             sink: TelemetrySink, n: int, probability: float,
             rate_rps: float, baseline_mean_latency_s: float = 0.0
             ) -> CellOutcome:
    """Run one campaign cell: a window of n requests through the pattern."""
    stream = (f"campaign:{pattern_id.value}:{platform.value}:{scenario.value}:"
              f"{component.value}:{fault.value}")
    ctx = CallContext.build(cfg, sink=sink, stream_prefix=stream)
    pattern = build(pattern_id, platform, ctx, cfg)
    unit = structural_unit(pattern_id, platform, component, cfg)

    if fault is FaultType.OUTAGE:
        # Cross-request outage window centred mid-run (task 104).
        horizon = n / rate_rps
        frac = float(cfg.faults.campaign.outage_window_fraction)
        start = horizon * (0.5 - frac / 2.0)
        end = horizon * (0.5 + frac / 2.0)
        ctx.fault_injector.arm_window(component, fault, start, end, unit=unit)
    else:
        ctx.fault_injector.arm(component, fault, probability, unit=unit)

    items = generate(scenario, n, cfg.get_rng(f"items:{stream}"), cfg)
    per_request: list[tuple[bool, bool, bool, float]] = []

    def service_fn(item):
        result, service_s = pattern.run(item)
        observed = [f for c, f in ctx.faults_seen if c is component]
        if hasattr(pattern, "remote_ctx"):
            observed += [f for c, f in pattern.remote_ctx.faults_seen
                         if c is component]
        injected = observed[0] if observed else None
        traversed = injected is not None
        degraded = bool(ctx.degraded)
        per_request.append((traversed, result.ok, degraded, service_s))
        return service_s, result.ok, injected

    run_open_loop(pattern, items, rate_rps=rate_rps,
                  concurrency=int(cfg.study.concurrency), sink=sink,
                  rng=cfg.get_rng(stream), mode=Mode.FAULT,
                  pattern_id=pattern_id, service_time_fn=service_fn)
    ctx.fault_injector.disarm(component)

    threshold = float(cfg.faults.containment_threshold)
    outcome = classify_cell(component, fault, per_request, threshold,
                            baseline_mean_latency_s)
    sink.record_fault(FaultRecord(
        component=component, fault=fault,
        contained=outcome.contained,
        requests_affected=outcome.requests_affected,
    ))
    return outcome


def run_campaign(pattern_id: PatternId, platform: Platform, scenario: ScenarioId,
                 cfg: Config, sink: TelemetrySink,
                 n: int | None = None) -> list[CellOutcome]:
    """Algorithm 2 (task 104): sweep the structurally relevant
    (component, fault_type) cells; emit NOT_EXERCISED rows for the rest
    so the matrix stays complete."""
    from agentorch.rig.loadgen import probe_service_rate

    campaign = cfg.faults.campaign
    if n is None:
        n = int(campaign.n_requests)
    probability = float(campaign.probability)

    # Per-(pattern, platform) load point: same below-saturation rule as
    # the baseline (task 102), probed once per campaign.
    stream = f"campaign:{pattern_id.value}:{platform.value}:{scenario.value}"
    mean_service = probe_service_rate(pattern_id, platform, scenario, cfg, stream)
    base_c = int(cfg.study.concurrency)
    rate = float(cfg.load.utilization_target) * base_c / mean_service

    relevant = relevant_components(pattern_id, platform, cfg)
    outcomes: list[CellOutcome] = []
    for comp_name in campaign.components:
        component = Component(comp_name)
        for fault_name in campaign.fault_types:
            fault = FaultType(fault_name)
            if component not in relevant:
                outcomes.append(CellOutcome(
                    component=component, fault=fault,
                    classification=NOT_EXERCISED, contained=True,
                    requests_affected=0, n_traversing=0,
                    n_non_traversing=0, non_traversing_success_rate=1.0,
                    traversing_success_rate=1.0,
                    baseline_mean_latency_s=mean_service))
                continue
            cell_n = n
            rare = [str(x) for x in campaign.get("rare_path_components", [])]
            if component.value in rare:
                cell_n = n * int(campaign.get("rare_path_boost", 1))
            outcomes.append(run_cell(pattern_id, platform, scenario, component,
                                     fault, cfg, sink, cell_n, probability,
                                     rate_rps=rate,
                                     baseline_mean_latency_s=mean_service))
    return outcomes
