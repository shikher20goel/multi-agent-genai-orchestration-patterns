"""Task 020: P5 tool-routed gateway; bulkhead contains a tool fault."""
import pytest

from agentorch.clients.context import CallContext
from agentorch.config import load_config
from agentorch.domain import WorkItem
from agentorch.patterns.base import validate_meta
from agentorch.patterns.p5_gateway import GatewayPattern
from agentorch.types import Component, FaultType, Platform, ScenarioId


@pytest.mark.parametrize("platform", [Platform.BEDROCK, Platform.AGENTFORCE])
def test_p5_runs_on_platform(platform: Platform) -> None:
    cfg = load_config()
    p = GatewayPattern(platform, CallContext.build(cfg), cfg)
    result, service_time = p.run(WorkItem(id="w1", scenario=ScenarioId.S1))
    assert result.ok, result.error
    assert sorted(result.payload["tools_ok"]) == sorted(cfg.patterns.p5.tools)
    assert service_time > 0


def test_p5_meta_valid() -> None:
    validate_meta(GatewayPattern.meta())


@pytest.mark.parametrize("platform", [Platform.BEDROCK, Platform.AGENTFORCE])
def test_p5_bulkhead_contains_tool_fault(platform: Platform) -> None:
    """A faulted tool fails, but other tools complete and the request succeeds."""
    cfg = load_config()
    ctx = CallContext.build(cfg)
    # Intermittent tool fault: some tool calls fail, the rest proceed —
    # the bulkhead must contain failures to the failing calls only.
    ctx.fault_injector.arm(Component.TOOL, FaultType.ERROR, 0.5)
    p = GatewayPattern(platform, ctx, cfg)
    saw_partial = False
    for i in range(20):
        result, _ = p.run(WorkItem(id=f"w{i}", scenario=ScenarioId.S1))
        if result.payload and result.payload.get("tools_failed") and result.ok:
            # at least one tool failed AND the request still returned ok
            assert result.payload["tools_ok"], "other tools must be unaffected"
            saw_partial = True
    assert saw_partial, "expected at least one contained partial failure"
