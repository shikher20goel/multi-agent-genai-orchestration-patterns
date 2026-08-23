"""P7 probe conditions C3/C4 — the AWS-side retry direction.

C1/C2 (bridge_probe.py) exercised the CRM direction: live Salesforce
replay redelivery handed the bridge the same event twice, and P7's
idempotent ingress in the bridge suppressed the duplicate. The AWS
direction was armed at SDK defaults and never fired, so Section VI-H had
to record AgentCore-managed retry as an unexercised surface. This probe
exercises it, in the same bridge, as the mirror image.

WHAT IS HELD FIXED, AND WHAT VARIES
  * Same live bridge: Salesforce ``Bridge_Task__e`` -> CometD subscriber
    -> live ``InvokeAgentRuntime``.
  * NO crash is injected, so the CRM direction contributes nothing. The
    run asserts this rather than assuming it: deliveries == published and
    redeliveries == 0 are recorded, and any duplicate execution therefore
    has only one place it can have come from.
  * The bridge's own idempotent ingress is ON in BOTH conditions. It
    cannot suppress anything here, and showing that is half the point:
    the reissued request is created below the bridge, which made exactly
    one call. An ingress must sit at the target boundary to see it.
  * Only the agent-side ingress varies: C3 off, C4 on.

HOW THE RETRY IS BROUGHT INTO PLAY
The harness shortens the client read timeout below the agent's cold-path
work time. botocore classifies ``ReadTimeoutError`` as an
``HTTPClientError``, one of the transient exception classes its standard
retry mode retries, so the SDK reissues the request on its own. The fault
is a client timeout setting -- an ordinary deployment choice; the retry
decision, the reissued request and the second agent execution are the
platform's. Wire attempts are counted with a botocore ``before-send``
hook, so "the retry fired" is evidence, not inference.

Credentials from the environment only (SF_MYDOMAIN, SF_CLIENT_ID,
SF_CLIENT_SECRET; AWS via the standard boto3 chain). Records are
redacted: ids, sequence numbers, counters, timestamps, status.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import time
from pathlib import Path

import boto3
import yaml
from botocore.config import Config

sys.path.insert(0, str(Path(__file__).resolve().parent))
from bridge_probe import CometdClient, publish_tasks, sf_token  # noqa: E402

CHANNEL = "/event/Bridge_Task__e"


class AttemptCounter:
    """Counts HTTP sends per logical InvokeAgentRuntime call.

    botocore fires ``before-send`` once per wire attempt, so this counts
    the SDK's retries directly rather than inferring them from timing.
    """

    def __init__(self, client):
        self._local = threading.local()
        # Registered broadly rather than on a service-qualified event name:
        # the qualified form depends on how botocore slugs this service id,
        # and a hook that silently never fires would read as "no retries".
        # This client is single-purpose, so every send is an invocation.
        client.meta.events.register("before-send", self._on_send)

    def _on_send(self, **kwargs):
        self._local.n = getattr(self._local, "n", 0) + 1

    def reset(self):
        self._local.n = 0

    @property
    def count(self):
        return getattr(self._local, "n", 0)


def invoke_with_retry(client, counter, runtime_arn, task, ingress_on,
                      delay_s, warm_delay_s):
    """One logical call. The SDK may put it on the wire more than once."""
    counter.reset()
    t0 = time.time()
    payload = {"task_id": task["task_id"], "seq": task["seq"],
               "idem_key": task["task_id"],
               "ingress": "on" if ingress_on else "off",
               "delay_s": delay_s, "warm_delay_s": warm_delay_s}
    rec = {"task_id": task["task_id"], "seq": task["seq"],
           "agent_ingress": "on" if ingress_on else "off"}
    try:
        resp = client.invoke_agent_runtime(
            agentRuntimeArn=runtime_arn,
            runtimeSessionId=f"p7r-{task['task_id']}"[:100].ljust(33, "x"),
            payload=json.dumps(payload).encode(),
        )
        body = resp["response"].read() if hasattr(resp.get("response"), "read") \
            else resp.get("response")
        inner = json.loads(body) if body else {}
        rec.update({
            "status": "ok",
            "http_status": resp.get("statusCode", 200),
            "entry_count": inner.get("entry_count"),
            "executions": inner.get("executions"),
            "executed": inner.get("executed"),
            "suppressed_by": inner.get("suppressed_by"),
            "worker_id": inner.get("worker_id"),
        })
    except Exception as exc:
        # A logical call whose every attempt timed out still tells us the
        # retry fired; the agent-side counters then come from CloudWatch.
        rec.update({"status": f"error:{type(exc).__name__}",
                    "entry_count": None, "executions": None,
                    "executed": None, "suppressed_by": None,
                    "worker_id": None})
    rec["wire_attempts"] = counter.count
    rec["client_latency_s"] = round(time.time() - t0, 4)
    rec["invoked_at"] = t0
    return rec


def run_probe(cfg, agent_ingress_on, run_label):
    n = int(cfg["n_tasks"])
    read_timeout = float(cfg["client_read_timeout_s"])
    max_attempts = int(cfg["sdk_max_attempts"])
    delay_s = float(cfg["agent_cold_delay_s"])
    warm_delay_s = float(cfg.get("agent_warm_delay_s", 0.0))
    runtime_arn = cfg["retry_agent_runtime_arn"]

    tok, inst = sf_token(cfg)
    client = boto3.client(
        "bedrock-agentcore", region_name=cfg["aws_region"],
        config=Config(read_timeout=read_timeout, connect_timeout=10,
                      retries={"mode": "standard",
                               "max_attempts": max_attempts}))
    counter = AttemptCounter(client)

    state_dir = Path(cfg["results_dir"]) / run_label
    state_dir.mkdir(parents=True, exist_ok=True)

    processed = set()        # the BRIDGE's idempotent ingress, ON in C3 and C4
    invocations, deliveries = [], []
    skipped_foreign = skipped_stale = 0
    durable_replay = -2

    print(f"[{run_label}] publishing {n} tasks ...", flush=True)
    published = publish_tasks(inst, tok, n, run_label)
    published_ids = {p["task_id"] for p in published}

    def _refresh():
        nonlocal tok
        tok, _ = sf_token(cfg)
        return tok

    start_ts = time.time()
    last_event_at = time.time()
    idle_secs = float(cfg["idle_seconds_to_finish"])
    max_secs = float(cfg["max_run_seconds"])
    resub_secs = float(cfg.get("resubscribe_after_seconds", 150))
    timed_out = False
    done = False

    print(f"[{run_label}] subscribing (bridge ingress ON, agent ingress "
          f"{'ON' if agent_ingress_on else 'OFF'}) ...", flush=True)
    while not done:
        c = CometdClient(inst, tok, refresh=_refresh)
        c.handshake()
        c.subscribe(CHANNEL, durable_replay)
        session_progress_at = time.time()
        while True:
            events, meta = c.connect()
            if not meta.get("successful", True):
                print(f"[{run_label}] connect unsuccessful "
                      f"({meta.get('error')}) -> re-handshaking", flush=True)
                break
            if not events:
                print(f"[{run_label}] poll: 0 events "
                      f"(t+{int(time.time() - start_ts)}s, "
                      f"distinct={len(processed)}/{n})", flush=True)
                if (len(processed) >= n
                        and time.time() - last_event_at >= idle_secs):
                    done = True
                    break
                if time.time() - start_ts >= max_secs:
                    timed_out = True
                    done = True
                    break
                if (len(processed) < n
                        and time.time() - session_progress_at >= resub_secs):
                    print(f"[{run_label}] subscription starved -> "
                          f"re-establishing from {durable_replay}", flush=True)
                    break
                continue
            session_progress_at = last_event_at = time.time()
            for ev in events:
                d = ev["data"]
                payload, replay = d["payload"], d["event"]["replayId"]
                if payload.get("Run_Label__c") != run_label:
                    durable_replay = replay
                    skipped_foreign += 1
                    continue
                if payload["Task_Id__c"] not in published_ids:
                    durable_replay = replay
                    skipped_stale += 1
                    continue
                task = {"task_id": payload["Task_Id__c"],
                        "seq": int(payload["Seq__c"])}
                deliveries.append({**task, "replay_id": replay,
                                   "delivered_at": time.time()})
                if task["task_id"] in processed:
                    # Bridge-side ingress, ON in both conditions. It never
                    # fires here (no crash is injected); that it cannot fire
                    # for an SDK-reissued request is the point.
                    durable_replay = replay
                    continue
                rec = invoke_with_retry(client, counter, runtime_arn, task,
                                        agent_ingress_on, delay_s,
                                        warm_delay_s)
                invocations.append(rec)
                processed.add(task["task_id"])
                durable_replay = replay
                print(f"[{run_label}] seq={task['seq']} "
                      f"wire_attempts={rec['wire_attempts']} "
                      f"entry_count={rec['entry_count']} "
                      f"executions={rec['executions']} "
                      f"status={rec['status']} "
                      f"distinct={len(processed)}/{n}", flush=True)
        c.disconnect()

    ok = [r for r in invocations if r["status"] == "ok"]
    retried = [r for r in invocations if r["wire_attempts"] > 1]
    dup_exec = [r for r in ok if (r.get("executions") or 0) > 1]
    multi_entry = [r for r in ok if (r.get("entry_count") or 0) > 1]
    workers = sorted({r["worker_id"] for r in ok if r.get("worker_id")})
    summary = {
        "run_label": run_label,
        "bridge_ingress": "on",
        "agent_ingress": "on" if agent_ingress_on else "off",
        "n_tasks": n,
        "client_read_timeout_s": read_timeout,
        "sdk_retry_mode": "standard",
        "sdk_max_attempts": max_attempts,
        "agent_cold_delay_s": delay_s,
        "agent_warm_delay_s": warm_delay_s,
        "published": len(published),
        "deliveries_observed": len(deliveries),
        "redeliveries_observed": len(deliveries) - len(
            {d["task_id"] for d in deliveries}),
        "injected_crashes": 0,
        "skipped_foreign_label": skipped_foreign,
        "skipped_stale_attempt": skipped_stale,
        "logical_calls": len(invocations),
        "calls_ok": len(ok),
        "wire_attempts_total": sum(r["wire_attempts"] for r in invocations),
        "calls_with_sdk_retry": len(retried),
        "agent_entries_gt_1": len(multi_entry),
        "duplicate_agent_executions": len(dup_exec),
        "distinct_worker_ids": workers,
        "timed_out": timed_out,
        "wall_seconds": round(time.time() - start_ts, 1),
    }
    (state_dir / "summary.json").write_text(json.dumps(summary, indent=2))
    (state_dir / "invocations.json").write_text(json.dumps(invocations, indent=2))
    (state_dir / "deliveries.json").write_text(json.dumps(deliveries, indent=2))
    print(json.dumps(summary, indent=2))
    return summary


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--agent-ingress", choices=["on", "off"], required=True)
    ap.add_argument("--run-label", required=True)
    a = ap.parse_args()
    cfg = yaml.safe_load(Path(a.config).read_text())
    for var in ("SF_MYDOMAIN", "SF_CLIENT_ID", "SF_CLIENT_SECRET"):
        if var not in os.environ:
            sys.exit(f"missing env var {var} (see SETUP-NOTES.md)")
    if not str(cfg.get("retry_agent_runtime_arn", "")).startswith("arn:"):
        sys.exit("retry_agent_runtime_arn is unset - run "
                 "anchor/p7/deploy_retry_agent.py first")
    if cfg["agent_cold_delay_s"] <= cfg["client_read_timeout_s"]:
        # Otherwise attempt 1 completes inside the timeout, the SDK never
        # reissues, and the run would quietly measure nothing.
        sys.exit("agent_cold_delay_s must exceed client_read_timeout_s for "
                 "the SDK retry path to be reached")
    run_probe(cfg, a.agent_ingress == "on", a.run_label)


if __name__ == "__main__":
    main()
