"""Agent and work-item abstractions (task 006)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from agentorch.types import ScenarioId

VALID_STATUSES = ("ok", "error", "timeout")


@dataclass(frozen=True)
class Agent:
    """A logical agent participating in an orchestration pattern."""

    id: str
    role: str


@dataclass
class WorkItem:
    """A unit of work flowing through a pattern under a scenario."""

    id: str
    scenario: ScenarioId
    payload: dict[str, Any] = field(default_factory=dict)
    created_at: float = 0.0


@dataclass
class WorkResult:
    """Outcome of running a WorkItem through a pattern."""

    item_id: str
    status: str
    payload: dict[str, Any] = field(default_factory=dict)
    error: str | None = None

    def __post_init__(self) -> None:
        if self.status not in VALID_STATUSES:
            raise ValueError(f"status must be one of {VALID_STATUSES}, got {self.status!r}")

    @property
    def ok(self) -> bool:
        return self.status == "ok"
