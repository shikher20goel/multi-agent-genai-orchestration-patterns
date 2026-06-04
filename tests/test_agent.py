"""Task 006: Agent and WorkItem abstractions."""
import pytest

from agentorch.domain import Agent, WorkItem, WorkResult
from agentorch.types import ScenarioId


def test_agent_fields() -> None:
    a = Agent(id="a1", role="supervisor")
    assert a.id == "a1" and a.role == "supervisor"


def test_workitem_defaults() -> None:
    w = WorkItem(id="w1", scenario=ScenarioId.S1)
    assert w.payload == {} and w.created_at == 0.0


def test_workresult_status_validation() -> None:
    for s in ("ok", "error", "timeout"):
        r = WorkResult(item_id="w1", status=s)
        assert r.status == s
    with pytest.raises(ValueError):
        WorkResult(item_id="w1", status="bogus")


def test_workresult_ok_property() -> None:
    assert WorkResult(item_id="w", status="ok").ok
    assert not WorkResult(item_id="w", status="error", error="boom").ok
