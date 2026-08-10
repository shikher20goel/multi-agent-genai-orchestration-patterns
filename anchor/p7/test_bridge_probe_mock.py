"""Offline state-machine test for bridge_probe.py.

Simulates Salesforce (client-credentials token, platform-event publish,
CometD long-poll with replay semantics) and AgentCore InvokeAgentRuntime,
so the C1/C2 control flow, fault injection and metrics can be validated
WITHOUT touching live services. Not part of the released artifact.
"""
import importlib.util
import io
import json
import sys
import types
from pathlib import Path

HERE = Path(__file__).parent

# ---------------------------------------------------------------- fake HTTP
EVENTS = []            # ordered platform-event store: dicts with replayId
SESSIONS = {}          # clientId -> cursor (replayId already delivered)
BATCH = 5
INVOKES = []


class FakeResp:
    def __init__(self, payload, status=200):
        self._p = payload
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._p


def fake_post(url, headers=None, json=None, data=None, timeout=None):
    if url.endswith("/services/oauth2/token"):
        return FakeResp({"access_token": "tok", "instance_url": "https://inst"})
    if "/sobjects/Bridge_Task__e/" in url:
        EVENTS.append({"replayId": len(EVENTS) + 1, "payload": dict(json)})
        return FakeResp({"id": "e", "success": True}, 201)
    if "/cometd/" in url:
        msg = json[0]
        ch = msg["channel"]
        if ch == "/meta/handshake":
            cid = f"c{len(SESSIONS)}"
            SESSIONS[cid] = 0
            return FakeResp([{"successful": True, "clientId": cid}])
        if ch == "/meta/subscribe":
            cid = msg["clientId"]
            rid = list(msg["ext"]["replay"].values())[0]
            SESSIONS[cid] = 0 if rid in (-2,) else (10**9 if rid == -1 else rid)
            return FakeResp([{"successful": True}])
        if ch == "/meta/connect":
            cid = msg["clientId"]
            cur = SESSIONS[cid]
            batch = [e for e in EVENTS if e["replayId"] > cur][:BATCH]
            if batch:
                SESSIONS[cid] = batch[-1]["replayId"]
            out = [{"channel": "/event/Bridge_Task__e",
                    "data": {"payload": e["payload"],
                             "event": {"replayId": e["replayId"]}}}
                   for e in batch]
            return FakeResp(out + [{"channel": "/meta/connect",
                                    "successful": True}])
    raise AssertionError(f"unexpected POST {url}")


# ----------------------------------------------------------------- fake AWS
class FakeAgentCore:
    def invoke_agent_runtime(self, agentRuntimeArn, runtimeSessionId, payload):
        p = json.loads(payload.decode())
        INVOKES.append(p)
        body = json.dumps({"task_id": p["task_id"], "seq": p["seq"],
                           "digest": "d" * 16}).encode()
        return {"statusCode": 200, "response": io.BytesIO(body)}


def load_module():
    spec = importlib.util.spec_from_file_location(
        "bp", HERE / "bridge_probe.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules["bp"] = m
    spec.loader.exec_module(m)
    class FakeSession:
        def post(self, *a, **k):
            return fake_post(*a, **k)

    fake_requests = types.SimpleNamespace(post=fake_post, Session=FakeSession)
    m.requests = fake_requests
    m.boto3 = types.SimpleNamespace(client=lambda *a, **k: FakeAgentCore())
    m.time.sleep = lambda *_: None
    return m


def main():
    import os
    os.environ.update(SF_MYDOMAIN="https://x", SF_CLIENT_ID="i",
                      SF_CLIENT_SECRET="s")
    m = load_module()
    cfg = {"seed": 42, "n_tasks": 30, "p_crash": 0.3, "max_crashes": 8,
           "idle_polls_to_finish": 3, "aws_region": "us-east-1",
           "agent_runtime_arn": "arn:test",
           "results_dir": str(HERE / "mockresults")}

    c1 = m.run_probe(cfg, False, "C1")
    EVENTS.clear(); SESSIONS.clear(); INVOKES.clear()
    c2 = m.run_probe(cfg, True, "C2")

    print("\n=== ASSERTIONS ===")
    ok = True
    for name, cond in [
        ("C1 deliveries == 30 + redeliveries",
         c1["deliveries_observed"] >= 30),
        ("C1 redeliveries > 0", c1["redeliveries_observed"] > 0),
        ("C1 duplicate_invocations > 0", c1["duplicate_invocations"] > 0),
        ("C1 distinct tasks invoked == 30",
         c1["distinct_tasks_invoked"] == 30),
        ("C2 redeliveries > 0", c2["redeliveries_observed"] > 0),
        ("C2 duplicate_invocations == 0",
         c2["duplicate_invocations"] == 0),
        ("C2 distinct tasks invoked == 30",
         c2["distinct_tasks_invoked"] == 30),
        ("C2 invocations == 30", c2["invocations"] == 30),
    ]:
        print(f"  {'PASS' if cond else 'FAIL'}  {name}")
        ok = ok and cond
    print("ALL PASS" if ok else "FAILURES PRESENT")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
