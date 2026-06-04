"""Runnable human-in-the-loop (HITL) governance demo (task 044).

Demonstrates the governance hooks of pattern P6 as a self-contained,
dependency-light script:

1. A **confidence gate** routes low-confidence agent drafts to a human.
2. A **human stub** records an approve/reject decision.
3. Every event is appended to a **hash-chained, append-only AuditLog**
   whose entries are immutable; ``verify_chain()`` detects tampering.
4. ``halt()`` stops the chain mid-stream: no further entries can be
   appended after a halt, modelling an emergency-stop oversight control
   (EU AI Act Art. 14(4)(e)-style intervention point).

Run it: ``python3 governance/hitl_example.py``
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Callable, Mapping

GENESIS_HASH = "0" * 64


class AuditLogHalted(RuntimeError):
    """Raised when appending to a halted audit log."""


class ImmutableEntryError(TypeError):
    """Raised on any attempt to mutate a committed audit entry."""


class AuditEntry:
    """One immutable, hash-chained audit record.

    All fields are set once via ``object.__setattr__`` at construction;
    any later attribute assignment or deletion raises
    :class:`ImmutableEntryError`.
    """

    __slots__ = ("index", "event", "payload", "prev_hash", "entry_hash")

    index: int
    event: str
    payload: Mapping[str, Any]
    prev_hash: str
    entry_hash: str

    def __setattr__(self, name: str, value: Any) -> None:
        raise ImmutableEntryError("audit entries are immutable")

    def __delattr__(self, name: str) -> None:
        raise ImmutableEntryError("audit entries are immutable")

    def __repr__(self) -> str:
        return (f"AuditEntry(index={self.index}, event={self.event!r}, "
                f"hash={self.entry_hash[:8]}...)")


def _hash_entry(index: int, event: str, payload: Mapping[str, Any], prev_hash: str) -> str:
    body = json.dumps(
        {"index": index, "event": event, "payload": dict(payload), "prev": prev_hash},
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


class AuditLog:
    """Hash-chained append-only audit log with an emergency halt."""

    def __init__(self) -> None:
        self._entries: list[AuditEntry] = []
        self._halted = False

    # -- append-only API -----------------------------------------------------
    def append(self, event: str, payload: dict[str, Any]) -> AuditEntry:
        if self._halted:
            raise AuditLogHalted("audit log halted; chain is closed")
        prev = self._entries[-1].entry_hash if self._entries else GENESIS_HASH
        index = len(self._entries)
        frozen_payload: Mapping[str, Any] = MappingProxyType(dict(payload))
        entry = object.__new__(AuditEntry)
        object.__setattr__(entry, "index", index)
        object.__setattr__(entry, "event", event)
        object.__setattr__(entry, "payload", frozen_payload)
        object.__setattr__(entry, "prev_hash", prev)
        object.__setattr__(entry, "entry_hash", _hash_entry(index, event, frozen_payload, prev))
        self._entries.append(entry)
        return entry

    def halt(self, reason: str) -> AuditEntry:
        """Record a final HALT entry and close the chain."""
        entry = self.append("halt", {"reason": reason})
        self._halted = True
        return entry

    @property
    def halted(self) -> bool:
        return self._halted

    def entries(self) -> tuple[AuditEntry, ...]:
        """Read-only view of the chain."""
        return tuple(self._entries)

    def __len__(self) -> int:
        return len(self._entries)

    # -- verification ----------------------------------------------------------
    def verify_chain(self) -> bool:
        """Recompute every hash; True iff the chain is intact and linked."""
        prev = GENESIS_HASH
        for i, e in enumerate(self._entries):
            if e.index != i or e.prev_hash != prev:
                return False
            if _hash_entry(e.index, e.event, e.payload, e.prev_hash) != e.entry_hash:
                return False
            prev = e.entry_hash
        return True


@dataclass
class HitlGovernor:
    """Confidence gate -> human stub -> audit log pipeline."""

    confidence_threshold: float
    audit_log: AuditLog = field(default_factory=AuditLog)
    human_stub: Callable[[str, float], str] | None = None

    def review(self, item_id: str, draft: str, confidence: float) -> dict[str, Any]:
        """Gate one agent draft. Returns the final disposition record."""
        self.audit_log.append(
            "draft_produced",
            {"item_id": item_id, "confidence": confidence, "draft_sha256":
             hashlib.sha256(draft.encode("utf-8")).hexdigest()},
        )
        if confidence >= self.confidence_threshold:
            self.audit_log.append(
                "auto_approved",
                {"item_id": item_id, "confidence": confidence,
                 "threshold": self.confidence_threshold},
            )
            return {"item_id": item_id, "disposition": "auto_approved",
                    "reviewer": None, "confidence": confidence}
        # below threshold: pause and route to the human
        self.audit_log.append(
            "routed_to_human",
            {"item_id": item_id, "confidence": confidence,
             "threshold": self.confidence_threshold},
        )
        decide = self.human_stub or default_human_stub
        decision = decide(draft, confidence)
        if decision not in ("approve", "reject"):
            raise ValueError(f"human decision must be approve|reject, got {decision!r}")
        self.audit_log.append(
            "human_decision",
            {"item_id": item_id, "decision": decision, "reviewer": "human-stub"},
        )
        return {"item_id": item_id, "disposition": decision,
                "reviewer": "human-stub", "confidence": confidence}


def default_human_stub(draft: str, confidence: float) -> str:
    """Deterministic stand-in for a human adjudicator.

    Approves unless the draft contains an obviously consequential
    keyword, in which case it rejects -- a stand-in for human judgment.
    """
    risky = any(k in draft.lower() for k in ("refund", "delete", "legal"))
    return "reject" if risky else "approve"


def main() -> int:
    """Run the end-to-end demo and print the audit trail."""
    gov = HitlGovernor(confidence_threshold=0.8)
    cases = [
        ("item-1", "Summarize the customer ticket.", 0.95),          # auto approve
        ("item-2", "Issue a refund of the disputed charge.", 0.55),  # human reject
        ("item-3", "Draft a follow-up email to the customer.", 0.62),  # human approve
    ]
    for item_id, draft, conf in cases:
        rec = gov.review(item_id, draft, conf)
        print(f"{rec['item_id']}: {rec['disposition']} "
              f"(confidence={rec['confidence']:.2f}, reviewer={rec['reviewer']})")

    gov.audit_log.halt("operator pressed emergency stop")
    print(f"chain length: {len(gov.audit_log)}; "
          f"verify_chain: {gov.audit_log.verify_chain()}; "
          f"halted: {gov.audit_log.halted}")
    try:
        gov.audit_log.append("post_halt", {})
    except AuditLogHalted:
        print("append after halt correctly refused")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
