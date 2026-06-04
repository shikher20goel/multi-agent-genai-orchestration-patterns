"""Task 031: percentile computation validated against known distributions."""
import numpy as np
import pytest
from scipy import stats as sps

from agentorch.config import load_config
from agentorch.stats.percentiles import DEFAULT_PS, percentiles


def test_uniform_distribution_percentiles() -> None:
    """For U(0,1), the p-th percentile is p/100 exactly."""
    cfg = load_config()
    x = cfg.get_rng("pctl-uniform").uniform(0, 1, size=200_000)
    got = percentiles(x, ps=(50, 95, 99))
    assert got[50] == pytest.approx(0.50, abs=0.01)
    assert got[95] == pytest.approx(0.95, abs=0.01)
    assert got[99] == pytest.approx(0.99, abs=0.005)


def test_lognormal_matches_analytic_quantiles() -> None:
    """Lognormal(mu, sigma) percentiles vs scipy's analytic ppf."""
    mu, sigma = -0.7, 0.55
    cfg = load_config()
    x = cfg.get_rng("pctl-lognorm").lognormal(mu, sigma, size=400_000)
    got = percentiles(x)
    dist = sps.lognorm(s=sigma, scale=np.exp(mu))
    for p in DEFAULT_PS:
        true_q = dist.ppf(p / 100.0)
        assert got[p] == pytest.approx(true_q, rel=0.03), f"p{p}"
    # Heavy upper tail: p99 > p50 strictly.
    assert got[99] > got[95] > got[50]


def test_exact_small_sample() -> None:
    """Linear-interpolation estimator on a tiny known sample."""
    got = percentiles([1.0, 2.0, 3.0, 4.0, 5.0], ps=(50,))
    assert got[50] == 3.0


def test_empty_and_bad_ps_raise() -> None:
    with pytest.raises(ValueError):
        percentiles([])
    with pytest.raises(ValueError):
        percentiles([1.0], ps=(150,))
