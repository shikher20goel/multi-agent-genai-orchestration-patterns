"""Parameterized lognormal latency model (task 008; recalibrated task 101).

Per-platform/service service times (seconds) sampled from lognormals
whose parameters come from the ``latency:`` section of
``configs/default.yaml``. A ``latency.shared`` section carries
platform-independent delay terms (the P6 human review decision time and
the P7 cross-platform RTT). Calibration (task 101): a single model step
has p50 in the 0.8-2.5 s range; cross-platform deltas are small and
documented in the config comments. The lognormal's heavy right tail
guarantees p99 > p50.
"""
from __future__ import annotations

import numpy as np

from agentorch.config import Config
from agentorch.types import Platform


class LatencyModel:
    """Samples per-platform/service service times (seconds) from lognormals."""

    def __init__(self, cfg: Config, rng: np.random.Generator):
        self._params = cfg.latency.to_dict()
        self._rng = rng

    def _lookup(self, plat: str, service: str) -> dict:
        plat_params = self._params.get(plat, {})
        if service in plat_params:
            return plat_params[service]
        shared = self._params.get("shared", {})
        if service in shared:
            return shared[service]
        raise KeyError(f"no latency params for ({plat}, {service})")

    def sample(self, platform: Platform | str, service: str) -> float:
        plat = platform.value if isinstance(platform, Platform) else platform
        p = self._lookup(plat, service)
        return float(self._rng.lognormal(mean=p["mu"], sigma=p["sigma"]))

    def sample_shared(self, service: str) -> float:
        """Sample a platform-independent shared delay term (task 101)."""
        shared = self._params.get("shared", {})
        if service not in shared:
            raise KeyError(f"no shared latency params for {service!r}")
        p = shared[service]
        return float(self._rng.lognormal(mean=p["mu"], sigma=p["sigma"]))
