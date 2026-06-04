"""Two-sample comparison: Mann-Whitney U + effect sizes (task 033, HUMAN-gated).

- Test: two-sided Mann-Whitney U (``scipy.stats.mannwhitneyu``), the
  rank-based test appropriate for skewed latency distributions.
- Effect size: rank-biserial correlation r = 2U/(n1*n2) - 1 in [-1, 1];
  r > 0 means x stochastically tends to exceed y.
- Shift estimate: Hodges-Lehmann estimator = median of all pairwise
  differences x_i - y_j, a robust estimate of the location shift.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np
from scipy import stats as sps


@dataclass
class CompareResult:
    u: float                  # Mann-Whitney U statistic (for x vs y)
    p: float                  # two-sided p-value
    rank_biserial: float      # effect size in [-1, 1]
    hodges_lehmann: float     # median of pairwise differences x_i - y_j
    n_x: int
    n_y: int


def hodges_lehmann_shift(x: np.ndarray, y: np.ndarray) -> float:
    """Median of all pairwise differences x_i - y_j."""
    diffs = x[:, None] - y[None, :]
    return float(np.median(diffs))


def compare(x: Iterable[float], y: Iterable[float]) -> CompareResult:
    """Two-sided Mann-Whitney U with rank-biserial and HL shift for x vs y."""
    ax = np.asarray(list(x), dtype=float)
    ay = np.asarray(list(y), dtype=float)
    if ax.size == 0 or ay.size == 0:
        raise ValueError("both samples must be non-empty")
    res = sps.mannwhitneyu(ax, ay, alternative="two-sided")
    u = float(res.statistic)
    rank_biserial = 2.0 * u / (ax.size * ay.size) - 1.0
    return CompareResult(
        u=u,
        p=float(res.pvalue),
        rank_biserial=float(rank_biserial),
        hodges_lehmann=hodges_lehmann_shift(ax, ay),
        n_x=int(ax.size),
        n_y=int(ay.size),
    )
