"""Task 038 (HUMAN-gated): Table 4 grades follow the documented rules."""
import pandas as pd
import pytest

from agentorch.config import load_config
from agentorch.study.make_table4 import GRADE_ORDER, build_table4
from agentorch.study.run_study import run_study


@pytest.fixture(scope="module")
def smoke_results(tmp_path_factory):
    out = tmp_path_factory.mktemp("res4")
    cfg = load_config()
    run_study(cfg, out, smoke=True)
    return out


@pytest.fixture(scope="module")
def table4(smoke_results):
    return build_table4(smoke_results)


def test_covers_all_conditions_with_valid_grades(table4) -> None:
    df = table4
    assert len(df) == 42
    for col in ("latency_grade", "cost_grade", "reliability_grade",
                "overall_grade"):
        assert set(df[col]) <= {"A", "B", "C"}, col


def test_overall_is_worst_of_components(table4) -> None:
    for _, r in table4.iterrows():
        worst = max((r["latency_grade"], r["cost_grade"],
                     r["reliability_grade"]), key=lambda g: GRADE_ORDER[g])
        assert r["overall_grade"] == worst


def test_cost_grade_follows_documented_ratio_rule(smoke_results, table4) -> None:
    """Re-derive one condition's cost grades from raw results."""
    lat = pd.read_csv(smoke_results / "latency.csv")
    cost = pd.read_csv(smoke_results / "cost.csv")
    base = lat[(lat["mode"] == "baseline") & (lat["platform"] == "bedrock")
               & (lat["scenario"] == "S1")]
    merged = base.merge(cost, on=["request_id", "pattern", "platform"])
    means = merged.groupby("pattern")["cost_units"].mean()
    cheapest = means.min()
    sub = table4[(table4["platform"] == "bedrock")
                 & (table4["scenario"] == "S1")]
    for _, r in sub.iterrows():
        ratio = means[r["pattern"]] / cheapest
        expected = "A" if ratio <= 1.5 else "B" if ratio <= 4.0 else "C"
        assert r["cost_grade"] == expected, r["pattern"]


def test_deterministic(smoke_results, table4) -> None:
    again = build_table4(smoke_results)
    pd.testing.assert_frame_equal(table4, again)
