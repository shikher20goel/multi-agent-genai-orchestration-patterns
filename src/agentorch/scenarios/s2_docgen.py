"""S2: long-horizon multi-step document generation, 4-8 sequential steps (task 025)."""
from __future__ import annotations

import numpy as np

from agentorch.config import Config
from agentorch.domain import WorkItem
from agentorch.types import ScenarioId

_STAGE_POOL = ("outline", "research", "draft_intro", "draft_body",
               "draft_conclusion", "citations", "review", "polish")


def generate_s2(n: int, rng: np.random.Generator, cfg: Config) -> list[WorkItem]:
    lo = int(cfg.scenarios.s2.min_steps)
    hi = int(cfg.scenarios.s2.max_steps)
    review_fraction = float(cfg.scenarios.s2.get("hitl_review_fraction", 0.0))
    threshold = float(cfg.patterns.p6.confidence_threshold)
    items: list[WorkItem] = []
    for i in range(n):
        n_steps = int(rng.integers(lo, hi + 1))
        stages = list(_STAGE_POOL[:n_steps])
        needs_review = bool(rng.random() < review_fraction)
        confidence = (float(rng.uniform(0.05, threshold - 0.05)) if needs_review
                      else float(rng.uniform(threshold + 0.05, 0.99)))
        items.append(WorkItem(
            id=f"s2-{i}",
            scenario=ScenarioId.S2,
            payload={
                "task": f"generate document {i}",
                "stages": stages,
                "steps": n_steps,
                "confidence": confidence,  # drives the P6 review gate
            },
        ))
    return items
