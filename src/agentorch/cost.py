"""Per-platform cost model (task 014, HUMAN-gated).

Unit prices come ONLY from ``configs/costs.yaml``; that file carries the
source/placeholder annotations awaiting human verification. Costs scale
linearly with invocations, tokens, and service calls.
"""
from __future__ import annotations

from pathlib import Path

import yaml

from agentorch.config import Config
from agentorch.types import Platform

_COSTS_PATH = Path(__file__).resolve().parents[2] / "configs" / "costs.yaml"


def load_costs(path: str | Path | None = None) -> dict:
    p = Path(path) if path is not None else _COSTS_PATH
    with open(p) as f:
        return yaml.safe_load(f)


class CostModel:
    """Computes cost units (USD under configs/costs.yaml assumptions)."""

    def __init__(self, cfg: Config, costs_path: str | Path | None = None):
        self._cfg = cfg
        self._prices = load_costs(costs_path)

    def _platform_prices(self, platform: Platform | str) -> dict:
        plat = platform.value if isinstance(platform, Platform) else platform
        try:
            return self._prices[plat]
        except KeyError as exc:
            raise KeyError(f"no cost assumptions for platform {plat!r}") from exc

    def invocation_cost(self, platform: Platform | str, tokens_in: int,
                        tokens_out: int) -> float:
        """Cost of one model invocation with the given token counts."""
        p = self._platform_prices(platform)
        cost = (tokens_in / 1000.0) * float(p.get("price_per_1k_tokens_in", 0.0))
        cost += (tokens_out / 1000.0) * float(p.get("price_per_1k_tokens_out", 0.0))
        cost += float(p.get("price_per_invocation_flat", 0.0))
        return cost

    def service_call_cost(self, platform: Platform | str, service: str) -> float:
        """Cost of one platform service call (gateway/tool/memory/...)."""
        p = self._platform_prices(platform)
        services = p.get("service_calls", {})
        try:
            return float(services[service])
        except KeyError as exc:
            raise KeyError(
                f"no service-call price for ({platform}, {service})") from exc

    def request_cost(self, platform: Platform | str, model_invocations: int,
                     tokens_in: int, tokens_out: int,
                     service_calls: list[str] | None = None) -> float:
        """Total cost of a request: token costs + per-invocation flat + services."""
        p = self._platform_prices(platform)
        cost = (tokens_in / 1000.0) * float(p.get("price_per_1k_tokens_in", 0.0))
        cost += (tokens_out / 1000.0) * float(p.get("price_per_1k_tokens_out", 0.0))
        cost += model_invocations * float(p.get("price_per_invocation_flat", 0.0))
        for svc in service_calls or []:
            cost += self.service_call_cost(platform, svc)
        return cost
