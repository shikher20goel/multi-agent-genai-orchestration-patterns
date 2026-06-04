"""Task 021: P6 HITL adjudication; pause-resume works; decision logged."""
import pytest

from agentorch.clients.context import CallContext
from agentorch.config import load_config
from agentorch.domain import WorkItem
from agentorch.patterns.base import validate_meta
from agentorch.patterns.p6_hitl import HitlPattern
from agentorch.types import Platform, ScenarioId


@pytest.mark.parametrize("platform", [Platform.BEDROCK, Platform.AGENTFORCE])
def test_p6_high_confidence_auto_approves(platform: Platform) -> None:
    cfg = load_config()
    p = HitlPattern(platform, CallContext.build(cfg), cfg)
    item = WorkItem(id="w1", scenario=ScenarioId.S3, payload={"confidence": 0.95})
    result, _ = p.run(item)
    assert result.ok and result.payload["adjudicated"] is False
    assert p.decision_log == []


@pytest.mark.parametrize("platform", [Platform.BEDROCK, Platform.AGENTFORCE])
def test_p6_low_confidence_pause_resume_logged(platform: Platform) -> None:
    cfg = load_config()
    p = HitlPattern(platform, CallContext.build(cfg), cfg)
    item = WorkItem(id="w2", scenario=ScenarioId.S3, payload={"confidence": 0.2})
    result, service_time = p.run(item)
    assert result.ok
    assert result.payload["adjudicated"] is True
    assert result.payload["decision"] == "approved"
    # decision logged with reviewer + confidence + timestamp
    assert len(p.decision_log) == 1
    entry = p.decision_log[0]
    assert entry["item_id"] == "w2" and entry["reviewer"] == "human-stub"
    assert entry["confidence"] == 0.2 and entry["ts"] >= 0
    assert service_time > 0


def test_p6_explicit_pause_resume_api() -> None:
    cfg = load_config()
    p = HitlPattern(Platform.BEDROCK, CallContext.build(cfg), cfg)
    item = WorkItem(id="w3", scenario=ScenarioId.S3)
    token = p.pause(item, draft="draft text", confidence=0.4)
    entry = p.resume(token, decision="rejected", reviewer="alice")
    assert entry["decision"] == "rejected" and entry["reviewer"] == "alice"
    with pytest.raises(KeyError):
        p.resume(token, decision="again")


def test_p6_agentforce_routes_to_adjudication_queue() -> None:
    cfg = load_config()
    p = HitlPattern(Platform.AGENTFORCE, CallContext.build(cfg), cfg)
    item = WorkItem(id="w4", scenario=ScenarioId.S3, payload={"confidence": 0.1})
    result, _ = p.run(item)
    assert result.ok
    assert p.omni is not None
    assert any(w.id == "w4" for w in p.omni.queues["adjudication"])


def test_p6_meta_valid() -> None:
    validate_meta(HitlPattern.meta())
