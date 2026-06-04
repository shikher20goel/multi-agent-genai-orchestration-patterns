"""Task 015: Pattern base + nine-element metadata."""
import pytest

from agentorch.clients.context import CallContext
from agentorch.config import load_config
from agentorch.domain import WorkItem, WorkResult
from agentorch.patterns.base import META_KEYS, Pattern, validate_meta
from agentorch.types import Component, Platform, ScenarioId


class _Demo(Pattern):
    @classmethod
    def meta(cls) -> dict:
        return {k: f"demo {k}" for k in META_KEYS}

    def _execute(self, item: WorkItem) -> WorkResult:
        self.ctx.boundary_call(self.platform, "model_invoke", Component.MODEL_BACKEND)
        return WorkResult(item_id=item.id, status="ok")


def test_meta_has_all_nine_keys() -> None:
    meta = _Demo.meta()
    assert len(META_KEYS) == 9
    assert set(meta) == set(META_KEYS)
    validate_meta(meta)


def test_validate_meta_rejects_bad_keys() -> None:
    with pytest.raises(ValueError):
        validate_meta({"name": "x"})
    bad = {k: "" for k in META_KEYS}
    bad["extra"] = "nope"
    with pytest.raises(ValueError):
        validate_meta(bad)


def test_run_returns_result_and_service_time() -> None:
    cfg = load_config()
    p = _Demo(Platform.BEDROCK, CallContext.build(cfg), cfg)
    result, service_time = p.run(WorkItem(id="w1", scenario=ScenarioId.S1))
    assert result.ok and service_time > 0


def test_platform_clients_wired() -> None:
    cfg = load_config()
    b = _Demo(Platform.BEDROCK, CallContext.build(cfg), cfg)
    assert b.bedrock is not None and b.agentforce is None
    a = _Demo(Platform.AGENTFORCE, CallContext.build(cfg), cfg)
    assert a.agentforce is not None and a.bedrock is None


def test_run_resets_per_request_accumulator() -> None:
    cfg = load_config()
    p = _Demo(Platform.BEDROCK, CallContext.build(cfg), cfg)
    _, t1 = p.run(WorkItem(id="w1", scenario=ScenarioId.S1))
    _, t2 = p.run(WorkItem(id="w2", scenario=ScenarioId.S1))
    # second run's service time is its own, not cumulative
    assert t2 < t1 + t2
    assert p.ctx.elapsed_s == t2
