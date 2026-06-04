"""Virtual clock: all timing is simulated; nothing sleeps (contract)."""
from __future__ import annotations


class VirtualClock:
    """Monotonic virtual time in float seconds."""

    def __init__(self, start: float = 0.0):
        self._t = float(start)

    def now(self) -> float:
        return self._t

    def advance(self, dt: float) -> float:
        if dt < 0:
            raise ValueError("cannot advance the clock backwards")
        self._t += dt
        return self._t
