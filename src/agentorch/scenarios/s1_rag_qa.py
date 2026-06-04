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
    review_fraction = float(cfg.scenarios.s1.get("hitl_review_fraction", 0.0))
    threshold = float(cfg.patterns.p6.confidence_threshold)
    items: list[WorkItem] = []
    for i in range(n):
        template = _QUESTION_BANK[int(rng.integers(0, len(_QUESTION_BANK)))]
        needs_review = bool(rng.random() < review_fraction)
        confidence = (float(rng.uniform(0.05, threshold - 0.05)) if needs_review
                      else float(rng.uniform(threshold + 0.05, 0.99)))
        items.append(WorkItem(
            id=f"s1-{i}",
            scenario=ScenarioId.S1,
            payload={
                "task": template.format(k=int(rng.integers(1000, 9999))),
                "retrieval_passages": passages,
                "steps": 1,  # single-step, throughput-oriented
                "confidence": confidence,  # drives the P6 review gate
            },
        ))
    return items
