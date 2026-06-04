"""Multiple-comparison correction over an enumerated family (task 034, HUMAN-gated).

Family definition (pre-committed): within ONE (platform, scenario)
condition, the family is the C(7, 2) = 21 pairwise comparisons among
the seven patterns P1..P7 for one endpoint. Each (platform, scenario,
endpoint) condition is corrected as its own family with the Holm
step-down procedure (statsmodels ``multipletests(method='holm')``),
which controls FWER at the configured alpha without independence
assumptions.
"""
from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from typing import Sequence

from statsmodels.stats.multitest import multipletests

from agentorch.types import PatternId, Platform, ScenarioId

FAMILY_SIZE = 21  # C(7, 2) pairwise pattern comparisons per condition


def enumerate_family(platform: Platform,
                     scenario: ScenarioId) -> list[tuple[PatternId, PatternId]]:
    """The 21 pattern pairs forming the family for one (platform, scenario)."""
    pairs = list(combinations(sorted(PatternId, key=lambda p: p.value), 2))
    assert len(pairs) == FAMILY_SIZE
    return pairs


@dataclass
class CorrectionResult:
    rejected: list[bool]
    p_adjusted: list[float]
    alpha: float
    method: str = "holm"


def holm(pvals: Sequence[float], alpha: float = 0.05) -> CorrectionResult:
    """Holm step-down FWER correction over one family of p-values."""
    if len(pvals) == 0:
        raise ValueError("empty p-value family")
    for p in pvals:
        if not 0.0 <= p <= 1.0:
            raise ValueError(f"p-value {p} outside [0, 1]")
    rejected, p_adj, _, _ = multipletests(list(pvals), alpha=alpha,
                                          method="holm")
    return CorrectionResult(rejected=[bool(r) for r in rejected],
                            p_adjusted=[float(p) for p in p_adj],
                            alpha=alpha)
