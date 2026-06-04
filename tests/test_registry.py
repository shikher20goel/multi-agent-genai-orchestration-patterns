"""Task 023: registry covers all 7 patterns; uniform smoke on both platforms."""
import pytest

from agentorch.clients.context import CallContext
from agentorch.config import load_config
from agentorch.domain import WorkItem
from agentorch.patterns.base import validate_meta
from agentorch.patterns.registry import REGISTRY, build
from agentorch.types import PatternId, Platform, ScenarioId


def test_registry_covers_all_seven() -> None:
    assert set(REGISTRY) == set(PatternId)


@pytest.mark.parametrize("pattern_id", list(PatternId))
@pytest.mark.parametrize("platform", [Platform.BEDROCK, Platform.AGENTFORCE])
def test_uniform_smoke(pattern_id: PatternId, platform: Platform) -> None:
    cfg = load_config()
    pattern = build(pattern_id, platform, CallContext.build(cfg), cfg)
    validate_meta(type(pattern).meta())
    result, service_time = pattern.run(
        WorkItem(id="smoke", scenario=ScenarioId.S1, payload={"task": "smoke"}))
    assert result.ok, f"{pattern_id} on {platform}: {result.error}"
    assert service_time > 0


def test_build_unknown_raises() -> None:
    cfg = load_config()
    with pytest.raises(KeyError):
        build("P99", Platform.BEDROCK, CallContext.build(cfg), cfg)  # type: ignore[arg-type]
