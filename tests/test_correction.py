"""Task 034 (HUMAN-gated): Holm correction over the enumerated 21-pair family."""
import numpy as np
import pytest

from agentorch.config import load_config
from agentorch.stats.correction import (FAMILY_SIZE, enumerate_family, holm)
from agentorch.types import PatternId, Platform, ScenarioId


def test_family_size_is_21_for_one_condition() -> None:
    fam = enumerate_family(Platform.BEDROCK, ScenarioId.S1)
    assert len(fam) == 21
    assert FAMILY_SIZE == 21
    # All pairs distinct, unordered, covering all 7 patterns.
    assert len(set(map(frozenset, fam))) == 21
    seen = {p for pair in fam for p in pair}
    assert seen == set(PatternId)


def test_holm_matches_hand_computation() -> None:
    """Holm on p = [0.01, 0.04, 0.03] at alpha=0.05:
    sorted p (0.01, 0.03, 0.04) vs alpha/(m-k): 0.0167, 0.025, 0.05 ->
    reject all three; adjusted p = [0.03, 0.08->monotone 0.08? no:
    statsmodels: adj = max-cummax of p*(m-rank)] - verify against
    statsmodels semantics with explicit expected values."""
    res = holm([0.01, 0.04, 0.03], alpha=0.05)
    # adjusted: 0.01*3=0.03, 0.03*2=0.06, 0.04*1=0.04 -> cummax: 0.03,0.06,0.06
    assert res.p_adjusted == pytest.approx([0.03, 0.06, 0.06])
    assert res.rejected == [True, False, False]


def test_holm_controls_fwer_under_global_null() -> None:
    """21 independent uniform p-values per family: the Holm familywise
    error rate must be ~alpha, far below the ~66% uncorrected rate."""
    cfg = load_config()
    rng = cfg.get_rng("holm-null")
    alpha = float(cfg.stats.alpha)
    n_families = 200  # statistical budget: SE(FWER)~=0.015 at alpha=0.05, bound 2*alpha
    any_reject = 0
    any_uncorrected = 0
    for _ in range(n_families):
        pvals = rng.uniform(0, 1, size=FAMILY_SIZE)
        res = holm(list(pvals), alpha=alpha)
        any_reject += int(any(res.rejected))
        any_uncorrected += int(np.any(pvals < alpha))
    fwer = any_reject / n_families
    raw = any_uncorrected / n_families
    assert fwer <= alpha * 2.0, f"FWER {fwer} not controlled"
    assert raw > 0.5  # sanity: uncorrected would be wildly anti-conservative


def test_holm_keeps_true_effects() -> None:
    """A very small p in a 21-family survives Holm."""
    pvals = [1e-6] + [0.5] * 20
    res = holm(pvals, alpha=0.05)
    assert res.rejected[0] is True
    assert sum(res.rejected) == 1


def test_validation() -> None:
    with pytest.raises(ValueError):
        holm([])
    with pytest.raises(ValueError):
        holm([1.2])
