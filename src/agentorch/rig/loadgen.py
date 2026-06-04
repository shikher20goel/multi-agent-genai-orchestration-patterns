"""Open-loop load generator (Algorithm 1, task 027; calibrated tasks
101/102).

Arrivals follow a Poisson process: the FULL arrival schedule is drawn
up front, and every request's ``submit_ts`` comes from that schedule —
never from the previous completion — so the generator keeps issuing
during stalls and measured latency includes queueing delay
(coordinated-omission correct). For the bursty scenario S3 the Poisson
intensity is piecewise: ``burst_fraction`` of the window runs at
``burst_factor`` x the base rate (configs ``scenarios.s3``).

Task 102: the offered rate is no longer a fixed config constant.
``run_condition`` first probes the condition's single-replica service
time, estimates the saturation rate (concurrency / mean service time),
and offers ``load.utilization_target`` x that rate, so p99 is never an
unbounded-queue artifact and S1's fast conditions are driven at rates
that genuinely stress coordination.

Service is a concurrency-``c`` pool: request i starts at
``max(submit_ts_i, earliest_free_server)`` and completes at
``start + service_time``. Task 101: P3's effective pool is
``concurrency x patterns.p3.consumer_scale`` — choreography consumers
are decoupled bus subscribers that scale with queue depth, which is the
structural mechanism of burst absorption. Service times come from
running the work item through the pattern (virtual clock; nothing
sleeps).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

import numpy as np

from agentorch.config import Config
from agentorch.domain import WorkItem
from agentorch.patterns.base import Pattern
from agentorch.telemetry import LatencyRecord, TelemetrySink
from agentorch.types import FaultType, Mode, PatternId, Platform, ScenarioId


def poisson_arrivals(n: int, rate_rps: float, rng: np.random.Generator,
                     start: float = 0.0) -> np.ndarray:
    """Cumulative arrival times for `n` Poisson arrivals at `rate_rps`."""
    if rate_rps <= 0:
        raise ValueError("rate_rps must be positive")
    gaps = rng.exponential(scale=1.0 / rate_rps, size=n)
    return start + np.cumsum(gaps)


def bursty_arrivals(n: int, base_rate_rps: float, rng: np.random.Generator,
                    burst_factor: float, burst_fraction: float,
                    cycle_s: float = 60.0, start: float = 0.0) -> np.ndarray:
    """Piecewise-Poisson arrivals: within each `cycle_s` window the first
    `burst_fraction` of the cycle runs at `burst_factor` x the base rate
    (S3 incident-storm bursts), the rest at the base rate."""
    if base_rate_rps <= 0:
        raise ValueError("rate_rps must be positive")
    if burst_factor < 1.0:
        raise ValueError("burst_factor must be >= 1")
    times: list[float] = []
    t = start
    while len(times) < n:
        phase = (t - start) % cycle_s
        in_burst = phase < burst_fraction * cycle_s
        rate = base_rate_rps * (burst_factor if in_burst else 1.0)
        t += float(rng.exponential(scale=1.0 / rate))
        times.append(t)
    return np.asarray(times[:n])


def pattern_id_of(pattern: Pattern) -> PatternId:
    """Resolve the registry PatternId for a pattern instance."""
    from agentorch.patterns.registry import REGISTRY

    for pid, cls in REGISTRY.items():
        if isinstance(pattern, cls):
            return pid
    raise KeyError(f"pattern {type(pattern).__name__} not in REGISTRY")


def effective_concurrency(pattern_id: PatternId, concurrency: int,
                          cfg: Config) -> int:
    """Task 101: P3's decoupled bus consumers scale the service pool."""
    if pattern_id is PatternId.CHOREOGRAPHY:
        return concurrency * int(cfg.patterns.p3.consumer_scale)
    return concurrency


@dataclass
class RunStats:
    """Summary of one open-loop run."""

    n: int
    duration_s: float
    offered_rate_rps: float
    completed_rate_rps: float
    mean_latency_s: float
    mean_in_flight: float          # Little's law L = lambda * W
    max_queue_depth: int
    concurrency: int = 1           # effective server-pool size
    queue_depths: list[int] = field(default_factory=list)
    submit_ts: list[float] = field(default_factory=list)

    @property
    def utilization(self) -> float:
        """Little's-law pool utilization L / c."""
        return self.mean_in_flight / self.concurrency if self.concurrency else 0.0


def run_open_loop(pattern: Pattern, items: list[WorkItem], rate_rps: float,
                  concurrency: int, sink: TelemetrySink, rng: np.random.Generator,
                  mode: Mode = Mode.BASELINE, pattern_id: PatternId | None = None,
                  service_time_fn: Callable[[WorkItem], tuple[float, bool, FaultType | None]]
                  | None = None,
                  arrivals: np.ndarray | None = None) -> RunStats:
    """Run `items` open-loop through `pattern` at `rate_rps` with `concurrency` servers.

    Emits one LatencyRecord per item into `sink`. `service_time_fn` may
    override service-time generation (tests inject stalls with it);
    by default the pattern is executed and its accumulated boundary-call
    elapsed time is the service time. A pre-drawn `arrivals` schedule
    overrides the plain Poisson draw (S3 bursty arrivals).
    """
    if concurrency < 1:
        raise ValueError("concurrency must be >= 1")
    if pattern_id is None:
        pattern_id = pattern_id_of(pattern)
    n = len(items)
    if arrivals is None:
        arrivals = poisson_arrivals(n, rate_rps, rng)
    server_free = np.zeros(concurrency, dtype=float)  # earliest-free time per server
    completes: list[float] = []
    queue_depths: list[int] = []
    latencies: list[float] = []

    for i, item in enumerate(items):
        submit = float(arrivals[i])
        # Queue depth at submit: requests already submitted but not yet complete.
        depth = sum(1 for c in completes if c > submit)
        queue_depths.append(depth)

        srv = int(np.argmin(server_free))
        start = max(submit, float(server_free[srv]))

        # Expose the simulated request timeline and concurrency to the
        # pattern (task 101 contention term; task 104 outage windows).
        pattern.ctx.request_start_ts = start
        pattern.ctx.concurrent_in_flight = min(concurrency, depth + 1)

        if service_time_fn is not None:
            service_s, success, fault = service_time_fn(item)
            # If the fn ran the pattern, honour its nonblocking share
            # (human waits release the server); synthetic test fns leave
            # nonblocking_s at zero.
            blocking_s = service_s - float(pattern.ctx.nonblocking_s)
        else:
            result, service_s = pattern.run(item)
            # A request waiting on a human decision releases its server
            # (task 101): the server is busy only for the blocking part.
            blocking_s = service_s - float(pattern.ctx.nonblocking_s)
            success = result.ok
            fault = None
            if pattern.ctx.faults_seen:
                fault = pattern.ctx.faults_seen[0][1]
            if pattern.ctx.cost_model is not None:
                from agentorch.rig.costcapture import capture_request_cost
                capture_request_cost(pattern.ctx, sink, item.id,
                                     pattern_id, pattern.platform,
                                     scenario=item.scenario)

        complete = start + service_s
        server_free[srv] = start + blocking_s
        completes.append(complete)
        latencies.append(complete - submit)

        sink.record_latency(LatencyRecord(
            request_id=item.id,
            pattern=pattern_id,
            scenario=item.scenario,
            platform=pattern.platform,
            mode=mode,
            submit_ts=submit,
            complete_ts=complete,
            fault=fault,
            success=success,
        ))

    duration = max(completes) - float(arrivals[0]) if n else 0.0
    mean_w = float(np.mean(latencies)) if latencies else 0.0
    completed_rate = n / duration if duration > 0 else 0.0
    return RunStats(
        n=n,
        duration_s=duration,
        offered_rate_rps=rate_rps,
        completed_rate_rps=completed_rate,
        mean_latency_s=mean_w,
        mean_in_flight=completed_rate * mean_w,
        max_queue_depth=max(queue_depths) if queue_depths else 0,
        concurrency=concurrency,
        queue_depths=queue_depths,
        submit_ts=[float(a) for a in arrivals],
    )


@dataclass
class ConditionLoadReport:
    """Task 102: per-condition saturation accounting for the manifest.

    ``offered_utilization`` is the server-busy fraction
    rho = offered_rate x mean service time / effective concurrency —
    the stability criterion (rho < 1 means the queue cannot grow without
    bound). ``measured_little_l_per_server`` is Little's L / c, which
    also counts queued requests and so can transiently exceed rho.
    """

    mean_service_s: float
    saturation_rate_rps: float
    utilization_target: float
    offered_rate_rps: float
    offered_utilization: float
    measured_little_l_per_server: float
    effective_concurrency: int


def probe_service_rate(pattern_id: PatternId, platform: Platform,
                       scenario: ScenarioId, cfg: Config,
                       stream: str, n: int | None = None) -> float:
    """Single-replica service-time probe (task 102): run `n` items
    back-to-back (no queueing) and return the mean service time."""
    from agentorch.clients.context import CallContext
    from agentorch.patterns.registry import build
    from agentorch.scenarios import generate

    if n is None:
        n = int(cfg.load.saturation_probe_n)
    ctx = CallContext.build(cfg, sink=TelemetrySink(),
                            stream_prefix=f"{stream}:probe")
    pattern = build(pattern_id, platform, ctx, cfg)
    items = generate(scenario, n, cfg.get_rng(f"items:{stream}:probe"), cfg)
    total = 0.0
    for item in items:
        _, service_s = pattern.run(item)
        # Capacity is set by the time a request OCCUPIES a server; human
        # review waits (nonblocking) extend latency, not server busy time.
        total += service_s - float(pattern.ctx.nonblocking_s)
    return total / n if n else 0.0


def run_condition(pattern_id: PatternId, platform: Platform, scenario: ScenarioId,
                  n: int, cfg: Config, sink: TelemetrySink,
                  mode: Mode = Mode.BASELINE,
                  ctx: "object | None" = None
                  ) -> tuple[RunStats, ConditionLoadReport]:
    """Run one condition below measured saturation (task 102).

    1. Probe the condition's mean single-replica service time.
    2. saturation = effective_concurrency / mean service time.
    3. Offer ``load.utilization_target`` x saturation (open-loop).

    Returns (run stats, per-condition load report for the manifest).
    Task 103: the condition's full name seeds independent RNG streams.
    """
    from agentorch.clients.context import CallContext
    from agentorch.patterns.registry import build
    from agentorch.scenarios import generate

    stream = f"loadgen:{pattern_id.value}:{platform.value}:{scenario.value}:{mode.value}"
    if ctx is None:
        ctx = CallContext.build(cfg, sink=sink, stream_prefix=stream)
    pattern = build(pattern_id, platform, ctx, cfg)
    items = generate(scenario, n, cfg.get_rng(f"items:{stream}"), cfg)

    base_c = int(cfg.study.concurrency)
    eff_c = effective_concurrency(pattern_id, base_c, cfg)
    mean_service = probe_service_rate(pattern_id, platform, scenario, cfg, stream)
    # Saturation of the PROVISIONED pool; P3's elastic consumers add
    # headroom beyond it (burst absorption) rather than raising the
    # offered rate, so offered load is apples-to-apples across patterns.
    saturation = base_c / mean_service if mean_service > 0 else float("inf")
    target = float(cfg.load.utilization_target)
    rate = target * saturation

    rng = cfg.get_rng(stream)
    arrivals = None
    if scenario is ScenarioId.S3:
        # Bursty arrivals: scale the base rate so the TIME-AVERAGED rate
        # still equals utilization_target x saturation — bursts are a
        # transient overload that a stable system must absorb, not a
        # permanently oversaturated queue (task 102).
        s3 = cfg.scenarios.s3
        bf = float(s3.burst_factor)
        frac = float(s3.burst_fraction)
        base = rate / (1.0 + frac * (bf - 1.0))
        arrivals = bursty_arrivals(n, base, rng, burst_factor=bf,
                                   burst_fraction=frac,
                                   cycle_s=float(s3.get("burst_cycle_s", 60.0)))
    stats = run_open_loop(pattern, items, rate_rps=rate, concurrency=eff_c,
                          sink=sink, rng=rng, mode=mode, arrivals=arrivals)
    report = ConditionLoadReport(
        mean_service_s=mean_service,
        saturation_rate_rps=saturation,
        utilization_target=target,
        offered_rate_rps=rate,
        offered_utilization=rate * mean_service / eff_c,
        measured_little_l_per_server=stats.utilization,
        effective_concurrency=eff_c,
    )
    return stats, report
