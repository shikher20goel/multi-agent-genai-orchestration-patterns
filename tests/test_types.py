"""Task 005: core enums."""
from agentorch.types import Component, FaultType, Mode, PatternId, Platform, ScenarioId


def test_seven_patterns() -> None:
    assert len(PatternId) == 7
    assert {p.value for p in PatternId} == {"P1", "P2", "P3", "P4", "P5", "P6", "P7"}
    assert PatternId.SUPERVISOR.value == "P1"
    assert PatternId.BRIDGE.value == "P7"


def test_three_scenarios() -> None:
    assert len(ScenarioId) == 3
    assert {s.value for s in ScenarioId} == {"S1", "S2", "S3"}


def test_platforms_modes() -> None:
    assert {p.value for p in Platform} == {"agentforce", "bedrock"}
    assert {m.value for m in Mode} == {"baseline", "fault"}


def test_fault_types_components() -> None:
    assert {f.name for f in FaultType} == {"TIMEOUT", "ERROR", "THROTTLE", "OUTAGE"}
    assert {c.name for c in Component} == {
        "MODEL_BACKEND", "GATEWAY", "TOOL", "EVENT_BUS", "MEMORY_STORE", "HUMAN_QUEUE",
    }
