"""Fault-injection hooks at the mock boundary (task 009).

Mocks call :meth:`FaultInjector.check` for the component they represent
before serving. An armed fault fires with its configured probability,
drawn from the injector's own deterministic RNG stream.
"""
from __future__ import annotations

import numpy as np

from agentorch.types import Component, FaultType


class FaultInjector:
    def __init__(self, rng: np.random.Generator):
        self._rng = rng
        self._armed: dict[Component, tuple[FaultType, float]] = {}

    def arm(self, component: Component, fault_type: FaultType, probability: float = 1.0) -> None:
        if not 0.0 <= probability <= 1.0:
            raise ValueError("probability must be in [0, 1]")
        self._armed[component] = (fault_type, probability)

    def disarm(self, component: Component) -> None:
        self._armed.pop(component, None)

    def disarm_all(self) -> None:
        self._armed.clear()

    def armed(self, component: Component) -> bool:
        return component in self._armed

    def check(self, component: Component) -> FaultType | None:
        """Return the fault to apply for this call, or None."""
        entry = self._armed.get(component)
        if entry is None:
            return None
        fault_type, probability = entry
        if probability >= 1.0 or self._rng.random() < probability:
            return fault_type
        return None
