"""AgentCore Runtime agent for the managed-runtime latency anchor (R1-1).

One image, deployed TWICE as two single-pattern agents. Which pattern a
deployment serves is fixed at deploy time by the ``ANCHOR_PATTERN``
environment variable, so each runtime really is one agent implementing
one pattern, not a dispatcher: a payload asking for the other pattern is
refused rather than served.

  ANCHOR_PATTERN=P1  Supervisor: plan -> parallel collaborator fan-out ->
                     synthesis, each step one Converse call.
  ANCHOR_PATTERN=P2  Pipeline on S1: a single stage = one Converse call.

The call sequences are the same ones ``anchor/live_bedrock.py`` issues
directly from the client, so the only difference between the two anchor
paths is WHERE the orchestration runs: inside the vendor's managed agent
runtime, or in the harness process. That is the whole point of this
agent -- it lets Section VI-G time a managed agent runtime rather than a
bare model call.

Redaction is enforced here, at the boundary: the handler returns timings,
invocation counts and token counts only. Completion text never leaves the
runtime.
"""
import concurrent.futures
import os
import time

import boto3
from bedrock_agentcore.runtime import BedrockAgentCoreApp

app = BedrockAgentCoreApp()

PATTERN = os.environ.get("ANCHOR_PATTERN", "P2").upper()
MODEL_ID = os.environ.get("ANCHOR_MODEL_ID", "us.amazon.nova-micro-v1:0")
# The runtime calls the model in its own region; the harness records the
# region on both sides so Section VI-G can state them without inference.
MODEL_REGION = os.environ.get("ANCHOR_MODEL_REGION",
                              os.environ.get("AWS_REGION", "us-east-1"))
N_COLLABORATORS = int(os.environ.get("ANCHOR_N_COLLABORATORS", "3"))

# Verbatim from anchor/live_bedrock.py -- the managed-runtime arm must
# issue the same prompts as the direct arm or the two are not comparable.
_ROLE_PROMPTS = {
    "plan": "You are a supervisor agent. Decompose this task into two "
            "subtasks, one line each, no preamble: ",
    "work": "You are a specialist collaborator. Answer briefly (max 3 "
            "sentences): ",
    "synthesize": "You are a supervisor agent. Combine into one final "
                  "answer, max 3 sentences: ",
    "stage": "Answer briefly (max 3 sentences): ",
}

_client = boto3.client("bedrock-runtime", region_name=MODEL_REGION)


def _converse(role, text):
    """One real Converse call. Returns redacted metrics only."""
    t0 = time.perf_counter()
    resp = _client.converse(
        modelId=MODEL_ID,
        messages=[{"role": "user",
                   "content": [{"text": _ROLE_PROMPTS[role] + text}]}],
        inferenceConfig={"maxTokens": 200, "temperature": 0.2},
    )
    usage = resp.get("usage", {})
    return {"latency_s": time.perf_counter() - t0, "invocations": 1,
            "tokens_in": int(usage.get("inputTokens", 0)),
            "tokens_out": int(usage.get("outputTokens", 0)),
            "status": "ok"}


def _run_p2(task):
    r = _converse("stage", task)
    return {"pattern": "P2", **r}


def _run_p1(task):
    plan = _converse("plan", task)
    with concurrent.futures.ThreadPoolExecutor(
            max_workers=N_COLLABORATORS) as ex:
        branch = list(ex.map(lambda _: _converse("work", task),
                             range(N_COLLABORATORS)))
    syn = _converse("synthesize", task)
    parts = [plan, *branch, syn]
    # Critical path: plan, then the slowest parallel branch, then synthesis.
    latency = (plan["latency_s"] + max(b["latency_s"] for b in branch)
               + syn["latency_s"])
    return {"pattern": "P1", "latency_s": latency,
            "invocations": sum(p["invocations"] for p in parts),
            "tokens_in": sum(p["tokens_in"] for p in parts),
            "tokens_out": sum(p["tokens_out"] for p in parts),
            "status": "ok" if all(p["status"] == "ok" for p in parts)
                      else "partial"}


@app.entrypoint
def handler(payload, context=None):
    """Serve one anchor request.

    ``in_runtime_latency_s`` is the orchestration time measured INSIDE the
    runtime. The harness separately records end-to-end client latency, so
    the difference is the managed runtime's own transport and scheduling
    overhead -- reported, never subtracted out.
    """
    t0 = time.perf_counter()
    task = str(payload.get("task", ""))
    want = str(payload.get("pattern", PATTERN)).upper()
    if want != PATTERN:
        # Single-pattern agent: refuse rather than quietly serve the other
        # pattern, so a mislabelled record cannot enter the results.
        return {"pattern": PATTERN, "status": f"error:pattern_mismatch:{want}",
                "latency_s": None, "invocations": None,
                "tokens_in": None, "tokens_out": None}
    try:
        out = _run_p1(task) if PATTERN == "P1" else _run_p2(task)
    except Exception as exc:                       # recorded, never invented
        return {"pattern": PATTERN, "status": f"error:{type(exc).__name__}",
                "latency_s": None, "invocations": None,
                "tokens_in": None, "tokens_out": None}
    out["in_runtime_latency_s"] = time.perf_counter() - t0
    out["model_region"] = MODEL_REGION
    out["model_id"] = MODEL_ID
    out["n_collaborators"] = N_COLLABORATORS if PATTERN == "P1" else None
    return out


if __name__ == "__main__":
    app.run()
