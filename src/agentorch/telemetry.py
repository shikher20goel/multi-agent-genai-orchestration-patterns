"""Telemetry records for latency, cost, and faults (task 007).

`submit_ts` and `complete_ts` are recorded separately so latency is
computed open-loop-correctly (no coordinated omission).
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

import pandas as pd

from agentorch.types import Component, FaultType, Mode, PatternId, Platform, ScenarioId


@dataclass
class LatencyRecord:
    request_id: str
    pattern: PatternId
    scenario: ScenarioId
    platform: Platform
    mode: Mode
    submit_ts: float
    complete_ts: float
    fault: FaultType | None = None
    success: bool = True

    @property
    def latency_ms(self) -> float:
        return (self.complete_ts - self.submit_ts) * 1000.0


@dataclass
class CostRecord:
    request_id: str
    pattern: PatternId
    platform: Platform
    model_invocations: int
    tokens_in: int
    tokens_out: int
    service_calls: int
    cost_units: float


@dataclass
class FaultRecord:
    component: Component
    fault: FaultType
    contained: bool
    requests_affected: int


def _row(rec: object) -> dict:
    d = asdict(rec)  # type: ignore[arg-type]
    out = {}
    for k, v in d.items():
        out[k] = v.value if hasattr(v, "value") else v
    return out


class TelemetrySink:
    """Collects latency, cost, and fault records; round-trips via CSV."""

    def __init__(self) -> None:
        self.latency: list[LatencyRecord] = []
        self.cost: list[CostRecord] = []
        self.faults: list[FaultRecord] = []

    def record_latency(self, rec: LatencyRecord) -> None:
        self.latency.append(rec)

    def record_cost(self, rec: CostRecord) -> None:
        self.cost.append(rec)

    def record_fault(self, rec: FaultRecord) -> None:
        self.faults.append(rec)

    def to_dataframe(self, kind: str) -> pd.DataFrame:
        if kind == "latency":
            rows = [_row(r) for r in self.latency]
            df = pd.DataFrame(rows)
            if not df.empty:
                df["latency_ms"] = (df["complete_ts"] - df["submit_ts"]) * 1000.0
            return df
        if kind == "cost":
            return pd.DataFrame([_row(r) for r in self.cost])
        if kind == "faults":
            return pd.DataFrame([_row(r) for r in self.faults])
        raise ValueError(f"unknown kind {kind!r}")

    def write(self, directory: str | Path) -> None:
        d = Path(directory)
        d.mkdir(parents=True, exist_ok=True)
        for kind in ("latency", "cost", "faults"):
            self.to_dataframe(kind).to_csv(d / f"{kind}.csv", index=False)

    @classmethod
    def read(cls, directory: str | Path) -> dict[str, pd.DataFrame]:
        d = Path(directory)
        out: dict[str, pd.DataFrame] = {}
        for kind in ("latency", "cost", "faults"):
            p = d / f"{kind}.csv"
            if not p.exists():
                out[kind] = pd.DataFrame()
                continue
            try:
                out[kind] = pd.read_csv(p)
            except pd.errors.EmptyDataError:
                out[kind] = pd.DataFrame()
        return out
