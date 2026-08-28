"""AgentCore agent that runs the RELEASED pattern modules, unmodified.

This exists to answer reviewer R2.2 in its own terms. An agent that
re-implemented a pattern's call sequence by hand would show only that *code
matching* the released implementation runs on a real platform. So this agent
imports ``agentorch.patterns`` and executes it.

Section V-A claims the mock boundary is "a single call-context seam:
replacing a mock with a live client means implementing that client interface
against the vendor SDK, while the orchestration logic, load generator,
telemetry, and statistical machinery are unchanged". That claim is either
true or it is not, and this file is the test. The entire substitution is
``attach_live_clients(pattern, ...)`` — three attribute assignments at most.
Nothing in ``agentorch`` is edited, subclassed, or monkey-patched.

WHAT THIS DOES AND DOES NOT SHOW. It shows that the released modules execute
against live AWS services. It is NOT a timing arm: the released
``Pattern._parallel`` runs fan-out branches sequentially and accounts only
``max`` of their durations, which is correct under the study's virtual clock
but makes wall-clock here incomparable to the anchor's. And P6's human wait
is a latency SAMPLE, not a platform call, so "P6 live" means live model +
live guardrail + live memory with a *simulated* human.

Work items come from the repo's own scenario generators, not hand-built
payloads. The generators supply fields the patterns branch on — notably
``confidence``, which drives P6's review gate. A synthetic payload silently
takes the default 0.9, P6 never pauses, and its human path and memory seam go
unexercised while everything still reports success.

Redaction is enforced at the boundary: completion text is consumed inside the
runtime and never returned.
"""
import os
import sys
import time

import boto3
from bedrock_agentcore.runtime import BedrockAgentCoreApp

sys.path.insert(0, "/app")

from agentorch.clients.context import CallContext              # noqa: E402
from agentorch.config import load_config                       # noqa: E402
from agentorch.patterns.p1_supervisor import SupervisorPattern      # noqa: E402
from agentorch.patterns.p2_pipeline import PipelinePattern          # noqa: E402
from agentorch.patterns.p3_choreography import ChoreographyPattern  # noqa: E402
from agentorch.patterns.p4_blackboard import BlackboardPattern      # noqa: E402
from agentorch.patterns.p5_gateway import GatewayPattern            # noqa: E402
from agentorch.patterns.p6_hitl import HitlPattern                  # noqa: E402
from agentorch.patterns.p7_bridge import BridgePattern              # noqa: E402
from agentorch.scenarios.s1_rag_qa import generate_s1          # noqa: E402
from agentorch.telemetry import TelemetrySink                  # noqa: E402
from agentorch.types import Platform                           # noqa: E402

from anchor.agentcore.live_backends import (GatewayBackend,    # noqa: E402
                                            GuardrailBackend,
                                            MemoryBackend,
                                            ObservabilityBackend)
from anchor.agentcore.live_clients import (LiveAgentCore,      # noqa: E402
                                           LiveBedrockAgentRuntime,
                                           LiveGuardrails,
                                           attach_live_clients)

app = BedrockAgentCoreApp()

PATTERNS = {
    "P1": SupervisorPattern, "P2": PipelinePattern, "P3": ChoreographyPattern,
    "P4": BlackboardPattern, "P5": GatewayPattern, "P6": HitlPattern,
    "P7": BridgePattern,
}

PATTERN = os.environ.get("ANCHOR_PATTERN", "P2").upper()
MODEL_ID = os.environ.get("ANCHOR_MODEL_ID", "us.amazon.nova-micro-v1:0")
MODEL_REGION = os.environ.get("ANCHOR_MODEL_REGION",
                              os.environ.get("AWS_REGION", "us-east-1"))
MEMORY_ID = os.environ.get("ANCHOR_MEMORY_ID") or None
GATEWAY_URL = os.environ.get("ANCHOR_GATEWAY_URL") or None
GUARDRAIL_ID = os.environ.get("ANCHOR_GUARDRAIL_ID") or None
LOG_GROUP = os.environ.get("ANCHOR_LOG_GROUP",
                           "/agentorch/all7/observability")

_CFG = load_config()
_bedrock = boto3.client("bedrock-runtime", region_name=MODEL_REGION)
_ac_data = boto3.client("bedrock-agentcore", region_name=MODEL_REGION)
_logs = boto3.client("logs", region_name=MODEL_REGION)
_br = boto3.client("bedrock-runtime", region_name=MODEL_REGION)


def _backends():
    """Only wire a backend that was actually provisioned.

    A pattern whose seam is unconfigured falls back to the in-memory stub, and
    the record says so, rather than the run failing opaquely inside a
    container or — worse — appearing to succeed against a service it never
    reached.
    """
    mem = MemoryBackend(_ac_data, MEMORY_ID) if MEMORY_ID else None
    gw = GatewayBackend(GATEWAY_URL, MODEL_REGION) if GATEWAY_URL else None
    obs = ObservabilityBackend(_logs, LOG_GROUP, f"{PATTERN}-live")
    gr = GuardrailBackend(_br, GUARDRAIL_ID) if GUARDRAIL_ID else None
    return mem, gw, obs, gr


def _build(item_seed: int):
    mem, gw, obs, gr = _backends()
    ctx = CallContext.build(_CFG, sink=TelemetrySink(),
                            stream_prefix=f"{PATTERN}:bedrock:S1:live")
    pat = PATTERNS[PATTERN](Platform.BEDROCK, ctx, _CFG)
    clients = {
        "bedrock": LiveBedrockAgentRuntime(_bedrock, MODEL_ID),
        "agentcore": LiveAgentCore(memory=mem, gateway=gw, observability=obs),
        "guardrails": LiveGuardrails(backend=gr),
    }
    attach_live_clients(pat, **clients)
    # Items from the repo's own generator, so scenario-supplied fields the
    # patterns branch on are present.
    items = generate_s1(item_seed + 1, _CFG.get_rng(f"all7-live-{item_seed}"),
                        _CFG)
    return pat, clients, items[-1]


@app.entrypoint
def handler(payload, context=None):
    want = str(payload.get("pattern", PATTERN)).upper()
    if want != PATTERN:
        return {"pattern": PATTERN,
                "status": f"error:pattern_mismatch:{want}",
                "invocations": None}
    t0 = time.perf_counter()
    try:
        pat, clients, item = _build(int(payload.get("seq", 0)))
        result, service_time_s = pat.run(item)
        b, ac, gr = clients["bedrock"], clients["agentcore"], clients["guardrails"]
        return {
            "pattern": PATTERN,
            "status": "ok" if result.status == "ok" else f"pattern:{result.status}",
            "released_module": type(pat).__module__,
            "released_class": type(pat).__name__,
            "pattern_name": pat.pattern_name,
            "result_status": result.status,
            # Counters come from the LIVE clients, so they count real calls
            # rather than the mock's virtual accounting.
            "invocations": b.invocations,
            "tokens_in": b.tokens_in,
            "tokens_out": b.tokens_out,
            "service_calls": ac.service_calls,
            "gateway_calls": ac.gateway_calls,
            "observability_events": len(ac.emitted),
            "guardrails_applied": gr.applied,
            # Which seams actually reached a real service, so a fallback to
            # the in-memory stub can never be mistaken for live evidence.
            "backends_live": {"memory": MEMORY_ID is not None,
                              "gateway": GATEWAY_URL is not None,
                              "guardrail": GUARDRAIL_ID is not None,
                              "observability": True},
            "item_confidence": item.payload.get("confidence"),
            "paused_for_human": ac.service_calls > 0 and PATTERN == "P6",
            # Recorded, but not a timing measurement -- see module docstring.
            "in_runtime_wall_s": time.perf_counter() - t0,
            "virtual_service_time_s": service_time_s,
        }
    except Exception as exc:
        return {"pattern": PATTERN, "status": f"error:{type(exc).__name__}",
                "detail": str(exc)[:300], "invocations": None}


if __name__ == "__main__":
    app.run()
