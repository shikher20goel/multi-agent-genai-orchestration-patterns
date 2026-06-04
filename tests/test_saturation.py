"""Task 028: Little's law headroom check + saturation finder."""
import numpy as np

from agentorch.clients.context import CallContext
from agentorch.config import load_config
from agentorch.domain import WorkItem
from agentorch.patterns.registry import build
from agentorch.rig.loadgen import run_open_loop
from agentorch.rig.saturation import find_saturation, headroom
from agentorch.telemetry import TelemetrySink
from agentorch.types import PatternId, Platform, ScenarioId


def _run_fixed(rate: float, service_s: float, concurrency: int, n: int = 200):
    cfg = load_config()
    sink = TelemetrySink()
    pattern = build(PatternId.PIPELINE, Platform.BEDROCK,
                    CallContext.build(cfg, sink=sink), cfg)
    items = [WorkItem(id=f"w{i}", scenario=ScenarioId.S1) for i in range(n)]
    return run_open_loop(pattern, items, rate_rps=rate, concurrency=concurrency,
                         sink=sink, rng=cfg.get_rng(f"hr:{rate}:{service_s}"),
                         service_time_fn=lambda item: (service_s, True, None))


def test_littles_law_identity_holds() -> None:
    """L reported by the run equals lambda * W by construction; check the
    underlying quantities are consistent on a stable system."""
    stats = _run_fixed(rate=2.0, service_s=0.2, concurrency=4)
    assert np.isclose(stats.mean_in_flight,
                      stats.completed_rate_rps * stats.mean_latency_s)
    rep = headroom(stats, concurrency=4)
    # rho = lambda * s / c = 2 * 0.2 / 4 = 0.1: deep headroom.
    assert rep.sustainable
    assert rep.utilization < 0.5


def test_overloaded_system_flagged_unsustainable() -> None:
    """Offered 10 rps, capacity c/s = 2/1 = 2 rps: must be unsustainable."""
    stats = _run_fixed(rate=10.0, service_s=1.0, concurrency=2)
    rep = headroom(stats, concurrency=2)
    assert not rep.sustainable
    assert rep.utilization >= 1.0 or rep.completed_rate_rps < 0.9 * 10.0


def test_find_saturation_returns_max_sustainable_rate() -> None:
    cfg = load_config()
    rates = [0.5, 1.0, 2.0, 4.0, 8.0, 16.0]
    best, reports = find_saturation(PatternId.PIPELINE, Platform.BEDROCK,
                                    ScenarioId.S1, rates, cfg, n=80,
                                    concurrency=4)
    assert len(reports) == len(rates)
    assert best is not None
    # Monotone-ish: every rate below `best` that was swept is sustainable.
    by_rate = {r.offered_rate_rps: r for r in reports}
    assert by_rate[best].sustainable
    # Some swept rate above capacity must be unsustainable for the sweep
    # to have found a real saturation point.
    assert any(not r.sustainable for r in reports)
    assert all(not r.sustainable for r in reports if r.offered_rate_rps > best)


def test_find_saturation_deterministic() -> None:
    cfg = load_config()
    rates = [1.0, 4.0, 16.0]
    b1, r1 = find_saturation(PatternId.SUPERVISOR, Platform.AGENTFORCE,
                             ScenarioId.S1, rates, cfg, n=40, concurrency=4)
    b2, r2 = find_saturation(PatternId.SUPERVISOR, Platform.AGENTFORCE,
                             ScenarioId.S1, rates, cfg, n=40, concurrency=4)
    assert b1 == b2
    assert [x.completed_rate_rps for x in r1] == [x.completed_rate_rps for x in r2]
