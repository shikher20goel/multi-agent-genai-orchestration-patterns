"""Task 018: P3 event-driven choreography on both platforms."""
import pytest

from agentorch.clients.context import CallContext
from agentorch.config import load_config
from agentorch.domain import WorkItem
from agentorch.patterns.base import validate_meta
from agentorch.patterns.p3_choreography import EVENT_CHAIN, ChoreographyPattern
from agentorch.types import Platform, ScenarioId


@pytest.mark.parametrize("platform", [Platform.BEDROCK, Platform.AGENTFORCE])
def test_p3_runs_on_platform(platform: Platform) -> None:
    cfg = load_config()
    p = ChoreographyPattern(platform, CallContext.build(cfg), cfg)
    result, service_time = p.run(WorkItem(id="w1", scenario=ScenarioId.S3))
    assert result.ok, result.error
    assert result.payload["hops"] == len(EVENT_CHAIN)
    assert service_time > 0


def test_p3_meta_valid() -> None:
    validate_meta(ChoreographyPattern.meta())


def test_p3_agentforce_chain_order() -> None:
    cfg = load_config()
    p = ChoreographyPattern(Platform.AGENTFORCE, CallContext.build(cfg), cfg)
    result, _ = p.run(WorkItem(id="w1", scenario=ScenarioId.S3))
    assert result.payload["events"] == list(EVENT_CHAIN)
