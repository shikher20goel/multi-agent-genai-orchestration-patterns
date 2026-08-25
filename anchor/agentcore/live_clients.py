"""Live implementations of the client seam the released patterns call through.

Section V-A of the manuscript claims the mock boundary is "a single
call-context seam": replacing a mock with a live client means implementing
that client interface against the vendor SDK, while the orchestration logic
is unchanged. These classes are that implementation, and
``attach_live_clients`` is the whole substitution.

THE RULE THAT GOVERNS EVERY CLASS HERE: a live client must never call
``ctx.boundary_call(...)``. That method drives the virtual clock, the latency
model and the fault injector of the deterministic study. A live client that
invoked it would fold wall-clock behaviour into the emulated timing model and
vice versa, and the two are deliberately separate -- live measurements stay
outside the deterministic statistics. The visible consequence is that
``virtual_service_time_s`` comes back as 0.0 from a live run: the mock's
accounting simply never ran. That is reported in the records rather than left
for a reader to infer.

Live clients count their own real calls instead, which is what the structural
assertions (five model invocations for the supervisor fan-out, one for the
single-stage pipeline, two service calls per gateway hop) are checked against.
"""
from __future__ import annotations

from typing import Any


class LiveBedrockAgentRuntime:
    """Live implementation of the seam ``MockBedrockAgentRuntime`` defines.

    Same method, same argument names, same return shape. The released patterns
    cannot tell the difference, which is the point.
    """

    def __init__(self, client, model_id: str):
        self._client = client
        self._model_id = model_id
        self.invocations = 0
        self.tokens_in = 0
        self.tokens_out = 0

    def invoke_agent(self, agentId: str, agentAliasId: str, sessionId: str,
                     inputText: str) -> dict[str, Any]:
        resp = self._client.converse(
            modelId=self._model_id,
            # agentId carries the released module's own role label
            # ("supervisor", "collab-0", "agent-draft"), so the live call
            # preserves the role structure the pattern expresses.
            messages=[{"role": "user",
                       "content": [{"text": f"[{agentId}] {inputText}"}]}],
            inferenceConfig={"maxTokens": 200, "temperature": 0.2},
        )
        usage = resp.get("usage", {})
        self.invocations += 1
        self.tokens_in += int(usage.get("inputTokens", 0))
        self.tokens_out += int(usage.get("outputTokens", 0))
        text = resp["output"]["message"]["content"][0]["text"]
        return {"completion": text, "sessionId": sessionId}


class LiveAgentCore:
    """Live implementation of the ``MockAgentCore`` seam methods.

    Stubbed in M1 so all seven patterns can be exercised offline before any
    AWS resource exists; each method is replaced with its real service call in
    M4, one at a time, smoke-tested standalone first.
    """

    def __init__(self, memory=None, gateway=None, observability=None):
        self._memory_backend = memory
        self._gateway_backend = gateway
        self._observability_backend = observability
        self._memory: dict[str, Any] = {}
        self.emitted: list[dict[str, Any]] = []
        self.service_calls = 0
        self.gateway_calls = 0

    def observability_emit(self, event: dict[str, Any]) -> None:
        """One structural event. P3 emits one per handled event."""
        self.service_calls += 1
        self.emitted.append(event)
        if self._observability_backend is not None:
            self._observability_backend.emit(event)

    def memory_get(self, key: str) -> Any:
        """Return the stored value, or None when absent.

        Returning None rather than raising is load-bearing: P4 calls
        ``memory_get`` on a key it has just created and relies on the mock's
        contract. Raising here would change the pattern's control flow.
        """
        self.service_calls += 1
        if self._memory_backend is not None:
            return self._memory_backend.get(key)
        return self._memory.get(key)

    def memory_put(self, key: str, value: Any) -> None:
        self.service_calls += 1
        if self._memory_backend is not None:
            self._memory_backend.put(key, value)
        else:
            self._memory[key] = value

    def gateway_call(self, tool: str, args: dict[str, Any]) -> dict[str, Any]:
        """A tool call through the gateway: one hop plus the tool itself.

        The mock counts TWO service calls here, and so does this. The extra
        hop is P5's structural consequence -- collapsing it into one would
        erase the very thing the pattern claims.
        """
        self.service_calls += 2
        self.gateway_calls += 1
        if self._gateway_backend is not None:
            return self._gateway_backend.call(tool, args)
        return {"tool": tool, "result": f"tool {tool} ok", "args": args}


class LiveGuardrails:
    """Live implementation of the ``MockGuardrails`` seam.

    P6's Bedrock branch calls ``apply(draft, mode="shadow")``. Shadow mode
    logs and never blocks; that is the mode the pattern uses, and the pattern's
    claim is about the human adjudication step, not about guardrail
    enforcement, so blocking is deliberately not implemented.
    """

    def __init__(self, backend=None):
        self._backend = backend
        self.applied = 0
        self.shadow_log: list[dict[str, Any]] = []
        self.service_calls = 0

    def apply(self, text: str, mode: str = "shadow") -> dict[str, Any]:
        if mode not in ("shadow", "block"):
            raise ValueError("mode must be 'shadow' or 'block'")
        self.service_calls += 1
        self.applied += 1
        if self._backend is not None:
            result = self._backend.apply(text, mode)
        else:
            result = {"mode": mode, "blocked": False, "assessments": []}
        # Redaction: the assessed text is never retained, only the verdict.
        self.shadow_log.append({"mode": mode,
                                "blocked": bool(result.get("blocked"))})
        return result


def attach_live_clients(pattern, *, bedrock=None, agentcore=None,
                        guardrails=None) -> dict[str, Any]:
    """Swap the pattern's mock collaborators for live ones.

    This is the entire substitution Section V-A describes. It assigns only
    attributes the pattern already defines: creating new ones would change
    ``agentorch``'s object shape rather than swapping its collaborators, and
    the claim under test is that the released module runs *unmodified*.

    Returns the bundle so the caller can read the live call counters.
    """
    bundle: dict[str, Any] = {}
    for name, client in (("bedrock", bedrock), ("agentcore", agentcore),
                         ("guardrails", guardrails)):
        if client is None:
            continue
        if getattr(pattern, name, None) is None and not hasattr(pattern, name):
            continue
        setattr(pattern, name, client)
        bundle[name] = client
    return bundle
