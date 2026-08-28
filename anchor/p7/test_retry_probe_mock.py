"""Offline state-machine test for retry_probe.py (conditions C3/C4).

Simulates Salesforce (token, platform-event publish, CometD long-poll with
replay semantics) and, critically, the AWS SDK's transient-error retry:
attempt 1 runs the agent's cold path, exceeds the client read timeout and
raises ReadTimeoutError; the SDK reissues; attempt 2 hits the agent's warm
path and returns. The fake agent mirrors agent_retry/agent_app.py's entry,
execution and ingress semantics.

This keeps the C3/C4 control flow and metrics testable WITHOUT touching
live services or credentials. Not part of the released artifact.
"""
import hashlib
import importlib.util
import io
import json
import os
import sys
import types
from pathlib import Path

from botocore.exceptions import ReadTimeoutError

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))

import test_bridge_probe_mock as mock  # noqa: E402  (reuse the Salesforce fake)


class FakeAgent:
    """In-process mirror of anchor/p7/agent_retry/agent_app.py."""

    def __init__(self):
        self.entries, self.executions, self.results, self.warm = {}, {}, {}, set()
        self.worker_id = "fakeworker01"

    def handle(self, p):
        """Returns (response dict, seconds the work took)."""
        key = p.get("idem_key") or p["task_id"]
        ingress_on = p.get("ingress") == "on"
        self.entries[key] = self.entries.get(key, 0) + 1
        entry_count = self.entries[key]

        if ingress_on and key in self.results:
            return ({"task_id": p["task_id"], "seq": p["seq"],
                     "digest": self.results[key], "entry_count": entry_count,
                     "executed": False, "executions": self.executions[key],
                     "worker_id": self.worker_id, "ingress": "on",
                     "suppressed_by": "memoized"}, 0.0)

        took = float(p.get("warm_delay_s", 0.0)) if key in self.warm \
            else float(p.get("delay_s", 0.0))
        self.warm.add(key)
        digest = hashlib.sha256(
            f"{p['task_id']}:{p['seq']}".encode()).hexdigest()[:16]
        self.executions[key] = self.executions.get(key, 0) + 1
        if ingress_on:
            self.results[key] = digest
        return ({"task_id": p["task_id"], "seq": p["seq"], "digest": digest,
                 "entry_count": entry_count, "executed": True,
                 "executions": self.executions[key],
                 "worker_id": self.worker_id,
                 "ingress": "on" if ingress_on else "off",
                 "suppressed_by": None}, took)


class FakeEvents:
    def __init__(self):
        self.handlers = []

    def register(self, name, handler):
        self.handlers.append(handler)

    def fire(self):
        for h in self.handlers:
            h()


class FakeBotoClient:
    """Implements the SDK behaviour under test: retry on read timeout."""

    def __init__(self, agent, read_timeout, max_attempts):
        self.agent = agent
        self.read_timeout = read_timeout
        self.max_attempts = max_attempts
        self.meta = types.SimpleNamespace(events=FakeEvents())

    def invoke_agent_runtime(self, agentRuntimeArn, runtimeSessionId, payload):
        p = json.loads(payload.decode())
        last = None
        for _ in range(self.max_attempts):
            self.meta.events.fire()          # botocore's before-send
            resp, took = self.agent.handle(p)
            if took > self.read_timeout:
                # The work DID run; only the response failed to arrive in
                # time. That is the whole at-least-once hazard.
                last = ReadTimeoutError(endpoint_url="https://fake")
                continue
            return {"statusCode": 200,
                    "response": io.BytesIO(json.dumps(resp).encode())}
        raise last


def load_retry_probe(agent, cfg):
    # bridge_probe must be loaded WITH the Salesforce fakes in place before
    # retry_probe imports names out of it.
    spec = importlib.util.spec_from_file_location(
        "bridge_probe", HERE / "bridge_probe.py")
    bp = importlib.util.module_from_spec(spec)
    sys.modules["bridge_probe"] = bp
    spec.loader.exec_module(bp)

    class FakeSession:
        def post(self, *a, **k):
            return mock.fake_post(*a, **k)

        def close(self):
            pass

    bp.requests = types.SimpleNamespace(post=mock.fake_post,
                                        Session=FakeSession)
    bp.time.sleep = lambda *_: None

    spec2 = importlib.util.spec_from_file_location(
        "rp", HERE / "retry_probe.py")
    rp = importlib.util.module_from_spec(spec2)
    sys.modules["rp"] = rp
    spec2.loader.exec_module(rp)
    rp.boto3 = types.SimpleNamespace(
        client=lambda *a, **k: FakeBotoClient(
            agent, cfg["client_read_timeout_s"], cfg["sdk_max_attempts"]))
    rp.time.sleep = lambda *_: None
    return rp


def main():
    os.environ.update(SF_MYDOMAIN="https://x", SF_CLIENT_ID="i",
                      SF_CLIENT_SECRET="s")
    cfg = {"n_tasks": 30, "aws_region": "us-east-1",
           "retry_agent_runtime_arn": "arn:test",
           "client_read_timeout_s": 5, "sdk_max_attempts": 3,
           "agent_cold_delay_s": 12, "agent_warm_delay_s": 0,
           "idle_seconds_to_finish": 0.2, "max_run_seconds": 120,
           "resubscribe_after_seconds": 150,
           "results_dir": str(HERE / "mockresults")}

    rp = load_retry_probe(FakeAgent(), cfg)
    c3 = rp.run_probe(cfg, False, "C3")
    mock.EVENTS.clear(); mock.SESSIONS.clear()

    rp = load_retry_probe(FakeAgent(), cfg)
    c4 = rp.run_probe(cfg, True, "C4")

    print("\n=== ASSERTIONS ===")
    ok = True
    for name, cond in [
        # The CRM direction must contribute nothing, or attribution fails.
        ("C3 redeliveries == 0", c3["redeliveries_observed"] == 0),
        ("C4 redeliveries == 0", c4["redeliveries_observed"] == 0),
        ("C3 logical calls == 30", c3["logical_calls"] == 30),
        ("C4 logical calls == 30", c4["logical_calls"] == 30),
        # The retry fired on the wire in both conditions ...
        ("C3 every call retried", c3["calls_with_sdk_retry"] == 30),
        ("C4 every call retried", c4["calls_with_sdk_retry"] == 30),
        ("C3 wire attempts > logical calls",
         c3["wire_attempts_total"] > c3["logical_calls"]),
        ("C3 agent entered twice per task", c3["agent_entries_gt_1"] == 30),
        ("C4 agent entered twice per task", c4["agent_entries_gt_1"] == 30),
        # ... and only the agent-side ingress changes the outcome.
        ("C3 duplicate agent executions == 30",
         c3["duplicate_agent_executions"] == 30),
        ("C4 duplicate agent executions == 0",
         c4["duplicate_agent_executions"] == 0),
        ("C3 bridge ingress was on", c3["bridge_ingress"] == "on"),
        ("C4 bridge ingress was on", c4["bridge_ingress"] == "on"),
    ]:
        print(f"  {'PASS' if cond else 'FAIL'}  {name}")
        ok = ok and cond
    print("ALL PASS" if ok else "FAILURES PRESENT")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
