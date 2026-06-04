"""Task 033 (HUMAN-gated): Mann-Whitney U, rank-biserial, Hodges-Lehmann
validated on synthetic shifted distributions."""
import numpy as np
import pytest

from agentorch.config import load_config
from agentorch.stats.compare import CompareResult, compare, hodges_lehmann_shift


def test_known_shift_detected() -> None:
    """x = y + 1.0 (same shape): p tiny, HL ~ 1.0, r > 0."""
    cfg = load_config()
    rng = cfg.get_rng("cmp-shift")
    y = rng.lognormal(0.0, 0.4, size=400)
    x = y + 1.0
    res = compare(x, y)
    assert isinstance(res, CompareResult)
    assert res.p < 1e-10
    assert res.hodges_lehmann == pytest.approx(1.0, abs=0.1)
    assert res.rank_biserial > 0.5


def test_identical_distributions_not_significant() -> None:
    cfg = load_config()
    rng = cfg.get_rng("cmp-null")
    x = rng.normal(0, 1, size=300)
    y = rng.normal(0, 1, size=300)
    res = compare(x, y)
    assert res.p > 0.01
    assert abs(res.rank_biserial) < 0.15
    assert res.hodges_lehmann == pytest.approx(0.0, abs=0.2)


def test_direction_and_antisymmetry() -> None:
    """Swapping the samples flips the signs of r and HL."""
    cfg = load_config()
    rng = cfg.get_rng("cmp-dir")
    y = rng.exponential(1.0, size=200)
    x = y + 0.5
    a = compare(x, y)
    b = compare(y, x)
    assert a.rank_biserial == pytest.approx(-b.rank_biserial)
    assert a.hodges_lehmann == pytest.approx(-b.hodges_lehmann)
    assert a.p == pytest.approx(b.p)


def test_hodges_lehmann_exact_small_case() -> None:
    """HL of x={1,2}, y={0}: pairwise diffs {1,2}, median 1.5."""
    assert hodges_lehmann_shift(np.array([1.0, 2.0]),
                                np.array([0.0])) == 1.5


def test_rank_biserial_bounds_extreme_separation() -> None:
    """Fully separated samples give |r| = 1."""
    x = np.arange(10, 20, dtype=float)
    y = np.arange(0, 10, dtype=float)
    res = compare(x, y)
    assert res.rank_biserial == pytest.approx(1.0)


def test_empty_raises() -> None:
    with pytest.raises(ValueError):
        compare([], [1.0])
