"""S3: bursty incident triage; configurable burst factor; some items need
human routing (task 026).

Arrival weights: a `burst_fraction` of the window carries `burst_factor`x
the base arrival intensity. Each item carries an `arrival_weight` the load
generator uses to thin/thicken the Poisson process, plus a confidence so a
`human_routing_fraction` of items fall below the HITL threshold.
"""
from __future__ import annotations

import numpy as np

from agentorch.config import Config
from agentorch.domain import WorkItem
from agentorch.types import ScenarioId

_SEVERITIES = ("sev1", "sev2", "sev3")


def generate_s3(n: int, rng: np.random.Generator, cfg: Config,
                burst_factor: float | None = None) -> list[WorkItem]:
    s3 = cfg.scenarios.s3
    bf = float(burst_factor if burst_factor is not None else s3.burst_factor)
    if bf < 1.0:
        raise ValueError("burst_factor must be >= 1")
    burst_fraction = float(s3.burst_fraction)
    human_fraction = float(s3.human_routing_fraction)
    threshold = float(cfg.patterns.p6.confidence_threshold)
    items: list[WorkItem] = []
    for i in range(n):
        in_burst = bool(rng.random() < burst_fraction)
        needs_human = bool(rng.random() < human_fraction)
        confidence = (float(rng.uniform(0.05, threshold - 0.05)) if needs_human
                      else float(rng.uniform(threshold + 0.05, 0.99)))
        items.append(WorkItem(
            id=f"s3-{i}",
            scenario=ScenarioId.S3,
            payload={
                "task": f"triage incident {i}",
                "steps": 2,  # triage = classify + act (two model steps)
                "severity": _SEVERITIES[int(rng.integers(0, len(_SEVERITIES)))],
                "arrival_weight": bf if in_burst else 1.0,
                "in_burst": in_burst,
                "confidence": confidence,
                "needs_human": needs_human,
                "burst_factor": bf,
            },
        ))
    return items
