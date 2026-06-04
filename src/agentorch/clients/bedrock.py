"""Local mocks of Amazon Bedrock agent runtimes (no network, no SDKs).

Method names and request/response shapes mirror the documented boto3
``bedrock-agent-runtime`` ``invoke_agent`` and ``bedrock-agentcore``
``invoke_agent_runtime`` calls. Every entry point performs
fault check -> latency sample -> cost/telemetry accounting through the
shared :class:`~agentorch.clients.context.CallContext`.
"""
from __future__ import annotations

from typing import Any

from agentorch.clients.context import CallContext, CallOutcome
from agentorch.types import Component, Platform


class BedrockClientError(RuntimeError):
    """Raised when a mocked Bedrock call fails (fault injected)."""

    def __init__(self, message: str, outcome: CallOutcome):
        super().__init__(message)
        self.outcome = outcome


def _draw_tokens(ctx: CallContext, text: str) -> tuple[int, int]:
    """Deterministic synthetic token counts derived from input length + config means."""
    tokens_cfg = ctx.cfg.tokens
    tokens_in = max(1, len(text) // 4) + int(tokens_cfg.input_mean)
    tokens_out = int(tokens_cfg.output_mean)
    return tokens_in, tokens_out


class MockBedrockAgentRuntime:
    """Mirror of boto3 bedrock-agent-runtime ``invoke_agent``."""

    def __init__(self, ctx: CallContext):
        self._ctx = ctx
        self._sessions: dict[str, list[str]] = {}

    def invoke_agent(self, agentId: str, agentAliasId: str, sessionId: str,
                     inputText: str) -> dict[str, Any]:
        ctx = self._ctx
        outcome = ctx.boundary_call(Platform.BEDROCK, "model_invoke", Component.MODEL_BACKEND)
        if not outcome.success:
            raise BedrockClientError(
                f"invoke_agent failed: {outcome.fault.value if outcome.fault else 'unknown'}",
                outcome,
            )
        tokens_in, tokens_out = _draw_tokens(ctx, inputText)
        ctx.model_invocations += 1
        ctx.tokens_in += tokens_in
        ctx.tokens_out += tokens_out
        self._sessions.setdefault(sessionId, []).append(inputText)
        return {
            "completion": f"[{agentId}/{agentAliasId}] response to: {inputText}",
            "sessionId": sessionId,
            "usage": {"inputTokens": tokens_in, "outputTokens": tokens_out},
        }


class MockAgentCore:
    """Mirror of bedrock-agentcore ``invoke_agent_runtime`` + AgentCore services."""

    def __init__(self, ctx: CallContext):
        self._ctx = ctx
        self._memory: dict[str, Any] = {}
        self.observability_events: list[dict[str, Any]] = []

    def invoke_agent_runtime(self, agentRuntimeArn: str, runtimeSessionId: str,
                             payload: dict[str, Any] | str,
                             qualifier: str = "DEFAULT") -> dict[str, Any]:
        ctx = self._ctx
        outcome = ctx.boundary_call(Platform.BEDROCK, "model_invoke", Component.MODEL_BACKEND)
        if not outcome.success:
            raise BedrockClientError(
                f"invoke_agent_runtime failed: "
                f"{outcome.fault.value if outcome.fault else 'unknown'}",
                outcome,
            )
        text = payload if isinstance(payload, str) else str(payload)
        tokens_in, tokens_out = _draw_tokens(ctx, text)
        ctx.model_invocations += 1
        ctx.tokens_in += tokens_in
        ctx.tokens_out += tokens_out
        return {
            "runtimeSessionId": runtimeSessionId,
            "qualifier": qualifier,
            "response": f"[{agentRuntimeArn}] handled payload",
            "usage": {"inputTokens": tokens_in, "outputTokens": tokens_out},
        }

    def gateway_call(self, tool: str, args: dict[str, Any]) -> dict[str, Any]:
        """Tool call via the AgentCore gateway: adds one extra latency hop."""
        ctx = self._ctx
        hop = ctx.boundary_call(Platform.BEDROCK, "gateway", Component.GATEWAY)
        if not hop.success:
            raise BedrockClientError(
                f"gateway hop failed: {hop.fault.value if hop.fault else 'unknown'}", hop)
        ctx.service_calls += 1
        tool_outcome = ctx.boundary_call(Platform.BEDROCK, "tool", Component.TOOL)
        if not tool_outcome.success:
            raise BedrockClientError(
                f"tool {tool} failed: "
                f"{tool_outcome.fault.value if tool_outcome.fault else 'unknown'}",
                tool_outcome,
            )
        ctx.service_calls += 1
        return {"tool": tool, "result": f"tool {tool} ok", "args": args}

    def memory_get(self, key: str) -> Any:
        outcome = self._ctx.boundary_call(Platform.BEDROCK, "memory", Component.MEMORY_STORE)
        if not outcome.success:
            raise BedrockClientError(
                f"memory_get failed: {outcome.fault.value if outcome.fault else 'unknown'}",
                outcome)
        self._ctx.service_calls += 1
        return self._memory.get(key)

    def memory_put(self, key: str, value: Any) -> None:
        outcome = self._ctx.boundary_call(Platform.BEDROCK, "memory", Component.MEMORY_STORE)
        if not outcome.success:
            raise BedrockClientError(
                f"memory_put failed: {outcome.fault.value if outcome.fault else 'unknown'}",
                outcome)
        self._ctx.service_calls += 1
        self._memory[key] = value

    def identity_check(self, principal: str) -> dict[str, Any]:
        outcome = self._ctx.boundary_call(Platform.BEDROCK, "identity", Component.GATEWAY)
        if not outcome.success:
            raise BedrockClientError(
                f"identity_check failed: {outcome.fault.value if outcome.fault else 'unknown'}",
                outcome)
        self._ctx.service_calls += 1
        return {"principal": principal, "allowed": True}

    def observability_emit(self, event: dict[str, Any]) -> None:
        outcome = self._ctx.boundary_call(
            Platform.BEDROCK, "observability", Component.EVENT_BUS)
        if not outcome.success:
            raise BedrockClientError(
                f"observability_emit failed: "
                f"{outcome.fault.value if outcome.fault else 'unknown'}",
                outcome)
        self._ctx.service_calls += 1
        self.observability_events.append(event)


class MockGuardrails:
    """Guardrails mock: shadow mode logs but never blocks; block mode may block."""

    BLOCKLIST = ("FORBIDDEN",)

    def __init__(self, ctx: CallContext):
        self._ctx = ctx
        self.shadow_log: list[dict[str, Any]] = []

    def apply(self, text: str, mode: str = "shadow") -> dict[str, Any]:
        if mode not in ("shadow", "block"):
            raise ValueError("mode must be 'shadow' or 'block'")
        outcome = self._ctx.boundary_call(Platform.BEDROCK, "guardrails", Component.GATEWAY)
        if not outcome.success:
            raise BedrockClientError(
                f"guardrails failed: {outcome.fault.value if outcome.fault else 'unknown'}",
                outcome)
        self._ctx.service_calls += 1
        flagged = any(term in text for term in self.BLOCKLIST)
        if mode == "shadow":
            if flagged:
                self.shadow_log.append({"text": text, "action": "would_block"})
            return {"action": "allowed", "flagged": flagged, "mode": mode}
        if flagged:
            return {"action": "blocked", "flagged": True, "mode": mode}
        return {"action": "allowed", "flagged": False, "mode": mode}
