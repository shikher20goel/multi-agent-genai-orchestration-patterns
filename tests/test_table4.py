"""Task 038 / Phase 2 task 106 (HUMAN-gated): Table 4 grades are COMPUTED
from the calibrated results through the MWU/Holm machinery per the grade
function documented in make_table4.py and docs/GRADES.md."""
import numpy as np
import pandas as pd
import pytest

from agentorch.study.make_table4 import (
    GRADE_ORDER,
    TAIL_FRACTION,
    _dominated_grades,
    _oversight_grades,
    _tail,
    build_table4,
)


@pytest.fixture(scope="module")
def table4(smoke_results):
    return build_table4(smoke_results)


def test_covers_all_conditions_with_valid_grades(table4) -> None:
    df = table4
    assert len(df) == 42
    for col in ("latency_grade", "cost_grade", "reliability_grade",
                "oversight_grade", "overall_grade"):
        assert set(df[col]) <= {"A", "B", "C"}, col


def test_overall_is_worst_of_measured_components(table4) -> None:
    """Overall = worst of the three MEASURED grades; oversight is a
    capability axis reported separately (task 106)."""
    for _, r in table4.iterrows():
        worst = max((r["latency_grade"], r["cost_grade"],
                     r["reliability_grade"]), key=lambda g: GRADE_ORDER[g])
        assert r["overall_grade"] == worst


def test_oversight_from_capability_metadata_not_latency(table4) -> None:
    """Oversight derives from Pattern.meta() capability text: P6 strong
    (structural human decision point), independent of latency."""
    ovs = _oversight_grades()
    assert ovs["P6"] == "A"
    assert all(g != "A" for p, g in ovs.items() if p != "P6")
    for _, r in table4.iterrows():
        assert r["oversight_grade"] == ovs[r["pattern"]]


def test_dominated_grades_equivalence_group_semantics() -> None:
    """A = best Holm-significant equivalence group (never significantly
    dominated); C = dominated by >= 4 others; B otherwise."""
    rng = np.random.default_rng(7)
    n = 120
    samples = {
        # two statistically indistinguishable fast patterns -> both A
        "fast1": rng.normal(10, 1, n),
        "fast2": rng.normal(10, 1, n),
        # mid pattern -> dominated by the two fast ones only -> B
        "mid": rng.normal(20, 1, n),
        # slow patterns dominated by >= 4 others -> C
        "slow1": rng.normal(40, 1, n),
        "slow2": rng.normal(50, 1, n),
        "slow3": rng.normal(60, 1, n),
        "slow4": rng.normal(70, 1, n),
    }
    g = _dominated_grades(samples, alpha=0.05)
    assert g["fast1"] == "A" and g["fast2"] == "A"
    assert g["mid"] == "B"
    assert g["slow2"] == "C" and g["slow3"] == "C" and g["slow4"] == "C"


def test_tail_selects_slowest_decile() -> None:
    x = np.arange(100, dtype=float)
    t = _tail(x)
    assert len(t) == max(2, int(np.ceil(100 * TAIL_FRACTION)))
    assert t.min() >= np.percentile(x, 90) - 1


def test_reliability_scenario_invariant(table4) -> None:
    """The fault campaign runs on one scenario, so the reliability grade
    is a per-(pattern, platform) structural property."""
    g = table4.groupby(["pattern", "platform"])["reliability_grade"].nunique()
    assert (g == 1).all()


def test_deterministic(smoke_results, table4) -> None:
    again = build_table4(smoke_results)
    pd.testing.assert_frame_equal(table4, again)
