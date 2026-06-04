"""Workload scenarios S1 (RAG QA), S2 (doc-gen), S3 (incident triage)."""
from __future__ import annotations

import numpy as np

from agentorch.config import Config
from agentorch.domain import WorkItem
from agentorch.scenarios.s1_rag_qa import generate_s1
from agentorch.scenarios.s2_docgen import generate_s2
from agentorch.scenarios.s3_triage import generate_s3
from agentorch.types import ScenarioId

_GENERATORS = {
    ScenarioId.S1: generate_s1,
    ScenarioId.S2: generate_s2,
    ScenarioId.S3: generate_s3,
}


def generate(scenario_id: ScenarioId, n: int, rng: np.random.Generator,
             cfg: Config) -> list[WorkItem]:
    """Generate `n` work items for the scenario, deterministically from `rng`."""
    try:
        fn = _GENERATORS[scenario_id]
    except KeyError as exc:
        raise KeyError(f"unknown scenario {scenario_id!r}") from exc
    return fn(n, rng, cfg)
