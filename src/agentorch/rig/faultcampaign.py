"""Fault-injection campaign (Algorithm 2, task 029).

For each (component, fault_type) cell in the campaign config, run a
measurement window with the injector armed at the configured
probability, then classify the cell:

- **contained**: failures are confined to requests that actually
  traversed the faulted component, AND the success rate of requests
  that did NOT traverse it is at least ``faults.containment_threshold``.
- **propagated** otherwise (a non-traversing request failed, or the
  blast radius depressed the non-traversing success rate).

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


@dataclass
class CellOutcome:
    """Classification of one (component, fault_type) campaign cell."""

    component: Component
    fault: FaultType
    contained: bool
    requests_affected: int
    n_traversing: int
    n_non_traversing: int
    non_traversing_success_rate: float


def classify_cell(component: Component, fault: FaultType,
                  per_request: list[tuple[bool, bool]],
                  threshold: float) -> CellOutcome:
    """Classify from per-request (traversed_faulted_component, success) pairs."""
    traversing = [(t, s) for t, s in per_request if t]
    non_traversing = [(t, s) for t, s in per_request if not t]
    affected = sum(1 for _, s in traversing if not s)
    non_trav_failures = sum(1 for _, s in non_traversing if not s)
    if non_traversing:
        nt_success = 1.0 - non_trav_failures / len(non_traversing)
    else:
        nt_success = 1.0
    contained = non_trav_failures == 0 and nt_success >= threshold
    return CellOutcome(
        component=component,
        fault=fault,
        contained=contained,
        requests_affected=affected + non_trav_failures,
        n_traversing=len(traversing),
        n_non_traversing=len(non_traversing),
        non_traversing_success_rate=nt_success,
    )


def run_cell(pattern_id: PatternId, platform: Platform, scenario: ScenarioId,
             component: Component, fault: FaultType, cfg: Config,
             sink: TelemetrySink, n: int, probability: float) -> CellOutcome:
    """Run one campaign cell: armed window of n requests through the pattern."""
    ctx = CallContext.build(cfg, sink=sink)
    pattern = build(pattern_id, platform, ctx, cfg)
    ctx.fault_injector.arm(component, fault, probability)
    stream = (f"campaign:{pattern_id.value}:{platform.value}:{scenario.value}:"
              f"{component.value}:{fault.value}")
    items = generate(scenario, n, cfg.get_rng(f"items:{stream}"), cfg)

    per_request: list[tuple[bool, bool]] = []

    def service_fn(item):
        result, service_s = pattern.run(item)
        traversed = component in ctx.components_touched
        injected = next((f for c, f in ctx.faults_seen if c is component), None)
        per_request.append((traversed, result.ok))
        return service_s, result.ok, injected

    run_open_loop(pattern, items, rate_rps=float(cfg.study.rate_rps),
                  concurrency=int(cfg.study.concurrency), sink=sink,
                  rng=cfg.get_rng(stream), mode=Mode.FAULT,
                  pattern_id=pattern_id, service_time_fn=service_fn)
    ctx.fault_injector.disarm(component)

    threshold = float(cfg.faults.containment_threshold)
    outcome = classify_cell(component, fault, per_request, threshold)
    sink.record_fault(FaultRecord(
        component=component, fault=fault,
        contained=outcome.contained,
        requests_affected=outcome.requests_affected,
    ))
    return outcome


def run_campaign(pattern_id: PatternId, platform: Platform, scenario: ScenarioId,
                 cfg: Config, sink: TelemetrySink,
                 n: int | None = None) -> list[CellOutcome]:
    """Algorithm 2: sweep all (component, fault_type) cells in the config."""
    campaign = cfg.faults.campaign
    if n is None:
        n = int(campaign.n_requests)
    probability = float(campaign.probability)
    outcomes: list[CellOutcome] = []
    for comp_name in campaign.components:
        component = Component(comp_name)
        for fault_name in campaign.fault_types:
            fault = FaultType(fault_name)
            outcomes.append(run_cell(pattern_id, platform, scenario, component,
                                     fault, cfg, sink, n, probability))
    return outcomes
