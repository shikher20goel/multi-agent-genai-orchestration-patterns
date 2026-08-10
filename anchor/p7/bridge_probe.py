"""P7 live bridge probe — Access-2026-28862 resubmission extension.

Exhibits the dual-retry duplicate-delivery failure class on LIVE services
(Salesforce Platform Events -> bridge -> AgentCore Runtime) and its
elimination by P7's single idempotent ingress point.

Retry Domain A (Salesforce side): replay-based redelivery. The subscriber
records its replay cursor durably only AFTER invocation; an injected crash
between invocation and cursor persistence causes the LIVE Salesforce
replay mechanism to redeliver events on resume (at-least-once).

Retry Domain B (AWS side): documented AWS SDK auto-retry on transient
InvokeAgentRuntime errors (session-conflict 409 etc.).

Usage (inside the repo, after setup — see SF_SETUP.md / AWS_SETUP.md):
    python anchor/p7/bridge_probe.py --config anchor/p7/p7_config.yaml \
        --ingress off --run-label C1
    python anchor/p7/bridge_probe.py --config anchor/p7/p7_config.yaml \
        --ingress on  --run-label C2

Credentials come from environment only (never files):
  SF_MYDOMAIN, SF_CLIENT_ID, SF_CLIENT_SECRET  (client-credentials flow)
  AWS creds via standard boto3 chain (anchor-runner).
Per-request records are redacted: IDs, seq, timestamps, status only.
"""
import argparse
import json
import os
import random
import sys
import time
import uuid
from pathlib import Path

import boto3
import requests
import yaml

API_VERSION = "v61.0"


# ---------------------------------------------------------------- Salesforce
def sf_token(cfg):
    domain = os.environ["SF_MYDOMAIN"].rstrip("/")
    r = requests.post(
        f"{domain}/services/oauth2/token",
        data={
            "grant_type": "client_credentials",
            "client_id": os.environ["SF_CLIENT_ID"],
            "client_secret": os.environ["SF_CLIENT_SECRET"],
        },
        timeout=30,
    )
    r.raise_for_status()
    j = r.json()
    return j["access_token"], j["instance_url"]


def publish_tasks(inst, tok, n, run_label):
    """Publish n logical tasks as Bridge_Task__e platform events."""
    published = []
    for seq in range(1, n + 1):
        task_id = str(uuid.uuid4())
        r = requests.post(
            f"{inst}/services/data/{API_VERSION}/sobjects/Bridge_Task__e/",
            headers={"Authorization": f"Bearer {tok}"},
            json={"Task_Id__c": task_id, "Seq__c": seq,
                  "Run_Label__c": run_label},
            timeout=30,
        )
        r.raise_for_status()
        published.append({"task_id": task_id, "seq": seq,
                          "published_at": time.time()})
        time.sleep(0.2)
    return published


class CometdClient:
    """Minimal CometD (Bayeux) long-polling client with replay extension."""

    def __init__(self, inst, tok, refresh=None):
        self.url = f"{inst}/cometd/{API_VERSION.lstrip('v')}"
        # One HTTP session for the whole Bayeux conversation: Salesforce
        # returns a BAYEUX_BROWSER cookie at handshake and routes subsequent
        # /meta/* calls on it. Dropping the cookie yields 403::Unknown client
        # on subscribe even though the handshake succeeded.
        self.http = requests.Session()
        self.token = tok
        # The Salesforce Bayeux endpoint authenticates with the "OAuth"
        # scheme; "Bearer" is accepted by the REST endpoints but rejected
        # here (403::Handshake denied / 401::Authentication invalid).
        self.scheme = "OAuth"
        self.headers = {"Authorization": f"{self.scheme} {tok}",
                        "Content-Type": "application/json"}
        self.client_id = None
        self.msg_id = 0
        self.refresh = refresh

    def _post(self, body):
        self.msg_id += 1
        for m in body:
            m["id"] = str(self.msg_id)
        r = self.http.post(self.url, headers=self.headers, json=body,
                           timeout=125)
        if r.status_code == 401 and self.refresh is not None:
            # Client-credentials access tokens expire (~30 min) and a probe
            # run can outlive one. Re-fetch once and retry; this is transport
            # housekeeping only and does not touch delivery semantics.
            self.token = self.refresh()
            self.headers["Authorization"] = f"{self.scheme} {self.token}"
            r = self.http.post(self.url, headers=self.headers, json=body,
                               timeout=125)
        r.raise_for_status()
        return r.json()

    def handshake(self):
        last = None
        for scheme in ("OAuth", "Bearer"):
            self.scheme = scheme
            self.headers["Authorization"] = f"{scheme} {self.token}"
            out = self._post([{
                "channel": "/meta/handshake", "version": "1.0",
                "supportedConnectionTypes": ["long-polling"],
            }])
            if out[0].get("successful"):
                self.client_id = out[0]["clientId"]
                return
            last = out
        raise AssertionError(last)

    def subscribe(self, channel, replay_id):
        out = self._post([{
            "channel": "/meta/subscribe", "clientId": self.client_id,
            "subscription": channel,
            "ext": {"replay": {channel: replay_id}},
        }])
        assert out[0]["successful"], out

    def connect(self):
        """One long-poll cycle; returns delivered event messages."""
        out = self._post([{
            "channel": "/meta/connect", "clientId": self.client_id,
            "connectionType": "long-polling",
        }])
        return [m for m in out if not m["channel"].startswith("/meta/")]


# ----------------------------------------------------------------- AWS side
def invoke_agentcore(client, runtime_arn, task):
    """One live InvokeAgentRuntime call. SDK-level retries on transient
    errors are the documented AWS-side retry domain (left at defaults)."""
    t0 = time.time()
    resp = client.invoke_agent_runtime(
        agentRuntimeArn=runtime_arn,
        runtimeSessionId=f"p7-{task['task_id']}"[:100].ljust(33, "x"),
        payload=json.dumps({"task_id": task["task_id"],
                            "seq": task["seq"]}).encode(),
    )
    body = resp["response"].read() if hasattr(resp.get("response"), "read") \
        else resp.get("response")
    return {"latency_s": round(time.time() - t0, 4),
            "status": resp.get("statusCode", 200),
            "resp_digest": json.loads(body).get("digest")
            if body else None}


# -------------------------------------------------------------------- Probe
def run_probe(cfg, ingress_on, run_label):
    rng = random.Random(cfg["seed"])
    n = cfg["n_tasks"]
    p_crash = cfg["p_crash"]
    channel = "/event/Bridge_Task__e"

    tok, inst = sf_token(cfg)
    ac = boto3.client("bedrock-agentcore",
                      region_name=cfg["aws_region"])
    runtime_arn = cfg["agent_runtime_arn"]

    state_dir = Path(cfg["results_dir"]) / run_label
    state_dir.mkdir(parents=True, exist_ok=True)
    # Tasks are published BEFORE the subscriber attaches, so the subscription
    # must start from the beginning of the retention window (-2), not from
    # "new events only" (-1); -1 would deliver nothing. Events belonging to
    # other run labels are skipped and the cursor advanced past them.
    durable_replay = -2
    processed = set()            # idempotent-ingress dedupe store (durable
    processed_file = state_dir / "processed_ids.json"  # across crashes)
    invocations = []             # (task_id, seq, invoked_at, dup_flag)
    deliveries = []              # every delivery incl. redeliveries
    crashes = 0

    print(f"[{run_label}] publishing {n} tasks ...")
    published = publish_tasks(inst, tok, n, run_label)
    published_ids = {p["task_id"] for p in published}

    print(f"[{run_label}] subscribing (ingress="
          f"{'ON' if ingress_on else 'OFF'}) ...")
    def _refresh_token():
        nonlocal tok
        tok, _ = sf_token(cfg)
        return tok

    done = False
    while not done:
        c = CometdClient(inst, tok, refresh=_refresh_token)
        c.handshake()
        c.subscribe(channel, durable_replay)
        session_seen = 0
        idle_polls = 0
        while True:
            events = c.connect()
            if not events:
                idle_polls += 1
                if idle_polls >= cfg["idle_polls_to_finish"]:
                    done = True
                    break
                continue
            idle_polls = 0
            for ev in events:
                d = ev["data"]
                payload, replay = d["payload"], d["event"]["replayId"]
                if payload.get("Run_Label__c") != run_label:
                    durable_replay = replay
                    continue
                if payload["Task_Id__c"] not in published_ids:
                    # Same label, earlier attempt: still inside the retention
                    # window but not part of this run's request set. Skip and
                    # advance the cursor so reruns stay measurable.
                    durable_replay = replay
                    continue
                task = {"task_id": payload["Task_Id__c"],
                        "seq": int(payload["Seq__c"])}
                deliveries.append({**task, "replay_id": replay,
                                   "delivered_at": time.time()})
                dup = task["task_id"] in processed
                if ingress_on and dup:
                    # P7 mandate: idempotent ingress swallows the duplicate.
                    durable_replay = replay
                    continue
                res = invoke_agentcore(ac, runtime_arn, task)
                invocations.append({**task, **res,
                                    "duplicate": dup,
                                    "invoked_at": time.time()})
                processed.add(task["task_id"])
                processed_file.write_text(
                    json.dumps(sorted(processed)))
                session_seen += 1
                # FAULT INJECTION: crash AFTER invoke, BEFORE durable
                # cursor update -> live Salesforce redelivery on resume.
                if rng.random() < p_crash and crashes < cfg["max_crashes"]:
                    crashes += 1
                    print(f"[{run_label}] injected crash #{crashes} "
                          f"(cursor stays at {durable_replay})")
                    break  # abandon CometD session; cursor NOT advanced
                durable_replay = replay
            else:
                continue
            break  # crashed: re-handshake from durable_replay
        if not done and session_seen == 0 and crashes >= cfg["max_crashes"]:
            done = len({i["task_id"] for i in invocations}) >= n

    # ------------------------------------------------------------- Metrics
    inv_ids = [i["task_id"] for i in invocations]
    dup_invocations = len(inv_ids) - len(set(inv_ids))
    seq_order = [i["seq"] for i in invocations]
    inversions = sum(1 for a, b in zip(seq_order, seq_order[1:]) if a > b)
    summary = {
        "run_label": run_label,
        "ingress": "on" if ingress_on else "off",
        "n_tasks": n, "seed": cfg["seed"], "p_crash": p_crash,
        "published": len(published),
        "deliveries_observed": len(deliveries),
        "redeliveries_observed": len(deliveries) - len(
            {d["task_id"] for d in deliveries}),
        "injected_crashes": crashes,
        "invocations": len(invocations),
        "duplicate_invocations": dup_invocations,
        "ordering_inversions": inversions,
        "distinct_tasks_invoked": len(set(inv_ids)),
    }
    (state_dir / "summary.json").write_text(json.dumps(summary, indent=2))
    (state_dir / "invocations.json").write_text(
        json.dumps(invocations, indent=2))       # redacted: no payloads
    (state_dir / "deliveries.json").write_text(
        json.dumps(deliveries, indent=2))
    print(json.dumps(summary, indent=2))
    return summary


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--ingress", choices=["on", "off"], required=True)
    ap.add_argument("--run-label", required=True)
    a = ap.parse_args()
    cfg = yaml.safe_load(Path(a.config).read_text())
    for var in ("SF_MYDOMAIN", "SF_CLIENT_ID", "SF_CLIENT_SECRET"):
        if var not in os.environ:
            sys.exit(f"missing env var {var} (see SF_SETUP.md)")
    run_probe(cfg, a.ingress == "on", a.run_label)


if __name__ == "__main__":
    main()
