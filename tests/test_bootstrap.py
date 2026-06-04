"""Task 032 (HUMAN-gated): BCa bootstrap CI correctness.

Coverage check: across many independent samples from a known
distribution, the 95% BCa interval for a statistic must bracket the
true value ~95% of the time (tolerance band; fully seeded).
"""
import numpy as np
import pytest

from agentorch.config import load_config
from agentorch.stats.bootstrap import bca_ci, bca_ci_from_config


def test_deterministic_given_seed() -> None:
    cfg = load_config()
    x = cfg.get_rng("boot-data").lognormal(0.0, 0.5, size=120)
    ci1 = bca_ci(x, np.median, rng=cfg.get_rng("boot"), n_resamples=500)
    ci2 = bca_ci(x, np.median, rng=cfg.get_rng("boot"), n_resamples=500)
    assert ci1 == ci2
    assert ci1[0] < np.median(x) < ci1[1]


def test_coverage_of_mean_on_known_normal() -> None:
    """True mean = 5.0; 95% BCa CIs over 200 replicates must cover ~95%."""
    cfg = load_config()
    rng = cfg.get_rng("boot-coverage")
    true_mean = 5.0
    n_reps, covered = 200, 0
    for _ in range(n_reps):
        x = rng.normal(true_mean, 2.0, size=60)
        lo, hi = bca_ci(x, np.mean, alpha=0.05, n_resamples=400, rng=rng)
        covered += int(lo <= true_mean <= hi)
    rate = covered / n_reps
    # Binomial(200, .95) two-sided ~99.7% band is about +-4.6%; allow a
    # slightly wider tolerance for finite-n bootstrap undercoverage.
    assert 0.88 <= rate <= 0.99, f"coverage {rate}"


def test_coverage_of_p95_on_lognormal() -> None:
    """Skewed case: 95th percentile of a lognormal; BCa should hold close
    to nominal coverage despite skew."""
    cfg = load_config()
    rng = cfg.get_rng("boot-coverage-p95")
    from scipy import stats as sps
    mu, sigma = 0.0, 0.6
    true_p95 = sps.lognorm(s=sigma, scale=np.exp(mu)).ppf(0.95)
    n_reps, covered = 120, 0
    for _ in range(n_reps):
        x = rng.lognormal(mu, sigma, size=300)
        lo, hi = bca_ci(x, lambda a: float(np.percentile(a, 95)),
                        alpha=0.05, n_resamples=400, rng=rng)
        covered += int(lo <= true_p95 <= hi)
    rate = covered / n_reps
    assert 0.85 <= rate <= 1.0, f"coverage {rate}"


def test_config_wrapper_uses_config_values() -> None:
    cfg = load_config()
    x = cfg.get_rng("boot-cfg").normal(0, 1, size=80)
    ci1 = bca_ci_from_config(x, np.mean, cfg, stream="boot-stream")
    ci2 = bca_ci_from_config(x, np.mean, cfg, stream="boot-stream")
    assert ci1 == ci2


def test_validation_errors() -> None:
    with pytest.raises(ValueError):
        bca_ci([1.0], np.mean)
    with pytest.raises(ValueError):
        bca_ci([1.0, 2.0], np.mean, alpha=1.5)
