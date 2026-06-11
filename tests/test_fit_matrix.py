"""Phase 3 task 201: figures/fit_matrix.csv is computed by the
pre-registered rule of docs/FIT_RULE.md -- 21 platform-independent
(pattern, scenario) cells in {Weak, Moderate, Strong}."""
import pandas as pd
import pytest

from agentorch.study.make_fit_matrix import (
    CAPABILITY_GATE,
    GRADE_OF_STANDING,
    UPGRADE,
    _pessimistic,
    _pool,
    build_fit_matrix,
)


@pytest.fixture(scope="module")
def fit(smoke_results):
    return build_fit_matrix(smoke_results)


def test_one_grade_per_pattern_scenario(fit) -> None:
    assert len(fit) == 21
    assert set(fit["fit_grade"]) <= {"Weak", "Moderate", "Strong"}
    assert fit.groupby(["pattern", "scenario"]).size().eq(1).all()
    assert "platform" not in fit.columns  # platform-independent


def test_grade_follows_pooled_standing_and_capability(fit) -> None:
    """fit_grade == base(pooled standing), upgraded one level when the
    scenario's required capability is present (docs/FIT_RULE.md)."""
    for _, r in fit.iterrows():
        base = GRADE_OF_STANDING[r["pooled_standing"]]
        expect = UPGRADE[base] if r["capability_applied"] else base
        assert r["fit_grade"] == expect, dict(r)


def test_pooling_requires_both_platforms_for_extremes(fit) -> None:
    for _, r in fit.iterrows():
        a, b = r["agentforce_standing"], r["bedrock_standing"]
        assert r["pooled_standing"] == (a if a == b else "MID"), dict(r)


def test_capability_gate_membership(fit) -> None:
    """capability_applied reflects the pattern capability flags for the
    scenario's gate (P1/P4 adaptive decomposition in S2; P3 event
    absorption and P6 selective human routing in S3; none in S1)."""
    assert CAPABILITY_GATE["S1"] == ()
    applied = {(r["pattern"], r["scenario"])
               for _, r in fit.iterrows() if r["capability_applied"]}
    assert applied == {("P1", "S2"), ("P4", "S2"), ("P3", "S3"),
                       ("P6", "S3")}


def test_helpers() -> None:
    assert _pessimistic("TOP", "BOTTOM") == "BOTTOM"
    assert _pessimistic("TOP", "MID") == "MID"
    assert _pool({"agentforce": "TOP", "bedrock": "TOP"}) == "TOP"
    assert _pool({"agentforce": "TOP", "bedrock": "BOTTOM"}) == "MID"


def test_deterministic(smoke_results, fit) -> None:
    pd.testing.assert_frame_equal(fit, build_fit_matrix(smoke_results))
