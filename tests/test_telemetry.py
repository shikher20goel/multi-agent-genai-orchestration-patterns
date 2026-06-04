"""Task 007: telemetry records; latency from separate timestamps."""
import math

from agentorch.telemetry import CostRecord, FaultRecord, LatencyRecord, TelemetrySink
from agentorch.types import Component, FaultType, Mode, PatternId, Platform, ScenarioId


def _lat(submit: float, complete: float) -> LatencyRecord:
    return LatencyRecord(
        request_id="r1", pattern=PatternId.SUPERVISOR, scenario=ScenarioId.S1,
        platform=Platform.BEDROCK, mode=Mode.BASELINE,
        submit_ts=submit, complete_ts=complete,
    )


def test_latency_ms_from_separate_timestamps() -> None:
    rec = _lat(10.0, 10.75)
    assert math.isclose(rec.latency_ms, 750.0)


def test_sink_collects_and_dataframes() -> None:
    sink = TelemetrySink()
    sink.record_latency(_lat(0.0, 0.5))
    sink.record_cost(CostRecord(
        request_id="r1", pattern=PatternId.SUPERVISOR, platform=Platform.BEDROCK,
        model_invocations=2, tokens_in=100, tokens_out=50, service_calls=3, cost_units=0.01,
    ))
    sink.record_fault(FaultRecord(
        component=Component.TOOL, fault=FaultType.TIMEOUT, contained=True, requests_affected=4,
    ))
    df = sink.to_dataframe("latency")
    assert len(df) == 1 and math.isclose(df["latency_ms"].iloc[0], 500.0)
    assert len(sink.to_dataframe("cost")) == 1
    assert len(sink.to_dataframe("faults")) == 1


def test_write_read_roundtrip(tmp_path) -> None:
    sink = TelemetrySink()
    sink.record_latency(_lat(1.0, 2.0))
    sink.write(tmp_path)
    frames = TelemetrySink.read(tmp_path)
    assert len(frames["latency"]) == 1
    assert math.isclose(frames["latency"]["latency_ms"].iloc[0], 1000.0)
    assert frames["cost"].empty and frames["faults"].empty
