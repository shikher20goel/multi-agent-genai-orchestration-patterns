"""Tests for the runnable HITL governance example (task 044)."""
from __future__ import annotations

import pathlib
import subprocess
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "governance"))

from hitl_example import (  # noqa: E402
    GENESIS_HASH,
    AuditLog,
    AuditLogHalted,
    HitlGovernor,
    ImmutableEntryError,
    default_human_stub,
)


def test_confidence_gate_auto_approves_above_threshold():
    gov = HitlGovernor(confidence_threshold=0.8)
    rec = gov.review("i1", "harmless summary", 0.9)
    assert rec["disposition"] == "auto_approved"
    events = [e.event for e in gov.audit_log.entries()]
    assert events == ["draft_produced", "auto_approved"]


def test_confidence_gate_routes_low_confidence_to_human_stub():
    gov = HitlGovernor(confidence_threshold=0.8)
    rec = gov.review("i2", "issue a refund now", 0.4)
    assert rec["disposition"] == "reject"  # default stub rejects risky drafts
    assert rec["reviewer"] == "human-stub"
    events = [e.event for e in gov.audit_log.entries()]
    assert events == ["draft_produced", "routed_to_human", "human_decision"]


def test_custom_human_stub_decision_is_logged():
    gov = HitlGovernor(confidence_threshold=0.8, human_stub=lambda d, c: "approve")
    rec = gov.review("i3", "issue a refund now", 0.4)
    assert rec["disposition"] == "approve"
    last = gov.audit_log.entries()[-1]
    assert last.event == "human_decision"
    assert last.payload["decision"] == "approve"


def test_chain_links_and_verifies():
    log = AuditLog()
    log.append("a", {"x": 1})
    log.append("b", {"y": 2})
    log.append("c", {"z": 3})
    entries = log.entries()
    assert entries[0].prev_hash == GENESIS_HASH
    assert entries[1].prev_hash == entries[0].entry_hash
    assert entries[2].prev_hash == entries[1].entry_hash
    assert log.verify_chain()


def test_entries_are_immutable():
    log = AuditLog()
    e = log.append("a", {"x": 1})
    with pytest.raises(ImmutableEntryError):
        e.event = "tampered"
    with pytest.raises(ImmutableEntryError):
        e.entry_hash = "0" * 64
    with pytest.raises(TypeError):
        e.payload["x"] = 999  # MappingProxyType refuses item assignment


def test_tampering_detected_by_verify_chain():
    log = AuditLog()
    log.append("a", {"x": 1})
    log.append("b", {"y": 2})
    # forge the internal list (bypassing the public API) to simulate tampering
    forged = object.__new__(type(log.entries()[0]))
    object.__setattr__(forged, "index", 0)
    object.__setattr__(forged, "event", "forged")
    object.__setattr__(forged, "payload", {})
    object.__setattr__(forged, "prev_hash", GENESIS_HASH)
    object.__setattr__(forged, "entry_hash", log.entries()[0].entry_hash)
    log._entries[0] = forged
    assert not log.verify_chain()


def test_halt_stops_chain_mid_stream():
    log = AuditLog()
    log.append("a", {"x": 1})
    log.halt("emergency stop")
    assert log.halted
    assert log.entries()[-1].event == "halt"
    with pytest.raises(AuditLogHalted):
        log.append("post_halt", {})
    assert len(log) == 2  # nothing appended after the halt
    assert log.verify_chain()  # halted chain still verifies


def test_default_human_stub_is_deterministic():
    assert default_human_stub("please issue a refund", 0.3) == "reject"
    assert default_human_stub("summarize the ticket", 0.3) == "approve"


def test_demo_script_runs_end_to_end():
    repo = pathlib.Path(__file__).resolve().parents[1]
    proc = subprocess.run(
        [sys.executable, str(repo / "governance" / "hitl_example.py")],
        capture_output=True, text=True, timeout=30,
    )
    assert proc.returncode == 0, proc.stderr
    assert "verify_chain: True" in proc.stdout
    assert "append after halt correctly refused" in proc.stdout
