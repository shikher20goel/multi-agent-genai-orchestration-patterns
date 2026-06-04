"""Shared CallContext for all mock platform clients.

Every mock entry point performs: fault check -> latency sample ->
clock advance -> cost/telemetry accounting, via :meth:`boundary_call`.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from agentorch.clock import VirtualClock
from agentorch.config import Config
from agentorch.faults import FaultInjector
from agentorch.latency import LatencyModel
from agentorch.telemetry import TelemetrySink
from agentorch.types import Component, FaultType, Platform


def _make_cost_model(cfg: Config) -> "object | None":
    """Build the CostModel if available (task 014); otherwise None."""
    try:
        from agentorch.cost import CostModel
    except ImportError:
        return None
    return CostModel(cfg)


@dataclass
class CallOutcome:
    """Result of one boundary call through the shared context."""

    success: bool
    fault: FaultType | None
    elapsed_s: float


@dataclass
class CallContext:
    sink: TelemetrySink
    latency_model: LatencyModel
    fault_injector: FaultInjector
    cost_model: "object | None"
    clock: VirtualClock
    cfg: Config
    # Per-request service-time accumulator (patterns reset/read this).
    elapsed_s: float = field(default=0.0)
    # Running counters a pattern can use for cost accounting.
    model_invocations: int = 0
    service_calls: int = 0
    tokens_in: int = 0
    tokens_out: int = 0
    # Per-request traversal trace (fault-campaign containment analysis).
    components_touched: set = field(default_factory=set)
    faults_seen: list = field(default_factory=list)
    # Per-request billable service-call names (cost capture, task 030).
    services_called: list = field(default_factory=list)

    @classmethod
    def build(cls, cfg: Config, clock: VirtualClock | None = None,
              sink: TelemetrySink | None = None) -> "CallContext":
        return cls(
            sink=sink or TelemetrySink(),
            latency_model=LatencyModel(cfg, cfg.get_rng("latency")),
            fault_injector=FaultInjector(cfg.get_rng("faults")),
            cost_model=_make_cost_model(cfg),
            clock=clock or VirtualClock(),
            cfg=cfg,
        )

    def reset_request(self) -> None:
        self.elapsed_s = 0.0
        self.model_invocations = 0
        self.service_calls = 0
        self.tokens_in = 0
        self.tokens_out = 0
        self.components_touched = set()
        self.faults_seen = []
        self.services_called = []

    def _advance(self, dt: float) -> None:
        self.clock.advance(dt)
        self.elapsed_s += dt

    def boundary_call(self, platform: Platform, service: str,
                      component: Component) -> CallOutcome:
        """Fault check -> latency sample -> clock advance; returns the outcome."""
        fault = self.fault_injector.check(component)
        self.components_touched.add(component)
        if service != "model_invoke":
            self.services_called.append(service)
        if fault is not None:
            self.faults_seen.append((component, fault))
        faults_cfg = self.cfg.faults
        if fault is FaultType.TIMEOUT:
            dt = float(faults_cfg.timeout_s)
            self._advance(dt)
            return CallOutcome(success=False, fault=fault, elapsed_s=dt)
        if fault is FaultType.OUTAGE:
            # Fast failure: the component is down; only a negligible probe delay.
            self._advance(0.0)
            return CallOutcome(success=False, fault=fault, elapsed_s=0.0)
        if fault is FaultType.ERROR:
            dt = self.latency_model.sample(platform, service)
            self._advance(dt)
            return CallOutcome(success=False, fault=fault, elapsed_s=dt)
        dt = self.latency_model.sample(platform, service)
        if fault is FaultType.THROTTLE:
            dt += float(faults_cfg.throttle_delay_s)
        self._advance(dt)
        return CallOutcome(success=True, fault=fault, elapsed_s=dt)
