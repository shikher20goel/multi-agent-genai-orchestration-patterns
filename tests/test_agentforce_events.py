"""Task 013: platform events + Omni-Channel handoff with fallback."""
import pytest

from agentorch.clients.agentforce import (
    AgentforceClientError,
    MockAgentforceClient,
    OmniChannel,
)
from agentorch.clients.context import CallContext
from agentorch.config import load_config
from agentorch.domain import WorkItem
from agentorch.types import Component, FaultType, ScenarioId


@pytest.fixture()
def ctx() -> CallContext:
    return CallContext.build(load_config())


def test_publish_event_delivers_to_subscribers(ctx: CallContext) -> None:
    client = MockAgentforceClient(ctx)
    seen: list[dict] = []
    client.subscribe("Case_Escalated__e", seen.append)
    client.subscribe("Case_Escalated__e", seen.append)
    n = client.publish_event("Case_Escalated__e", {"case": "C-1"})
    assert n == 2 and seen == [{"case": "C-1"}, {"case": "C-1"}]


def test_publish_event_no_subscribers(ctx: CallContext) -> None:
    client = MockAgentforceClient(ctx)
    assert client.publish_event("Quiet__e", {}) == 0


def test_event_bus_fault_raises(ctx: CallContext) -> None:
    ctx.fault_injector.arm(Component.EVENT_BUS, FaultType.OUTAGE, 1.0)
    client = MockAgentforceClient(ctx)
    with pytest.raises(AgentforceClientError):
        client.publish_event("X__e", {})


def test_escalation_routes_to_human_queue(ctx: CallContext) -> None:
    omni = OmniChannel(ctx)
    omni.add_queue("tier2_support", agents=2)
    item = WorkItem(id="w1", scenario=ScenarioId.S3)
    res = omni.handoff(item, "tier2_support")
    assert res["queue"] == "tier2_support" and res["fallback"] is False
    assert omni.queues["tier2_support"] == [item]


def test_handoff_falls_back_when_queue_absent(ctx: CallContext) -> None:
    omni = OmniChannel(ctx)
    item = WorkItem(id="w2", scenario=ScenarioId.S3)
    res = omni.handoff(item, "nonexistent")
    assert res["queue"] == OmniChannel.DEFAULT_QUEUE and res["fallback"] is True
    assert omni.queues[OmniChannel.DEFAULT_QUEUE] == [item]


def test_handoff_falls_back_when_queue_empty_of_agents(ctx: CallContext) -> None:
    omni = OmniChannel(ctx)
    omni.add_queue("ghost_town", agents=0)
    item = WorkItem(id="w3", scenario=ScenarioId.S3)
    res = omni.handoff(item, "ghost_town")
    assert res["queue"] == OmniChannel.DEFAULT_QUEUE and res["fallback"] is True
