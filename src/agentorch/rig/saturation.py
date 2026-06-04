"""Little's law headroom check and saturation finder (task 028).

Little's law: L = lambda * W (mean in-flight = throughput x mean
latency). A run is *sustainable* when the system keeps up with the
offered rate: completed throughput ~ offered rate and utilization of
the concurrency-c pool stays below 1. ``find_saturation`` sweeps offered
rates and returns the highest sustainable one.
"""
from __future__ import annotations

from dataclasses import dataclass

from agentorch.config import Config
from agentorch.rig.loadgen import RunStats, run_open_loop
from agentorch.telemetry import TelemetrySink
from agentorch.types import PatternId, Platform, ScenarioId


@dataclass
class HeadroomReport:
    """Little's law accounting for one run."""

    offered_rate_rps: float
    completed_rate_rps: float
    mean_latency_s: float
    little_l: float          # L = lambda_completed * W
    utilization: float       # little_l / concurrency
    sustainable: bool


def headroom(stats: RunStats, concurrency: int,
             utilization_limit: float = 1.0,
             rate_tolerance: float = 0.9) -> HeadroomReport:
    """Classify a run as sustainable via Little's law.

    Sustainable iff (a) mean in-flight per server (utilization) is below
    `utilization_limit` and (b) completed throughput reached at least
    `rate_tolerance` of the offered rate.
    """
    util = stats.mean_in_flight / concurrency if concurrency > 0 else float("inf")
    keeps_up = stats.completed_rate_rps >= rate_tolerance * stats.offered_rate_rps
    return HeadroomReport(
        offered_rate_rps=stats.offered_rate_rps,
        completed_rate_rps=stats.completed_rate_rps,
        mean_latency_s=stats.mean_latency_s,
        little_l=stats.mean_in_flight,
        utilization=util,
        sustainable=bool(util < utilization_limit and keeps_up),
    )


def find_saturation(pattern_id: PatternId, platform: Platform, scenario: ScenarioId,
                    rates: list[float], cfg: Config, n: int | None = None,
                    concurrency: int | None = None) -> tuple[float | None,
                                                             list[HeadroomReport]]:
    """Sweep offered rates; return (max sustainable rate, all reports).

    Returns None for the rate if no swept rate is sustainable.
    """
    from agentorch.clients.context import CallContext
    from agentorch.patterns.registry import build
    from agentorch.scenarios import generate

    if n is None:
        n = int(cfg.study.n_items)
    if concurrency is None:
        concurrency = int(cfg.study.concurrency)

    reports: list[HeadroomReport] = []
    best: float | None = None
    for rate in sorted(rates):
        sink = TelemetrySink()
        ctx = CallContext.build(cfg, sink=sink)
        pattern = build(pattern_id, platform, ctx, cfg)
        stream = f"sat:{pattern_id.value}:{platform.value}:{scenario.value}:{rate}"
        items = generate(scenario, n, cfg.get_rng(f"items:{stream}"), cfg)
        stats = run_open_loop(pattern, items, rate_rps=rate,
                              concurrency=concurrency, sink=sink,
                              rng=cfg.get_rng(stream))
        report = headroom(stats, concurrency)
        reports.append(report)
        if report.sustainable:
            best = rate
    return best, reports
