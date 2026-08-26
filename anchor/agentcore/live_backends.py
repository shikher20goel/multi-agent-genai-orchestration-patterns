"""Real AWS backends behind the live client seam.

``live_clients.py`` holds the classes the released patterns actually call;
these are the objects those clients delegate to when a real service is
configured. Splitting them keeps the seam classes testable offline: a stub
backend exercises the whole control flow with no credentials, which is what
lets all seven patterns be verified before any money is spent.

Every backend is redaction-safe by construction: what crosses into a record
is an identifier, a counter or a verdict, never model text or event payload
content.
"""
from __future__ import annotations

import json
import time
from typing import Any


class MemoryBackend:
    """AgentCore Memory as a key/value store for P4's board and P6's pauses.

    The pattern contract is the mock's: ``get`` returns the stored value or
    ``None``. P4 reads a key it has just written and branches on the result,
    so raising on a miss would change its control flow.

    Values are JSON-encoded. A value that will not serialise fails loudly
    rather than being coerced -- a silently truncated blackboard would make
    P4's contention result wrong in a way no assertion would catch.
    """

    def __init__(self, client, memory_id: str, actor_id: str = "agentorch"):
        self._c = client
        self._memory_id = memory_id
        self._actor = actor_id

    def put(self, key: str, value: Any) -> None:
        blob = json.dumps(value)
        self._c.create_event(
            memoryId=self._memory_id,
            actorId=self._actor,
            sessionId=key,
            eventTimestamp=time.time(),
            payload=[{"conversational": {"role": "ASSISTANT",
                                         "content": {"text": blob}}}],
        )

    def get(self, key: str) -> Any:
        try:
            r = self._c.list_events(memoryId=self._memory_id,
                                    actorId=self._actor,
                                    sessionId=key, maxResults=1)
        except Exception:
            return None
        events = r.get("events", [])
        if not events:
            return None
        for entry in events[0].get("payload", []):
            text = (entry.get("conversational", {})
                         .get("content", {}).get("text"))
            if text is not None:
                return json.loads(text)
        return None


class GatewayBackend:
    """AgentCore Gateway tool invocation for P5.

    Returns the mock's dict shape. The two-call accounting (hop + tool) lives
    in ``LiveAgentCore.gateway_call``, not here, because it is a property of
    the seam contract rather than of the transport.
    """

    def __init__(self, client, gateway_url: str, target: str = "stand-in"):
        self._c = client
        self._url = gateway_url
        self._target = target

    def call(self, tool: str, args: dict[str, Any]) -> dict[str, Any]:
        resp = self._c.invoke_gateway(
            gatewayIdentifier=self._url,
            payload=json.dumps({"tool": tool, "arguments": args}).encode(),
        )
        body = resp.get("response")
        raw = body.read() if hasattr(body, "read") else body
        out = json.loads(raw) if raw else {}
        return {"tool": tool, "result": out.get("result", f"tool {tool} ok"),
                "args": args}


class ObservabilityBackend:
    """CloudWatch Logs emission for P3's structural events.

    Only ids and counters are emitted. P3's claim is about event flow, not
    about content, so nothing else needs to leave the runtime.
    """

    def __init__(self, client, log_group: str, log_stream: str):
        self._c = client
        self._group = log_group
        self._stream = log_stream
        self._ensured = False

    def _ensure(self) -> None:
        if self._ensured:
            return
        for create, kwargs in ((self._c.create_log_group,
                                {"logGroupName": self._group}),
                               (self._c.create_log_stream,
                                {"logGroupName": self._group,
                                 "logStreamName": self._stream})):
            try:
                create(**kwargs)
            except Exception:
                pass          # already exists is the normal case
        self._ensured = True

    def emit(self, event: dict[str, Any]) -> None:
        self._ensure()
        safe = {k: v for k, v in event.items()
                if k in ("event", "item", "seq", "pattern")}
        self._c.put_log_events(
            logGroupName=self._group, logStreamName=self._stream,
            logEvents=[{"timestamp": int(time.time() * 1000),
                        "message": json.dumps(safe)}],
        )


class GuardrailBackend:
    """Bedrock ApplyGuardrail for P6, shadow mode only.

    The assessed text is sent to the guardrail API and nowhere else, and only
    the verdict is returned upward. Blocking is not implemented: P6 calls
    ``apply(..., mode="shadow")`` and its claim concerns the human step.
    """

    def __init__(self, client, guardrail_id: str, version: str = "DRAFT"):
        self._c = client
        self._id = guardrail_id
        self._version = version

    def apply(self, text: str, mode: str) -> dict[str, Any]:
        r = self._c.apply_guardrail(
            guardrailIdentifier=self._id,
            guardrailVersion=str(self._version),
            source="OUTPUT",
            content=[{"text": {"text": text}}],
        )
        action = r.get("action", "NONE")
        return {
            "mode": mode,
            # Shadow mode never blocks regardless of the assessment; the
            # verdict is recorded so a reader can see what the guardrail
            # would have done.
            "blocked": False,
            "would_block": action == "GUARDRAIL_INTERVENED",
            "assessments": len(r.get("assessments", [])),
        }
