"""Shared CallContext for all mock platform clients.

Every mock entry point performs: fault check -> latency sample ->
clock advance -> cost/telemetry accounting, via :meth:`boundary_call`.

Phase 2 (task 103): each (pattern, platform, scenario) condition builds
its CallContext with a condition-specific ``stream_prefix`` so latency
and fault draws come from *independent* child RNG streams (seed derived
from master seed + full condition string). No common-random-numbers
coupling remains across conditions (SAP Option A).

Phase 2 (task 104): boundary calls carry the simulated request time
(``request_start_ts + elapsed_s``) and an optional sub-``unit`` label so
cross-request outage *windows* and single-unit faults (one tool, one
cluster) can be injected.
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
    # Portion of elapsed_s that does NOT occupy a compute server: a P6
    # request waiting on a human decision releases its server (the human
    # queue is a separate resource); end-to-end latency still includes
    # the wait (task 101).
    nonblocking_s: float = field(default=0.0)
    # Simulated arrival-timeline start of the current request (set by the
    # load generator); simulated "now" = request_start_ts + elapsed_s.
    request_start_ts: float = 0.0
    # Concurrent in-flight requests at this request's start (set by the
    # load generator; drives the P4 write-contention term, task 101).
    concurrent_in_flight: int = 1
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
    # Content-volume multiplier for the NEXT model invocation's token
    # accounting (task 105): an invocation that generates the content of
    # a multi-step work item (e.g. a 6-section document drafted in one
    # call) produces proportionally more tokens. Patterns set this to the
    # number of scenario steps the invocation covers; default 1.
    content_scale: float = 1.0
    # Per-request degradation marker: the request completed but lost the
    # work of a faulted sub-unit (bulkhead/bridge isolation, task 104).
    degraded: bool = False
    # Unit label applied to every boundary call from this context when the
    # call itself names none (e.g. "remote" for the P7 remote cluster).
    default_unit: "str | None" = None

    @classmethod
    def build(cls, cfg: Config, clock: VirtualClock | None = None,
              sink: TelemetrySink | None = None,
              stream_prefix: str = "",
              fault_injector: FaultInjector | None = None) -> "CallContext":
        """Build a context; `stream_prefix` namespaces the RNG streams.

        Task 103: pass the full condition string (e.g.
        ``"P2:bedrock:S2:baseline"``) so every condition draws from
        independent child streams.
        """
        prefix = f"{stream_prefix}:" if stream_prefix else ""
        return cls(
            sink=sink or TelemetrySink(),
            latency_model=LatencyModel(cfg, cfg.get_rng(f"{prefix}latency")),
            fault_injector=fault_injector
            or FaultInjector(cfg.get_rng(f"{prefix}faults")),
            cost_model=_make_cost_model(cfg),
            clock=clock or VirtualClock(),
            cfg=cfg,
        )

    def reset_request(self) -> None:
        self.elapsed_s = 0.0
        self.content_scale = 1.0
        self.nonblocking_s = 0.0
        self.model_invocations = 0
        self.service_calls = 0
        self.tokens_in = 0
        self.tokens_out = 0
        self.components_touched = set()
        self.faults_seen = []
        self.services_called = []
        self.degraded = False

    @property
    def sim_now(self) -> float:
        """Simulated time of the current call on the arrival timeline."""
        return self.request_start_ts + self.elapsed_s

    def _advance(self, dt: float) -> None:
        self.clock.advance(dt)
        self.elapsed_s += dt

    def add_delay(self, dt: float, blocking: bool = True) -> None:
        """Add a structural delay term to the current request (task 101/104).

        ``blocking=False`` marks the delay as not occupying a compute
        server (human review wait): it extends end-to-end latency but
        not the server pool's busy time.
        """
        if dt < 0:
            raise ValueError("delay must be non-negative")
        self._advance(dt)
        if not blocking:
            self.nonblocking_s += dt

    def boundary_call(self, platform: Platform, service: str,
                      component: Component,
                      unit: str | None = None) -> CallOutcome:
        """Fault check -> latency sample -> clock advance; returns the outcome."""
        if unit is None:
            unit = self.default_unit
        fault = self.fault_injector.check(component, unit=unit, now=self.sim_now)
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
