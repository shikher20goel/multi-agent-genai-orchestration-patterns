"""Latency percentile computation (task 031).

Uses the standard linear-interpolation quantile estimator
(numpy ``percentile`` with the default 'linear' method), which is
consistent: for large samples from a continuous distribution the
estimates converge to the true quantiles.
"""
from __future__ import annotations

from typing import Iterable, Sequence

import numpy as np

DEFAULT_PS: tuple[float, ...] = (50, 95, 99, 99.9)


def percentiles(x: Iterable[float],
                ps: Sequence[float] = DEFAULT_PS) -> dict[float, float]:
    """Return {p: value} for each requested percentile of `x`.

    Raises ValueError on an empty sample or out-of-range percentile.
    """
    arr = np.asarray(list(x), dtype=float)
    if arr.size == 0:
        raise ValueError("cannot compute percentiles of an empty sample")
    for p in ps:
        if not 0 <= p <= 100:
            raise ValueError(f"percentile {p} outside [0, 100]")
    values = np.percentile(arr, list(ps))
    return {float(p): float(v) for p, v in zip(ps, values)}
