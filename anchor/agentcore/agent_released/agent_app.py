"""AgentCore agent that runs the RELEASED pattern modules, unmodified.

This exists to answer reviewer R2.2 in its own terms. The earlier anchor
agent re-implemented P1's and P2's call sequences by hand; a reviewer can
fairly reply that this demonstrates only that *code matching* the released
implementation runs on a real platform, not the released implementation
itself. So this agent imports ``agentorch.patterns`` and executes it.

Section V-A claims the mock boundary is "a single call-context seam:
replacing a mock with a live client means implementing that client
interface against the vendor SDK, while the orchestration logic, load
generator, telemetry, and statistical machinery are unchanged". That
claim is either true or it is not, and this file is the test. The entire
substitution is one attribute assignment:

    pattern.bedrock = LiveBedrockAgentRuntime(...)

Nothing in ``agentorch`` is edited, subclassed, or monkey-patched. P1
still calls ``self.bedrock.invoke_agent(...)`` and still composes plan,
fan-out and synthesis; P2 still chains its stages. The only difference is
that the object behind the seam reaches Amazon Bedrock instead of
returning a synthetic completion.

WHAT THIS DOES AND DOES NOT SHOW. It shows that the released P1 and P2
modules execute against a live hyperscaler agent runtime. It is NOT a
timing arm: the released ``Pattern._parallel`` runs fan-out branches
sequentially and accounts only ``max`` of their durations, which is
correct for the virtual clock of the deterministic study but means
wall-clock latency here is not comparable to the anchor's. Latency from
this agent is therefore recorded but explicitly not reported as a
measurement of P1's fan-out.

Redaction is enforced at the boundary, as elsewhere: completion text is
consumed inside the runtime and never returned.
"""
import os
import time
import uuid

import boto3
from bedrock_agentcore.runtime import BedrockAgentCoreApp

from agentorch.clients.context import CallContext
from agentorch.config import load_config
from agentorch.domain import WorkItem
from agentorch.patterns.p1_supervisor import SupervisorPattern
from agentorch.patterns.p2_pipeline import PipelinePattern
from agentorch.telemetry import TelemetrySink
from agentorch.types import Platform, ScenarioId

app = BedrockAgentCoreApp()

PATTERN = os.environ.get("ANCHOR_PATTERN", "P2").upper()
MODEL_ID = os.environ.get("ANCHOR_MODEL_ID", "us.amazon.nova-micro-v1:0")
MODEL_REGION = os.environ.get("ANCHOR_MODEL_REGION",
                              os.environ.get("AWS_REGION", "us-east-1"))

_CFG = load_config()
_client = boto3.client("bedrock-runtime", region_name=MODEL_REGION)


class LiveBedrockAgentRuntime:
    """Live implementation of the seam ``MockBedrockAgentRuntime`` defines.

    Same method, same argument names, same return shape. The released
    patterns cannot tell the difference, which is the point.
    """

    def __init__(self):
        self.invocations = 0
        self.tokens_in = 0
        self.tokens_out = 0

    def invoke_agent(self, agentId: str, agentAliasId: str, sessionId: str,
                     inputText: str) -> dict:
        resp = _client.converse(
            modelId=MODEL_ID,
            # agentId carries the released module's own role label
            # ("supervisor", "collab-0", "agent-draft"), so the live call
            # preserves the role structure the pattern expresses.
            messages=[{"role": "user",
                       "content": [{"text": f"[{agentId}] {inputText}"}]}],
            inferenceConfig={"maxTokens": 200, "temperature": 0.2},
        )
        usage = resp.get("usage", {})
        self.invocations += 1
        self.tokens_in += int(usage.get("inputTokens", 0))
        self.tokens_out += int(usage.get("outputTokens", 0))
        text = resp["output"]["message"]["content"][0]["text"]
        return {"completion": text, "sessionId": sessionId}


def _build_pattern():
    ctx = CallContext.build(_CFG, sink=TelemetrySink(),
                            stream_prefix=f"{PATTERN}:bedrock:S1:live")
    cls = SupervisorPattern if PATTERN == "P1" else PipelinePattern
    pat = cls(Platform.BEDROCK, ctx, _CFG)
    live = LiveBedrockAgentRuntime()
    pat.bedrock = live          # <-- the entire swap, per Section V-A
    return pat, live


@app.entrypoint
def handler(payload, context=None):
    task = str(payload.get("task", ""))
    want = str(payload.get("pattern", PATTERN)).upper()
    if want != PATTERN:
        return {"pattern": PATTERN, "status": f"error:pattern_mismatch:{want}",
                "invocations": None, "tokens_in": None, "tokens_out": None}
    t0 = time.perf_counter()
    try:
        pat, live = _build_pattern()
        item = WorkItem(id=f"live-{uuid.uuid4().hex[:8]}",
                        scenario=ScenarioId.S1,
                        payload={"task": task, "steps": 1})
        result, service_time_s = pat.run(item)
        return {
            "pattern": PATTERN,
            "status": "ok" if result.status == "ok" else f"pattern:{result.status}",
            "released_module": type(pat).__module__,
            "released_class": type(pat).__name__,
            "pattern_name": pat.pattern_name,
            "result_status": result.status,
            # Invocation count comes from the LIVE client, so it counts
            # real Converse calls rather than the mock's accounting.
            "invocations": live.invocations,
            "tokens_in": live.tokens_in,
            "tokens_out": live.tokens_out,
            # Recorded, but not a timing measurement -- see module docstring.
            "in_runtime_wall_s": time.perf_counter() - t0,
            "virtual_service_time_s": service_time_s,
            "n_collaborators": result.payload.get("n_collaborators"),
            "n_steps": result.payload.get("n_steps"),
        }
    except Exception as exc:
        return {"pattern": PATTERN, "status": f"error:{type(exc).__name__}",
                "detail": str(exc)[:200],
                "invocations": None, "tokens_in": None, "tokens_out": None}


if __name__ == "__main__":
    app.run()
