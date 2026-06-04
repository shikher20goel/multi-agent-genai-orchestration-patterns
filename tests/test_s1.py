"""Task 024: S1 RAG QA workload (throughput-oriented, single-step)."""
from agentorch.config import load_config
from agentorch.scenarios import generate
from agentorch.types import ScenarioId


def test_s1_generates_n_items() -> None:
    cfg = load_config()
    items = generate(ScenarioId.S1, 25, cfg.get_rng("s1"), cfg)
    assert len(items) == 25
    assert all(i.scenario is ScenarioId.S1 for i in items)


def test_s1_single_step_with_retrieval() -> None:
    cfg = load_config()
    items = generate(ScenarioId.S1, 5, cfg.get_rng("s1"), cfg)
    for item in items:
        assert item.payload["steps"] == 1
        assert item.payload["retrieval_passages"] == cfg.scenarios.s1.retrieval_passages
        assert item.payload["task"]


def test_s1_deterministic() -> None:
    cfg = load_config()
    a = generate(ScenarioId.S1, 10, cfg.get_rng("s1"), cfg)
    b = generate(ScenarioId.S1, 10, cfg.get_rng("s1"), cfg)
    assert [i.payload for i in a] == [i.payload for i in b]
