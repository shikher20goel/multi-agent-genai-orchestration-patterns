"""Fault-injection hooks at the mock boundary (task 009; windows task 104).

Mocks call :meth:`FaultInjector.check` for the component they represent
before serving. Two arming modes:

- **Probabilistic** (:meth:`arm`): an armed fault fires with its
  configured probability on each boundary call, drawn from the
  injector's own deterministic RNG stream (TIMEOUT/ERROR/THROTTLE).
- **Outage window** (:meth:`arm_window`, task 104): cross-request fault
  state — the component is *down* for a wall-clock window
  ``[start_s, end_s)`` on the simulated arrival timeline, and every
  boundary call traversing it during the window is affected.

Either mode can be restricted to a named ``unit`` of the component
(e.g. one tool behind the P5 gateway, or the P7 remote cluster), so the
campaign can inject *one tool's* fault or *one cluster's* outage.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from agentorch.types import Component, FaultType


@dataclass
class _Armed:
    fault_type: FaultType
    probability: float = 1.0
    unit: str | None = None          # None = every unit of the component
    window: tuple[float, float] | None = None  # (start_s, end_s) or None


class FaultInjector:
    def __init__(self, rng: np.random.Generator):
        self._rng = rng
        self._armed: dict[Component, _Armed] = {}

    def arm(self, component: Component, fault_type: FaultType,
            probability: float = 1.0, unit: str | None = None) -> None:
        if not 0.0 <= probability <= 1.0:
            raise ValueError("probability must be in [0, 1]")
        self._armed[component] = _Armed(fault_type, probability, unit)

    def arm_window(self, component: Component, fault_type: FaultType,
                   start_s: float, end_s: float, unit: str | None = None) -> None:
        """Arm a cross-request outage window on the simulated timeline."""
        if end_s <= start_s:
            raise ValueError("window end must be after start")
        self._armed[component] = _Armed(fault_type, 1.0, unit, (start_s, end_s))

    def disarm(self, component: Component) -> None:
        self._armed.pop(component, None)

    def disarm_all(self) -> None:
        self._armed.clear()

    def armed(self, component: Component) -> bool:
        return component in self._armed

    def window_end(self, component: Component) -> float | None:
        """End of the armed outage window for `component`, if any."""
        entry = self._armed.get(component)
        if entry is None or entry.window is None:
            return None
        return entry.window[1]

    def check(self, component: Component, unit: str | None = None,
              now: float | None = None) -> FaultType | None:
        """Return the fault to apply for this call, or None.

        `unit` names the sub-unit being called (tool name, cluster);
        `now` is the simulated time of the call (required to evaluate
        outage windows; window faults never fire when `now` is None).
        """
        entry = self._armed.get(component)
        if entry is None:
            return None
        if entry.unit is not None and unit != entry.unit:
            return None
        if entry.window is not None:
            if now is None:
                return None
            start, end = entry.window
            return entry.fault_type if start <= now < end else None
        if entry.probability >= 1.0 or self._rng.random() < entry.probability:
            return entry.fault_type
        return None
