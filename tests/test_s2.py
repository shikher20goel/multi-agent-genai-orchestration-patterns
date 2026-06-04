"""Task 025: S2 long-horizon doc-gen workload (4-8 sequential steps)."""
from agentorch.clients.context import CallContext
from agentorch.config import load_config
from agentorch.patterns.p2_pipeline import PipelinePattern
from agentorch.scenarios import generate
from agentorch.types import Platform, ScenarioId


def test_s2_step_counts_in_range() -> None:
    cfg = load_config()
    items = generate(ScenarioId.S2, 50, cfg.get_rng("s2"), cfg)
    steps = [i.payload["steps"] for i in items]
    assert all(4 <= s <= 8 for s in steps)
    assert len(set(steps)) > 1  # varied horizons
    for item in items:
        assert len(item.payload["stages"]) == item.payload["steps"]


def test_s2_deterministic() -> None:
    cfg = load_config()
    a = generate(ScenarioId.S2, 20, cfg.get_rng("s2"), cfg)
    b = generate(ScenarioId.S2, 20, cfg.get_rng("s2"), cfg)
    assert [i.payload for i in a] == [i.payload for i in b]


def test_s2_runs_through_pipeline_pattern() -> None:
    cfg = load_config()
    item = generate(ScenarioId.S2, 1, cfg.get_rng("s2"), cfg)[0]
    p = PipelinePattern(Platform.BEDROCK, CallContext.build(cfg), cfg)
    result, _ = p.run(item)
    assert result.ok and result.payload["n_steps"] == item.payload["steps"]
