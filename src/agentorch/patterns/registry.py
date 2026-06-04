"""Pattern registry (task 023)."""
from __future__ import annotations

from agentorch.clients.context import CallContext
from agentorch.config import Config
from agentorch.patterns.base import Pattern
from agentorch.patterns.p1_supervisor import SupervisorPattern
from agentorch.patterns.p2_pipeline import PipelinePattern
from agentorch.patterns.p3_choreography import ChoreographyPattern
from agentorch.patterns.p4_blackboard import BlackboardPattern
from agentorch.patterns.p5_gateway import GatewayPattern
from agentorch.patterns.p6_hitl import HitlPattern
from agentorch.patterns.p7_bridge import BridgePattern
from agentorch.types import PatternId, Platform

REGISTRY: dict[PatternId, type[Pattern]] = {
    PatternId.SUPERVISOR: SupervisorPattern,
    PatternId.PIPELINE: PipelinePattern,
    PatternId.CHOREOGRAPHY: ChoreographyPattern,
    PatternId.BLACKBOARD: BlackboardPattern,
    PatternId.GATEWAY: GatewayPattern,
    PatternId.HITL: HitlPattern,
    PatternId.BRIDGE: BridgePattern,
}


def build(pattern_id: PatternId, platform: Platform, ctx: CallContext,
          cfg: Config) -> Pattern:
    """Instantiate the registered pattern class for `pattern_id`."""
    try:
        cls = REGISTRY[pattern_id]
    except KeyError as exc:
        raise KeyError(f"unknown pattern {pattern_id!r}") from exc
    return cls(platform, ctx, cfg)
