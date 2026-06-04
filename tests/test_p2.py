"""Task 017: P2 sequential pipeline on both platforms."""
import pytest

from agentorch.clients.context import CallContext
from agentorch.config import load_config
from agentorch.domain import WorkItem
from agentorch.patterns.base import validate_meta
from agentorch.patterns.p2_pipeline import PipelinePattern
from agentorch.types import Platform, ScenarioId


@pytest.mark.parametrize("platform", [Platform.BEDROCK, Platform.AGENTFORCE])
def test_p2_runs_on_platform(platform: Platform) -> None:
    cfg = load_config()
    p = PipelinePattern(platform, CallContext.build(cfg), cfg)
    item = WorkItem(id="w1", scenario=ScenarioId.S2, payload={"task": "write doc"})
    result, service_time = p.run(item)
    assert result.ok, result.error
    assert result.payload["n_steps"] == 3
    assert service_time > 0


def test_p2_meta_valid() -> None:
    validate_meta(PipelinePattern.meta())


def test_p2_custom_stage_list() -> None:
    cfg = load_config()
    p = PipelinePattern(Platform.BEDROCK, CallContext.build(cfg), cfg)
    item = WorkItem(id="w1", scenario=ScenarioId.S2,
                    payload={"stages": ["a", "b", "c", "d", "e"]})
    result, _ = p.run(item)
    assert result.payload["n_steps"] == 5
