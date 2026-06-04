"""Task 014 (HUMAN-gated): per-platform cost model; cost scales with invocations."""
import math

import pytest

from agentorch.config import load_config
from agentorch.cost import CostModel, load_costs
from agentorch.types import Platform


@pytest.fixture()
def model() -> CostModel:
    return CostModel(load_config())


def test_prices_load_from_yaml() -> None:
    prices = load_costs()
    assert "bedrock" in prices and "agentforce" in prices


def test_invocation_cost_scales_with_tokens(model: CostModel) -> None:
    c1 = model.invocation_cost(Platform.BEDROCK, tokens_in=1000, tokens_out=500)
    c2 = model.invocation_cost(Platform.BEDROCK, tokens_in=2000, tokens_out=1000)
    assert c2 == pytest.approx(2 * c1)
    assert c1 > 0


def test_cost_scales_with_invocations(model: CostModel) -> None:
    one = model.request_cost(Platform.AGENTFORCE, model_invocations=1,
                             tokens_in=500, tokens_out=200)
    three = model.request_cost(Platform.AGENTFORCE, model_invocations=3,
                               tokens_in=1500, tokens_out=600)
    assert three == pytest.approx(3 * one)


def test_service_call_cost(model: CostModel) -> None:
    g = model.service_call_cost(Platform.BEDROCK, "gateway")
    t = model.service_call_cost(Platform.BEDROCK, "tool")
    assert g > 0 and t > 0
    with pytest.raises(KeyError):
        model.service_call_cost(Platform.BEDROCK, "nonexistent")


def test_request_cost_includes_services(model: CostModel) -> None:
    base = model.request_cost(Platform.BEDROCK, 1, 1000, 500)
    with_services = model.request_cost(
        Platform.BEDROCK, 1, 1000, 500, service_calls=["gateway", "tool"])
    expected = (base + model.service_call_cost(Platform.BEDROCK, "gateway")
                + model.service_call_cost(Platform.BEDROCK, "tool"))
    assert math.isclose(with_services, expected)


def test_platforms_differ(model: CostModel) -> None:
    b = model.request_cost(Platform.BEDROCK, 1, 1000, 500)
    a = model.request_cost(Platform.AGENTFORCE, 1, 1000, 500)
    assert b != a
