"""Pattern abstract base with nine-element metadata (task 015).

A pattern is constructed for one (platform, ctx, cfg) and exposes:
- ``meta()`` with EXACTLY the nine catalog keys;
- ``run(item) -> (WorkResult, service_time_s)`` where service_time_s
  is the per-request elapsed accumulated by client boundary calls.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from agentorch.clients.agentforce import MockAgentforceClient, OmniChannel
from agentorch.clients.bedrock import MockAgentCore, MockBedrockAgentRuntime, MockGuardrails
from agentorch.clients.context import CallContext
from agentorch.config import Config
from agentorch.domain import WorkItem, WorkResult
from agentorch.types import Platform

META_KEYS = (
    "name",
    "intent",
    "context",
    "problem",
    "forces",
    "solution",
    "platform_instantiations",
    "consequences",
    "governance_hooks",
)


class Pattern(ABC):
    """Base class for the seven orchestration patterns."""

    def __init__(self, platform: Platform, ctx: CallContext, cfg: Config):
        self.platform = platform
        self.ctx = ctx
        self.cfg = cfg
        # Platform clients (mocked, local, deterministic).
        if platform is Platform.BEDROCK:
            self.bedrock = MockBedrockAgentRuntime(ctx)
            self.agentcore = MockAgentCore(ctx)
            self.guardrails = MockGuardrails(ctx)
            self.agentforce = None
            self.omni = None
        else:
            self.bedrock = None
            self.agentcore = None
            self.guardrails = None
            self.agentforce = MockAgentforceClient(ctx)
            self.omni = OmniChannel(ctx)

    @classmethod
    @abstractmethod
    def meta(cls) -> dict[str, Any]:
        """Nine-element pattern metadata (catalog form)."""

    @abstractmethod
    def _execute(self, item: WorkItem) -> WorkResult:
        """Pattern-specific orchestration logic."""

    def run(self, item: WorkItem) -> tuple[WorkResult, float]:
        """Run one work item; returns (result, service_time_s)."""
        self.ctx.reset_request()
        result = self._execute(item)
        return result, self.ctx.elapsed_s


def validate_meta(meta: dict[str, Any]) -> None:
    """Raise if `meta` does not carry exactly the nine catalog keys."""
    keys = tuple(meta.keys())
    if set(keys) != set(META_KEYS):
        missing = set(META_KEYS) - set(keys)
        extra = set(keys) - set(META_KEYS)
        raise ValueError(f"meta keys mismatch: missing={missing}, extra={extra}")
