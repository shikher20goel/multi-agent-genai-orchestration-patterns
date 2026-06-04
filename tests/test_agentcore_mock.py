"""Task 011: MockAgentCore services + Guardrails."""
import inspect

import pytest

from agentorch.clients.bedrock import BedrockClientError, MockAgentCore, MockGuardrails
from agentorch.clients.context import CallContext
from agentorch.config import load_config
from agentorch.types import Component, FaultType, Platform


@pytest.fixture()
def ctx() -> CallContext:
    return CallContext.build(load_config())


def test_invoke_agent_runtime_signature() -> None:
    sig = inspect.signature(MockAgentCore.invoke_agent_runtime)
    params = sig.parameters
    assert list(params) == [
        "self", "agentRuntimeArn", "runtimeSessionId", "payload", "qualifier",
    ]
    assert params["qualifier"].default == "DEFAULT"


def test_invoke_agent_runtime_shape(ctx: CallContext) -> None:
    core = MockAgentCore(ctx)
    resp = core.invoke_agent_runtime(
        agentRuntimeArn="arn:aws:bedrock-agentcore:::runtime/x",
        runtimeSessionId="rs-1", payload={"q": "hi"},
    )
    assert resp["runtimeSessionId"] == "rs-1"
    assert resp["qualifier"] == "DEFAULT"
    assert "usage" in resp


def test_gateway_adds_one_extra_hop(ctx: CallContext) -> None:
    """gateway_call = gateway hop + tool execution (one more sample than bare tool)."""
    core = MockAgentCore(ctx)
    before = ctx.elapsed_s
    core.gateway_call("search", {"q": "x"})
    gw_elapsed = ctx.elapsed_s - before
    # Direct tool call (no gateway) for comparison from a fresh context.
    ctx2 = CallContext.build(load_config())
    direct = ctx2.boundary_call(Platform.BEDROCK, "tool", Component.TOOL).elapsed_s
    assert gw_elapsed > direct  # extra hop adds latency
    assert ctx.service_calls == 2  # gateway hop + tool


def test_memory_roundtrip(ctx: CallContext) -> None:
    core = MockAgentCore(ctx)
    core.memory_put("k", {"v": 1})
    assert core.memory_get("k") == {"v": 1}
    assert core.memory_get("missing") is None


def test_identity_and_observability(ctx: CallContext) -> None:
    core = MockAgentCore(ctx)
    assert core.identity_check("user-1")["allowed"] is True
    core.observability_emit({"event": "step"})
    assert core.observability_events == [{"event": "step"}]


def test_memory_fault_raises(ctx: CallContext) -> None:
    ctx.fault_injector.arm(Component.MEMORY_STORE, FaultType.OUTAGE, 1.0)
    core = MockAgentCore(ctx)
    with pytest.raises(BedrockClientError):
        core.memory_put("k", 1)


def test_guardrails_shadow_logs_but_never_blocks(ctx: CallContext) -> None:
    g = MockGuardrails(ctx)
    res = g.apply("contains FORBIDDEN content", mode="shadow")
    assert res["action"] == "allowed"
    assert res["flagged"] is True
    assert len(g.shadow_log) == 1 and g.shadow_log[0]["action"] == "would_block"


def test_guardrails_block_mode_blocks(ctx: CallContext) -> None:
    g = MockGuardrails(ctx)
    assert g.apply("contains FORBIDDEN content", mode="block")["action"] == "blocked"
    assert g.apply("benign", mode="block")["action"] == "allowed"
