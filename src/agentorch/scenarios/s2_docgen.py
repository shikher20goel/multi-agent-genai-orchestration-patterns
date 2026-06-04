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
    items: list[WorkItem] = []
    for i in range(n):
        n_steps = int(rng.integers(lo, hi + 1))
        stages = list(_STAGE_POOL[:n_steps])
        items.append(WorkItem(
            id=f"s2-{i}",
            scenario=ScenarioId.S2,
            payload={
                "task": f"generate document {i}",
                "stages": stages,
                "steps": n_steps,
            },
        ))
    return items
