"""Offline tests for the real-AWS backends, using stub boto3 clients.

These prove the backend logic — serialisation, the missing-key contract,
redaction, shadow-mode non-blocking — without credentials or spend. What they
cannot prove is that the AWS API shapes are right; that is what the standalone
live smoke tests in M4 are for, and why those come before any pattern is
wired to a real service.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from anchor.agentcore.live_backends import (GatewayBackend,      # noqa: E402
                                            GuardrailBackend,
                                            MemoryBackend,
                                            ObservabilityBackend)
from anchor.agentcore.live_clients import (LiveAgentCore,        # noqa: E402
                                           LiveGuardrails)


class StubMemoryClient:
    def __init__(self):
        self.store: dict[str, list] = {}

    def create_event(self, *, memoryId, actorId, sessionId, eventTimestamp,
                     payload):
        self.store.setdefault(sessionId, []).insert(0, {"payload": payload})

    def list_events(self, *, memoryId, actorId, sessionId, maxResults):
        return {"events": self.store.get(sessionId, [])[:maxResults]}


def test_memory_round_trips_a_list_of_dicts() -> None:
    b = MemoryBackend(StubMemoryClient(), "mem-1")
    value = [{"agent": "a", "note": 1}, {"agent": "b", "note": 2}]
    b.put("board", value)
    assert b.get("board") == value


def test_memory_returns_none_for_a_missing_key() -> None:
    """P4 branches on this; raising would change its control flow."""
    assert MemoryBackend(StubMemoryClient(), "mem-1").get("absent") is None


def test_memory_overwrite_reads_back_the_latest() -> None:
    b = MemoryBackend(StubMemoryClient(), "mem-1")
    b.put("k", [1])
    b.put("k", [1, 2])
    assert b.get("k") == [1, 2]


def test_memory_refuses_an_unserialisable_value() -> None:
    """Loud failure beats a silently truncated blackboard."""
    with pytest.raises(TypeError):
        MemoryBackend(StubMemoryClient(), "mem-1").put("k", {1, 2, 3})


class StubGatewayClient:
    def __init__(self):
        self.calls = []

    def invoke_gateway(self, *, gatewayIdentifier, payload):
        self.calls.append(json.loads(payload.decode()))
        import io
        return {"response": io.BytesIO(json.dumps({"result": "ok"}).encode())}


def test_gateway_returns_the_mock_shape() -> None:
    g = GatewayBackend(StubGatewayClient(), "https://gw")
    out = g.call("search", {"q": 1})
    assert set(out) == {"tool", "result", "args"}
    assert out["tool"] == "search"


def test_gateway_call_through_the_seam_counts_hop_plus_tool() -> None:
    """P5's extra hop must survive the move to a real backend."""
    ac = LiveAgentCore(gateway=GatewayBackend(StubGatewayClient(), "https://gw"))
    before = ac.service_calls
    ac.gateway_call("search", {"q": 1})
    assert ac.service_calls - before == 2


class StubLogsClient:
    def __init__(self):
        self.events = []

    def create_log_group(self, **kw):
        raise Exception("already exists")

    def create_log_stream(self, **kw):
        raise Exception("already exists")

    def put_log_events(self, *, logGroupName, logStreamName, logEvents):
        self.events.extend(logEvents)


def test_observability_emits_only_structural_fields() -> None:
    """Redaction: ids and counters, never payload content."""
    c = StubLogsClient()
    b = ObservabilityBackend(c, "/g", "s")
    b.emit({"event": "created", "item": "i-1", "secret_payload": "DO NOT LOG"})
    msg = json.loads(c.events[0]["message"])
    assert msg == {"event": "created", "item": "i-1"}
    assert "secret_payload" not in msg


def test_observability_survives_an_existing_log_group() -> None:
    b = ObservabilityBackend(StubLogsClient(), "/g", "s")
    b.emit({"event": "x", "item": "y"})   # must not raise


class StubGuardrailClient:
    def __init__(self, action="NONE"):
        self.action = action
        self.seen = []

    def apply_guardrail(self, *, guardrailIdentifier, guardrailVersion, source,
                        content):
        self.seen.append(content)
        return {"action": self.action, "assessments": [{"x": 1}]}


def test_guardrail_shadow_never_blocks_even_on_intervention() -> None:
    """Shadow mode records what would have happened; it does not block."""
    b = GuardrailBackend(StubGuardrailClient("GUARDRAIL_INTERVENED"), "gr-1")
    out = b.apply("some draft", "shadow")
    assert out["blocked"] is False
    assert out["would_block"] is True


def test_guardrail_seam_records_verdict_not_text() -> None:
    gr = LiveGuardrails(backend=GuardrailBackend(StubGuardrailClient(), "gr-1"))
    gr.apply("a draft containing sensitive wording", mode="shadow")
    logged = json.dumps(gr.shadow_log)
    assert "sensitive wording" not in logged
    assert gr.shadow_log[0] == {"mode": "shadow", "blocked": False}


def test_guardrail_still_rejects_an_invalid_mode_with_a_backend() -> None:
    gr = LiveGuardrails(backend=GuardrailBackend(StubGuardrailClient(), "gr-1"))
    with pytest.raises(ValueError):
        gr.apply("x", mode="enforce")
