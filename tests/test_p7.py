"""Task 022: P7 federated bridge; cluster outage contained."""
import pytest

from agentorch.clients.context import CallContext
from agentorch.config import load_config
from agentorch.domain import WorkItem
from agentorch.patterns.base import validate_meta
from agentorch.patterns.p7_bridge import BridgePattern
from agentorch.types import Component, FaultType, Platform, ScenarioId


@pytest.mark.parametrize("platform", [Platform.BEDROCK, Platform.AGENTFORCE])
def test_p7_runs_on_platform(platform: Platform) -> None:
    cfg = load_config()
    p = BridgePattern(platform, CallContext.build(cfg), cfg)
    result, service_time = p.run(WorkItem(id="w1", scenario=ScenarioId.S1))
    assert result.ok, result.error
    assert result.payload["remote"] is not None
    assert result.payload["degraded"] is False
    assert service_time > 0


def test_p7_meta_valid() -> None:
    validate_meta(BridgePattern.meta())


@pytest.mark.parametrize("platform", [Platform.BEDROCK, Platform.AGENTFORCE])
def test_p7_remote_cluster_outage_contained(platform: Platform) -> None:
    """Full remote-cluster outage degrades the federated portion only."""
    cfg = load_config()
    ctx = CallContext.build(cfg)
    p = BridgePattern(platform, ctx, cfg)
    # Outage of the ENTIRE remote cluster: the remote fault domain is
    # the shared injector's unit="remote" (task 104) — local-cluster
    # calls carry no unit and are unaffected.
    for comp in Component:
        p.remote_ctx.fault_injector.arm(comp, FaultType.OUTAGE, 1.0,
                                        unit="remote")
    result, _ = p.run(WorkItem(id="w1", scenario=ScenarioId.S1))
    assert result.ok, "local work must still complete"
    assert result.payload["degraded"] is True
    assert result.payload["remote"] is None
    assert "outage" in result.payload["remote_error"]


def test_p7_local_fault_still_fails_request() -> None:
    cfg = load_config()
    ctx = CallContext.build(cfg)
    ctx.fault_injector.arm(Component.MODEL_BACKEND, FaultType.ERROR, 1.0)
    p = BridgePattern(Platform.BEDROCK, ctx, cfg)
    result, _ = p.run(WorkItem(id="w1", scenario=ScenarioId.S1))
    assert result.status == "error"
