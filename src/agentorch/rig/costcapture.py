"""Cost-capture harness (task 030, HUMAN-gated).

Converts per-request CallContext counters into CostRecords using the
HUMAN-gated unit prices in ``configs/costs.yaml``, and aggregates the
records into a per-(pattern, platform) ledger:
mean cost-units per request, decomposed into model vs service spend.

All prices flow from configs/costs.yaml only; nothing is hard-coded.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from agentorch.clients.context import CallContext
from agentorch.telemetry import CostRecord, TelemetrySink
from agentorch.types import PatternId, Platform

LEDGER_COLUMNS = [
    "pattern", "platform", "n_requests", "mean_cost_units",
    "mean_model_invocations", "mean_tokens_in", "mean_tokens_out",
    "mean_service_calls", "total_cost_units",
]


def capture_request_cost(ctx: CallContext, sink: TelemetrySink, request_id: str,
                         pattern: PatternId, platform: Platform) -> CostRecord:
    """Emit one CostRecord from the context's per-request counters."""
    cost_model = ctx.cost_model
    if cost_model is None:
        raise RuntimeError("CallContext has no cost model; cannot capture cost")
    cost_units = cost_model.request_cost(  # type: ignore[attr-defined]
        platform,
        model_invocations=ctx.model_invocations,
        tokens_in=ctx.tokens_in,
        tokens_out=ctx.tokens_out,
        service_calls=list(ctx.services_called),
    )
    rec = CostRecord(
        request_id=request_id,
        pattern=pattern,
        platform=platform,
        model_invocations=ctx.model_invocations,
        tokens_in=ctx.tokens_in,
        tokens_out=ctx.tokens_out,
        service_calls=ctx.service_calls,
        cost_units=cost_units,
    )
    sink.record_cost(rec)
    return rec


def aggregate_ledger(cost_df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate CostRecords into a per-(pattern, platform) ledger frame."""
    if cost_df.empty:
        return pd.DataFrame(columns=LEDGER_COLUMNS)
    grouped = cost_df.groupby(["pattern", "platform"], as_index=False).agg(
        n_requests=("request_id", "count"),
        mean_cost_units=("cost_units", "mean"),
        mean_model_invocations=("model_invocations", "mean"),
        mean_tokens_in=("tokens_in", "mean"),
        mean_tokens_out=("tokens_out", "mean"),
        mean_service_calls=("service_calls", "mean"),
        total_cost_units=("cost_units", "sum"),
    )
    return grouped[LEDGER_COLUMNS].sort_values(["pattern", "platform"]).reset_index(drop=True)


def write_ledger(sink_or_df: "TelemetrySink | pd.DataFrame",
                 path: str | Path) -> pd.DataFrame:
    """Write the aggregated cost ledger CSV; returns the ledger frame."""
    if isinstance(sink_or_df, TelemetrySink):
        cost_df = sink_or_df.to_dataframe("cost")
    else:
        cost_df = sink_or_df
    ledger = aggregate_ledger(cost_df)
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    ledger.to_csv(p, index=False)
    return ledger
