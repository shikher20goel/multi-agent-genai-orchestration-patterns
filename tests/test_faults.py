"""Task 009: fault injector semantics; TIMEOUT produces timeout behavior."""
from agentorch.config import load_config
from agentorch.faults import FaultInjector
from agentorch.types import Component, FaultType


def _injector() -> FaultInjector:
    cfg = load_config()
    return FaultInjector(cfg.get_rng("faults"))


def test_unarmed_returns_none() -> None:
    inj = _injector()
    assert inj.check(Component.TOOL) is None


def test_armed_probability_one_always_fires() -> None:
    inj = _injector()
    inj.arm(Component.TOOL, FaultType.TIMEOUT, probability=1.0)
    assert all(inj.check(Component.TOOL) is FaultType.TIMEOUT for _ in range(20))


def test_disarm_stops_faults() -> None:
    inj = _injector()
    inj.arm(Component.GATEWAY, FaultType.ERROR, 1.0)
    assert inj.check(Component.GATEWAY) is FaultType.ERROR
    inj.disarm(Component.GATEWAY)
    assert inj.check(Component.GATEWAY) is None


def test_probability_respected_deterministically() -> None:
    inj1 = _injector()
    inj2 = _injector()
    for inj in (inj1, inj2):
        inj.arm(Component.MODEL_BACKEND, FaultType.THROTTLE, probability=0.3)
    seq1 = [inj1.check(Component.MODEL_BACKEND) for _ in range(200)]
    seq2 = [inj2.check(Component.MODEL_BACKEND) for _ in range(200)]
    assert seq1 == seq2
    fired = sum(1 for f in seq1 if f is not None)
    assert 30 <= fired <= 90  # ~0.3 of 200


def test_timeout_fault_causes_timeout_behavior() -> None:
    """A TIMEOUT fault at the boundary makes the call take timeout_s and fail."""
    from agentorch.clients.context import CallContext
    from agentorch.types import Platform

    cfg = load_config()
    ctx = CallContext.build(cfg)
    ctx.fault_injector.arm(Component.MODEL_BACKEND, FaultType.TIMEOUT, 1.0)
    t0 = ctx.clock.now()
    outcome = ctx.boundary_call(Platform.BEDROCK, "model_invoke", Component.MODEL_BACKEND)
    assert outcome.fault is FaultType.TIMEOUT
    assert not outcome.success
    assert ctx.clock.now() - t0 >= cfg.faults.timeout_s
