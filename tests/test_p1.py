"""Task 016: P1 supervisor-collaborator on both platforms (S1)."""
import pytest

from agentorch.clients.context import CallContext
from agentorch.config import load_config
from agentorch.domain import WorkItem
from agentorch.patterns.base import validate_meta
from agentorch.patterns.p1_supervisor import SupervisorPattern
from agentorch.types import Component, FaultType, Platform, ScenarioId


@pytest.mark.parametrize("platform", [Platform.BEDROCK, Platform.AGENTFORCE])
def test_p1_runs_on_platform(platform: Platform) -> None:
    cfg = load_config()
    p = SupervisorPattern(platform, CallContext.build(cfg), cfg)
    item = WorkItem(id="w1", scenario=ScenarioId.S1, payload={"task": "answer Q"})
    result, service_time = p.run(item)
    assert result.ok, result.error
    assert result.payload["n_collaborators"] == cfg.patterns.p1.n_collaborators
    assert service_time > 0


def test_p1_meta_valid() -> None:
    validate_meta(SupervisorPattern.meta())


def test_p1_model_backend_fault_yields_error_result() -> None:
    cfg = load_config()
    ctx = CallContext.build(cfg)
    ctx.fault_injector.arm(Component.MODEL_BACKEND, FaultType.ERROR, 1.0)
    p = SupervisorPattern(Platform.BEDROCK, ctx, cfg)
    result, _ = p.run(WorkItem(id="w1", scenario=ScenarioId.S1))
    assert result.status == "error"
