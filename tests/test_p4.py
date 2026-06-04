"""Task 019: P4 shared-memory blackboard on both platforms."""
import pytest

from agentorch.clients.context import CallContext
from agentorch.config import load_config
from agentorch.domain import WorkItem
from agentorch.patterns.base import validate_meta
from agentorch.patterns.p4_blackboard import BlackboardPattern
from agentorch.types import Component, FaultType, Platform, ScenarioId


@pytest.mark.parametrize("platform", [Platform.BEDROCK, Platform.AGENTFORCE])
def test_p4_runs_on_platform(platform: Platform) -> None:
    cfg = load_config()
    p = BlackboardPattern(platform, CallContext.build(cfg), cfg)
    result, service_time = p.run(WorkItem(id="w1", scenario=ScenarioId.S1))
    assert result.ok, result.error
    assert result.payload["contributions"] == cfg.patterns.p4.n_specialists
    assert service_time > 0


def test_p4_meta_valid() -> None:
    validate_meta(BlackboardPattern.meta())


def test_p4_memory_outage_yields_error() -> None:
    cfg = load_config()
    ctx = CallContext.build(cfg)
    ctx.fault_injector.arm(Component.MEMORY_STORE, FaultType.OUTAGE, 1.0)
    p = BlackboardPattern(Platform.BEDROCK, ctx, cfg)
    result, _ = p.run(WorkItem(id="w1", scenario=ScenarioId.S1))
    assert result.status == "error"
