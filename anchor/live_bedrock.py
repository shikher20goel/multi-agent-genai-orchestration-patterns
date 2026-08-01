"""Thin LIVE Amazon Bedrock client for the anchor study (Converse API).

WHY CONVERSE, NOT invoke_agent: Amazon Bedrock Agents "Classic" entered
maintenance mode and is closed to accounts without prior service usage
(new-customer cutoff July 30, 2026), so a fresh account cannot create the
managed agents the mock's ``invoke_agent`` mirror assumed. The anchor
therefore issues the pattern call sequences directly against the model
runtime via the documented ``bedrock-runtime`` Converse API. This remains
structurally faithful to the emulation: the mock models one agent
invocation as one model call behind a single boundary. An AgentCore-based
anchor (invoke_agent_runtime) is planned as follow-up work.

Only timing / invocation / token counts are returned - never completion
text (redaction).
"""
from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor

import boto3

DEFAULT_MODEL_ID = "us.amazon.nova-micro-v1:0"

_ROLE_PROMPTS = {
    "plan": "You are a supervisor agent. Decompose this task into two "
            "subtasks, one line each, no preamble: ",
    "work": "You are a specialist collaborator. Answer briefly (max 3 "
            "sentences): ",
    "synthesize": "You are a supervisor agent. Combine into one final "
                  "answer, max 3 sentences: ",
    "stage": "Answer briefly (max 3 sentences): ",
}


class LiveBedrock:
    def __init__(self, region: str, model_id: str = DEFAULT_MODEL_ID):
        self._client = boto3.client("bedrock-runtime", region_name=region)
        self._model_id = model_id

    def _converse(self, role: str, text: str) -> dict:
        """One real Converse call. Returns redacted metrics only."""
        t0 = time.perf_counter()
        resp = self._client.converse(
            modelId=self._model_id,
            messages=[{"role": "user",
                       "content": [{"text": _ROLE_PROMPTS[role] + text}]}],
            inferenceConfig={"maxTokens": 200, "temperature": 0.2},
        )
        usage = resp.get("usage", {})
        return {"latency_s": time.perf_counter() - t0, "invocations": 1,
                "tokens_in": int(usage.get("inputTokens", 0)),
                "tokens_out": int(usage.get("outputTokens", 0)),
                "status": "ok"}

    def run_p2(self, task: str, cfg: dict) -> dict:
        """P2 Pipeline on S1 = single stage = one model call."""
        r = self._converse("stage", task)
        return {"pattern": "P2", **r}

    def run_p1(self, task: str, cfg: dict) -> dict:
        """P1 Supervisor on S1 = plan + PARALLEL fan-out + synthesis."""
        n = int(cfg.get("n_collaborators", 2))
        plan = self._converse("plan", task)
        with ThreadPoolExecutor(max_workers=n) as ex:
            branch = list(ex.map(lambda _: self._converse("work", task),
                                 range(n)))
        syn = self._converse("synthesize", task)
        parts = [plan, *branch, syn]
        latency = (plan["latency_s"] + max(b["latency_s"] for b in branch)
                   + syn["latency_s"])
        return {"pattern": "P1", "latency_s": latency,
                "invocations": sum(p["invocations"] for p in parts),
                "tokens_in": sum(p["tokens_in"] for p in parts),
                "tokens_out": sum(p["tokens_out"] for p in parts),
                "status": "ok" if all(p["status"] == "ok" for p in parts)
                          else "partial"}
