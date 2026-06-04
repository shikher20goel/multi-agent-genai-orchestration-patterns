"""Parameterized lognormal latency model (task 008)."""
from __future__ import annotations

import numpy as np

from agentorch.config import Config
from agentorch.types import Platform


class LatencyModel:
    """Samples per-platform/service service times (seconds) from lognormals.

    Parameters come from the ``latency:`` section of ``configs/default.yaml``.
    The lognormal's heavy right tail guarantees p99 > p50.
    """

    def __init__(self, cfg: Config, rng: np.random.Generator):
        self._params = cfg.latency.to_dict()
        self._rng = rng

    def sample(self, platform: Platform | str, service: str) -> float:
        plat = platform.value if isinstance(platform, Platform) else platform
        try:
            p = self._params[plat][service]
        except KeyError as exc:
            raise KeyError(f"no latency params for ({plat}, {service})") from exc
        return float(self._rng.lognormal(mean=p["mu"], sigma=p["sigma"]))
