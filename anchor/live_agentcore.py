"""LIVE Amazon Bedrock AgentCore Runtime client for the anchor study.

WHY THIS EXISTS: the first anchor (anchor/live_bedrock.py) issued the
pattern call sequences from the harness process against the Converse API,
because Bedrock Agents "Classic" is closed to accounts without prior
service usage. That timed a model call rather than a managed agent
runtime. This client closes that gap: the SAME S1 request set is sent to
two agents deployed on Bedrock AgentCore Runtime -- P1's orchestration
(plan, parallel fan-out, synthesis) happens INSIDE the vendor's managed
runtime, and the harness only issues ``InvokeAgentRuntime`` and times it.

Each request gets a fresh runtimeSessionId, so a record is one full
managed-runtime invocation including whatever scheduling the platform
does; no attempt is made to reuse warm sessions or to subtract platform
overhead out of the number.

Returns redacted metrics only -- never completion text.
"""
from __future__ import annotations

import json
import time
import uuid

import boto3


class LiveAgentCore:
    """Drives one deployed single-pattern agent runtime per pattern."""

    def __init__(self, region: str, runtime_arns: dict, read_timeout: int = 300):
        from botocore.config import Config
        self._client = boto3.client(
            "bedrock-agentcore", region_name=region,
            config=Config(read_timeout=read_timeout, connect_timeout=15,
                          retries={"mode": "standard", "max_attempts": 3}))
        self._arns = dict(runtime_arns)

    @staticmethod
    def _session_id() -> str:
        # InvokeAgentRuntime requires >= 33 characters.
        return f"anchor-{uuid.uuid4().hex}{uuid.uuid4().hex}"[:64]

    def _invoke(self, pattern: str, task: str) -> dict:
        arn = self._arns[pattern]
        t0 = time.perf_counter()
        resp = self._client.invoke_agent_runtime(
            agentRuntimeArn=arn,
            runtimeSessionId=self._session_id(),
            payload=json.dumps({"task": task, "pattern": pattern}).encode(),
        )
        body = resp["response"].read() if hasattr(resp.get("response"), "read") \
            else resp.get("response")
        wall = time.perf_counter() - t0
        inner = json.loads(body) if body else {}
        # The agent's own status wins: a runtime that answered 200 while the
        # model call inside it failed is not an "ok" record.
        return {
            "pattern": pattern,
            "latency_s": wall,
            "in_runtime_latency_s": inner.get("in_runtime_latency_s"),
            "invocations": inner.get("invocations"),
            "tokens_in": inner.get("tokens_in"),
            "tokens_out": inner.get("tokens_out"),
            "http_status": resp.get("statusCode", 200),
            "status": inner.get("status", "error:empty_response"),
        }

    def run_p1(self, task: str, cfg: dict) -> dict:
        return self._invoke("P1", task)

    def run_p2(self, task: str, cfg: dict) -> dict:
        return self._invoke("P2", task)
