"""Open-loop load generator (Algorithm 1, task 027).

Arrivals follow a Poisson process at ``rate_rps``: the FULL arrival
schedule is drawn up front, and every request's ``submit_ts`` comes
from that schedule — never from the previous completion — so the
generator keeps issuing during stalls and measured latency includes
queueing delay (coordinated-omission correct).

Service is a concurrency-``c`` pool: request i starts at
``max(submit_ts_i, earliest_free_server)`` and completes at
``start + service_time``. Service times come from running the work
item through the pattern (virtual clock; nothing sleeps).
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


def pattern_id_of(pattern: Pattern) -> PatternId:
    """Resolve the registry PatternId for a pattern instance."""
    from agentorch.patterns.registry import REGISTRY

    for pid, cls in REGISTRY.items():
        if isinstance(pattern, cls):
            return pid
    raise KeyError(f"pattern {type(pattern).__name__} not in REGISTRY")


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
    queue_depths: list[int] = field(default_factory=list)
    submit_ts: list[float] = field(default_factory=list)


def run_open_loop(pattern: Pattern, items: list[WorkItem], rate_rps: float,
                  concurrency: int, sink: TelemetrySink, rng: np.random.Generator,
                  mode: Mode = Mode.BASELINE, pattern_id: PatternId | None = None,
                  service_time_fn: Callable[[WorkItem], tuple[float, bool, FaultType | None]]
                  | None = None) -> RunStats:
    """Run `items` open-loop through `pattern` at `rate_rps` with `concurrency` servers.

    Emits one LatencyRecord per item into `sink`. `service_time_fn` may
    override service-time generation (tests inject stalls with it);
    by default the pattern is executed and its accumulated boundary-call
    elapsed time is the service time.
    """
    if concurrency < 1:
        raise ValueError("concurrency must be >= 1")
    if pattern_id is None:
        pattern_id = pattern_id_of(pattern)
    n = len(items)
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

        if service_time_fn is not None:
            service_s, success, fault = service_time_fn(item)
        else:
            result, service_s = pattern.run(item)
            success = result.ok
            fault = None
            if pattern.ctx.faults_seen:
                fault = pattern.ctx.faults_seen[0][1]
            if pattern.ctx.cost_model is not None:
                from agentorch.rig.costcapture import capture_request_cost
                capture_request_cost(pattern.ctx, sink, item.id,
                                     pattern_id, pattern.platform)

        srv = int(np.argmin(server_free))
        start = max(submit, float(server_free[srv]))
        complete = start + service_s
        server_free[srv] = complete
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
        queue_depths=queue_depths,
        submit_ts=[float(a) for a in arrivals],
    )


def run_condition(pattern_id: PatternId, platform: Platform, scenario: ScenarioId,
                  n: int, cfg: Config, sink: TelemetrySink,
                  mode: Mode = Mode.BASELINE,
                  ctx: "object | None" = None) -> RunStats:
    """Convenience wrapper: build the pattern + items and run one condition."""
    from agentorch.clients.context import CallContext
    from agentorch.patterns.registry import build
    from agentorch.scenarios import generate

    if ctx is None:
        ctx = CallContext.build(cfg, sink=sink)
    pattern = build(pattern_id, platform, ctx, cfg)
    stream = f"loadgen:{pattern_id.value}:{platform.value}:{scenario.value}:{mode.value}"
    items = generate(scenario, n, cfg.get_rng(f"items:{stream}"), cfg)
    return run_open_loop(
        pattern, items,
        rate_rps=float(cfg.study.rate_rps),
        concurrency=int(cfg.study.concurrency),
        sink=sink,
        rng=cfg.get_rng(stream),
        mode=mode,
    )
