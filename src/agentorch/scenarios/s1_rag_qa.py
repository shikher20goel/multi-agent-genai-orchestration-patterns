"""S1: throughput-oriented single-step retrieval-augmented QA (task 024)."""
from __future__ import annotations

import numpy as np

from agentorch.config import Config
from agentorch.domain import WorkItem
from agentorch.types import ScenarioId

_QUESTION_BANK = (
    "What is the refund policy for order {k}?",
    "Summarize account {k} renewal terms.",
    "Which plan covers feature {k}?",
    "What is the SLA for ticket class {k}?",
)


def generate_s1(n: int, rng: np.random.Generator, cfg: Config) -> list[WorkItem]:
    passages = int(cfg.scenarios.s1.retrieval_passages)
    items: list[WorkItem] = []
    for i in range(n):
        template = _QUESTION_BANK[int(rng.integers(0, len(_QUESTION_BANK)))]
        items.append(WorkItem(
            id=f"s1-{i}",
            scenario=ScenarioId.S1,
            payload={
                "task": template.format(k=int(rng.integers(1000, 9999))),
                "retrieval_passages": passages,
                "steps": 1,  # single-step, throughput-oriented
            },
        ))
    return items
