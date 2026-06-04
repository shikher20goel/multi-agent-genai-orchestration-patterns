"""Core enums and identifiers (architecture contract, task 005)."""
from __future__ import annotations

from enum import Enum


class PatternId(str, Enum):
    SUPERVISOR = "P1"
    PIPELINE = "P2"
    CHOREOGRAPHY = "P3"
    BLACKBOARD = "P4"
    GATEWAY = "P5"
    HITL = "P6"
    BRIDGE = "P7"


class ScenarioId(str, Enum):
    S1 = "S1"
    S2 = "S2"
    S3 = "S3"


class Platform(str, Enum):
    AGENTFORCE = "agentforce"
    BEDROCK = "bedrock"


class Mode(str, Enum):
    BASELINE = "baseline"
    FAULT = "fault"


class FaultType(str, Enum):
    TIMEOUT = "timeout"
    ERROR = "error"
    THROTTLE = "throttle"
    OUTAGE = "outage"


class Component(str, Enum):
    MODEL_BACKEND = "model_backend"
    GATEWAY = "gateway"
    TOOL = "tool"
    EVENT_BUS = "event_bus"
    MEMORY_STORE = "memory_store"
    HUMAN_QUEUE = "human_queue"
