"""Task 010: MockBedrockAgentRuntime mirrors documented invoke_agent shape."""
import inspect

import pytest

from agentorch.clients.bedrock import BedrockClientError, MockBedrockAgentRuntime
from agentorch.clients.context import CallContext
from agentorch.config import load_config
from agentorch.types import Component, FaultType


@pytest.fixture()
def ctx() -> CallContext:
    return CallContext.build(load_config())


def test_invoke_agent_signature(ctx: CallContext) -> None:
    sig = inspect.signature(MockBedrockAgentRuntime.invoke_agent)
    assert list(sig.parameters) == [
        "self", "agentId", "agentAliasId", "sessionId", "inputText",
    ]


def test_invoke_agent_response_shape(ctx: CallContext) -> None:
    rt = MockBedrockAgentRuntime(ctx)
    resp = rt.invoke_agent(
        agentId="AG1", agentAliasId="ALIAS1", sessionId="s-1", inputText="hello",
    )
    assert set(resp) == {"completion", "sessionId", "usage"}
    assert resp["sessionId"] == "s-1"
    assert set(resp["usage"]) == {"inputTokens", "outputTokens"}
    assert resp["usage"]["inputTokens"] > 0 and resp["usage"]["outputTokens"] > 0


def test_invoke_agent_advances_virtual_clock(ctx: CallContext) -> None:
    rt = MockBedrockAgentRuntime(ctx)
    t0 = ctx.clock.now()
    rt.invoke_agent("AG1", "A1", "s", "hi")
    assert ctx.clock.now() > t0
    assert ctx.model_invocations == 1


def test_invoke_agent_fault_raises(ctx: CallContext) -> None:
    ctx.fault_injector.arm(Component.MODEL_BACKEND, FaultType.ERROR, 1.0)
    rt = MockBedrockAgentRuntime(ctx)
    with pytest.raises(BedrockClientError):
        rt.invoke_agent("AG1", "A1", "s", "hi")


def test_deterministic_usage_same_seed() -> None:
    cfg = load_config()
    r1 = MockBedrockAgentRuntime(CallContext.build(cfg)).invoke_agent("a", "b", "s", "x")
    r2 = MockBedrockAgentRuntime(CallContext.build(cfg)).invoke_agent("a", "b", "s", "x")
    assert r1 == r2
