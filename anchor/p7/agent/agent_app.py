"""Minimal AgentCore Runtime agent for the P7 live bridge probe.

Deterministic task processor: receives a bridge task, returns an
acknowledgment envelope. No model call by default (delivery-semantics
probe; see P7-PROBE-DESIGN.md). The agent is intentionally trivial —
the probe measures what crosses the bridge boundary, not what the
agent computes.
"""
import hashlib
import json
import os
import time

from bedrock_agentcore.runtime import BedrockAgentCoreApp

app = BedrockAgentCoreApp()

WITH_MODEL = os.environ.get("P7_WITH_MODEL", "0") == "1"  # OFF for recorded run


@app.entrypoint
def handler(payload, context=None):
    task_id = str(payload.get("task_id", ""))
    seq = payload.get("seq")
    received_at = time.time()
    # Deterministic transform: stable digest of the logical task identity.
    digest = hashlib.sha256(f"{task_id}:{seq}".encode()).hexdigest()[:16]
    return {
        "task_id": task_id,
        "seq": seq,
        "digest": digest,
        "received_at": received_at,
        "model_used": False,
    }


if __name__ == "__main__":
    app.run()
