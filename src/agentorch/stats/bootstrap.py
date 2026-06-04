"""BCa bootstrap confidence intervals (task 032, HUMAN-gated).

Thin, seeded wrapper over ``scipy.stats.bootstrap(method='BCa')``
(bias-corrected and accelerated; Efron 1987). BCa adjusts the
percentile interval for median bias and skewness of the bootstrap
distribution, which matters for latency percentiles whose sampling
distributions are right-skewed.
"""
from __future__ import annotations

from typing import Callable, Iterable

import numpy as np
from scipy import stats as sps

from agentorch.config import Config


def bca_ci(x: Iterable[float], stat_fn: Callable[[np.ndarray], float],
           alpha: float = 0.05, n_resamples: int = 2000,
           rng: np.random.Generator | None = None) -> tuple[float, float]:
    """BCa (1 - alpha) confidence interval for ``stat_fn`` of `x`.

    `stat_fn` takes a 1-D array and returns a scalar (e.g. a percentile).
    Deterministic given the same `rng` state.
    """
    arr = np.asarray(list(x), dtype=float)
    if arr.size < 2:
        raise ValueError("need at least 2 observations for a bootstrap CI")
    if not 0 < alpha < 1:
        raise ValueError("alpha must be in (0, 1)")
    res = sps.bootstrap(
        (arr,),
        statistic=lambda sample, axis=-1: np.apply_along_axis(stat_fn, axis,
                                                              np.asarray(sample)),
        vectorized=True,
        confidence_level=1.0 - alpha,
        n_resamples=n_resamples,
        method="BCa",
        random_state=rng,
    )
    return float(res.confidence_interval.low), float(res.confidence_interval.high)


def bca_ci_from_config(x: Iterable[float], stat_fn: Callable[[np.ndarray], float],
                       cfg: Config, stream: str) -> tuple[float, float]:
    """`bca_ci` with alpha/n_resamples and the RNG taken from the config."""
    return bca_ci(x, stat_fn,
                  alpha=float(cfg.stats.alpha),
                  n_resamples=int(cfg.stats.n_resamples),
                  rng=cfg.get_rng(stream))
