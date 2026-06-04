"""Task 012: MockAgentforceClient topics/actions/Agent Script."""
import pytest

from agentorch.clients.agentforce import AgentforceClientError, MockAgentforceClient
from agentorch.clients.context import CallContext
from agentorch.config import load_config
from agentorch.types import Component, FaultType


@pytest.fixture()
def client() -> MockAgentforceClient:
    return MockAgentforceClient(CallContext.build(load_config()))


def test_start_session(client: MockAgentforceClient) -> None:
    s1 = client.start_session(user_id="u1")
    s2 = client.start_session(user_id="u2")
    assert s1 != s2 and s1.startswith("af-session-")


def test_topic_routes_to_actions_pass_through(client: MockAgentforceClient) -> None:
    client.register_action("lookup", lambda a: {"record": "acct-9"})
    client.register_action("summarize", lambda a: {"summary": f"about {a.get('record')}"})
    client.register_topic("account_help", ["lookup", "summarize"])
    out = client.send("account_help", {"q": "tell me about my account"})
    assert out["topic"] == "account_help"
    # pass-through chaining: second action saw the first action's output
    assert out["result"]["summary"] == "about acct-9"
    assert len(out["trace"]) == 2


def test_unregistered_topic_raises(client: MockAgentforceClient) -> None:
    with pytest.raises(KeyError):
        client.send("nope", {})


def test_agent_script_sequential_chaining(client: MockAgentforceClient) -> None:
    client.register_action("step1", lambda a: {"x": 1})
    client.register_action("step2", lambda a: {"y": a["x"] + 1})
    client.register_action("step3", lambda a: {"z": a["y"] + 1})
    results = client.run_agent_script([
        {"action": "step1"}, {"action": "step2"}, {"action": "step3"},
    ])
    assert results[-1]["z"] == 3


def test_action_fault_raises() -> None:
    ctx = CallContext.build(load_config())
    ctx.fault_injector.arm(Component.TOOL, FaultType.ERROR, 1.0)
    client = MockAgentforceClient(ctx)
    client.register_action("a")
    client.register_topic("t", ["a"])
    with pytest.raises(AgentforceClientError):
        client.send("t", {})


def test_send_accounts_model_invocation() -> None:
    ctx = CallContext.build(load_config())
    client = MockAgentforceClient(ctx)
    client.register_action("a")
    client.register_topic("t", ["a"])
    client.send("t", {})
    assert ctx.model_invocations == 1
    assert ctx.service_calls == 1
    assert ctx.clock.now() > 0
