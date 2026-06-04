"""Task 027: open-loop load generator (Algorithm 1).

Key property: open-loop arrivals continue during a server stall — the
submit cadence comes from the Poisson schedule (not from completions),
queue depth grows, and measured latency includes the queueing delay
(coordinated-omission correct).
"""
import numpy as np
import pytest

from agentorch.clients.context import CallContext
from agentorch.config import load_config
from agentorch.domain import WorkItem
from agentorch.patterns.registry import build
from agentorch.rig.loadgen import poisson_arrivals, run_condition, run_open_loop
from agentorch.telemetry import TelemetrySink
from agentorch.types import Mode, PatternId, Platform, ScenarioId


def _items(n: int) -> list[WorkItem]:
    return [WorkItem(id=f"w{i}", scenario=ScenarioId.S1, payload={"task": f"t{i}"})
            for i in range(n)]


def test_poisson_arrivals_deterministic_and_rate() -> None:
    cfg = load_config()
    a1 = poisson_arrivals(500, 2.0, cfg.get_rng("arrivals"))
    a2 = poisson_arrivals(500, 2.0, cfg.get_rng("arrivals"))
    assert np.array_equal(a1, a2)
    assert np.all(np.diff(a1) > 0)
    # Mean inter-arrival ~ 1/rate.
    assert abs(np.mean(np.diff(a1)) - 0.5) < 0.1


def test_open_loop_emits_latency_records() -> None:
    cfg = load_config()
    sink = TelemetrySink()
    pattern = build(PatternId.PIPELINE, Platform.BEDROCK,
                    CallContext.build(cfg, sink=sink), cfg)
    items = _items(30)
    stats = run_open_loop(pattern, items, rate_rps=2.0, concurrency=4,
                          sink=sink, rng=cfg.get_rng("t"))
    assert len(sink.latency) == 30
    assert stats.n == 30
    for rec in sink.latency:
        assert rec.complete_ts > rec.submit_ts
        assert rec.pattern is PatternId.PIPELINE
        assert rec.mode is Mode.BASELINE


def test_submit_ts_from_arrival_schedule_not_completions() -> None:
    """submit_ts must equal the pre-drawn Poisson schedule exactly."""
    cfg = load_config()
    sink = TelemetrySink()
    pattern = build(PatternId.SUPERVISOR, Platform.AGENTFORCE,
                    CallContext.build(cfg, sink=sink), cfg)
    items = _items(40)
    expected = poisson_arrivals(40, 3.0, cfg.get_rng("sched"))
    run_open_loop(pattern, items, rate_rps=3.0, concurrency=2,
                  sink=sink, rng=cfg.get_rng("sched"))
    got = np.array([r.submit_ts for r in sink.latency])
    assert np.allclose(got, expected)


def test_issuing_continues_during_injected_stall() -> None:
    """A long stall on one request must not pause arrivals: queue depth
    grows while the submit cadence is unchanged versus a no-stall run."""
    cfg = load_config()

    def make_service_fn(stall_at: int, stall_s: float):
        def fn(item: WorkItem):
            idx = int(item.id[1:])
            if idx == stall_at:
                return stall_s, True, None
            return 0.05, True, None
        return fn

    def run_with(service_fn):
        sink = TelemetrySink()
        pattern = build(PatternId.PIPELINE, Platform.BEDROCK,
                        CallContext.build(cfg, sink=sink), cfg)
        stats = run_open_loop(pattern, _items(60), rate_rps=5.0, concurrency=1,
                              sink=sink, rng=cfg.get_rng("stall"),
                              service_time_fn=service_fn)
        return stats, sink

    stalled, sink_stall = run_with(make_service_fn(stall_at=5, stall_s=30.0))
    normal, sink_norm = run_with(make_service_fn(stall_at=5, stall_s=0.05))

    # Submit cadence identical: same seed -> same arrival schedule.
    assert stalled.submit_ts == normal.submit_ts
    # Queue depth grows during the stall.
    assert stalled.max_queue_depth > normal.max_queue_depth
    assert stalled.max_queue_depth >= 10
    # Requests submitted during the stall pay queueing delay (no omission).
    lat_stall = [r.complete_ts - r.submit_ts for r in sink_stall.latency]
    lat_norm = [r.complete_ts - r.submit_ts for r in sink_norm.latency]
    assert max(lat_stall) > 10 * max(lat_norm)


def test_concurrency_pool_limits_parallelism() -> None:
    """With c=2 and fixed 1s service at high rate, throughput caps at ~2 rps."""
    cfg = load_config()
    sink = TelemetrySink()
    pattern = build(PatternId.PIPELINE, Platform.BEDROCK,
                    CallContext.build(cfg, sink=sink), cfg)

    def fixed(item: WorkItem):
        return 1.0, True, None

    stats = run_open_loop(pattern, _items(100), rate_rps=50.0, concurrency=2,
                          sink=sink, rng=cfg.get_rng("pool"),
                          service_time_fn=fixed)
    assert stats.completed_rate_rps < 2.5
    assert stats.completed_rate_rps > 1.5


def test_run_condition_wrapper() -> None:
    cfg = load_config()
    sink = TelemetrySink()
    stats, load = run_condition(PatternId.GATEWAY, Platform.BEDROCK,
                                ScenarioId.S1, n=10, cfg=cfg, sink=sink)
    assert stats.n == 10
    assert len(sink.latency) == 10
    # Task 102: the offered rate sits below measured saturation.
    assert load.offered_rate_rps < load.saturation_rate_rps
    assert load.offered_utilization < 1.0
    assert load.offered_rate_rps == pytest.approx(
        load.utilization_target * load.saturation_rate_rps)

def test_conditions_use_independent_latency_streams() -> None:
    """Task 103: two conditions' per-request latencies must differ —
    the shared 'latency' stream coupling is gone (SAP Option A)."""
    cfg = load_config()
    s1, s2 = TelemetrySink(), TelemetrySink()
    run_condition(PatternId.GATEWAY, Platform.BEDROCK, ScenarioId.S1,
                  n=20, cfg=cfg, sink=s1)
    run_condition(PatternId.GATEWAY, Platform.BEDROCK, ScenarioId.S2,
                  n=20, cfg=cfg, sink=s2)
    lat1 = [r.latency_ms for r in s1.latency]
    lat2 = [r.latency_ms for r in s2.latency]
    assert lat1 != lat2

