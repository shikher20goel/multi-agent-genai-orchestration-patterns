"""AgentCore Runtime agent for P7 probe conditions C3/C4 (AWS-side retry).

C1/C2 exercised the CRM direction: live Salesforce replay redelivery
reaching the bridge twice. The AWS direction stayed armed but unfired, so
Section VI-H had to concede AgentCore-managed retry as an unexercised
surface. This agent makes that direction observable.

The measurement problem C1/C2 did not have: when the AWS SDK reissues
``InvokeAgentRuntime`` after a transient error, the bridge process never
sees a second call -- it made one. Counting invocations client-side, as
C1/C2 did, is therefore blind to this direction by construction. The
count has to come from inside the runtime, so this agent reports it:

  entry_count  how many times THIS agent was entered for the idempotency
               key (>1 means the platform delivered the reissued request)
  executions   how many times the work actually ran for that key
  worker_id    process identity, so "entered twice" can be distinguished
               from "entered once in each of two processes"

``ingress`` selects where P7's mandate is honoured:

  off  every entry executes -- the anti-pattern, and the mirror of C1
  on   an idempotent ingress AT THE TARGET BOUNDARY: the first entry for
       a key executes and memoizes; a concurrent second entry blocks on
       the first (single flight) and returns its result without
       re-executing.

An ingress inside the bridge process cannot suppress this direction at
all, because the duplicate is created below it. That is the point of the
condition, and why the ingress lives here rather than in the caller.

Redaction: task ids, sequence numbers, counters and timestamps only.
"""
import hashlib
import os
import threading
import time
import uuid

from bedrock_agentcore.runtime import BedrockAgentCoreApp

app = BedrockAgentCoreApp()

# Regenerated per process. If a reissued request lands on a different
# worker, in-process state cannot see it and the record must say so
# rather than silently reporting entry_count = 1.
WORKER_ID = uuid.uuid4().hex[:12]

_LOCK = threading.Lock()
_ENTRIES = {}        # idem key -> times this agent was entered
_EXECUTIONS = {}     # idem key -> times the work actually ran
_RESULTS = {}        # idem key -> memoized result (ingress on)
_INFLIGHT = {}       # idem key -> threading.Event, set when work completes
_WARM = set()        # idem keys whose work has run at least once here

DEFAULT_DELAY_S = float(os.environ.get("P7_RETRY_DELAY_S", "0"))


def _work(key, task_id, seq, delay_s, warm_delay_s):
    """The unit of work whose repetition is the thing being counted.

    Cold on a key, warm afterwards -- an ordinary property of real work,
    and here a deliberate one. The cold delay is what lets a client-side
    read timeout expire while the runtime is genuinely mid-request, so the
    SDK reissues; the warm path is what lets the reissued call finish
    inside the same timeout and carry the counters back to the harness.
    Without the asymmetry every attempt would time out and the duplicate
    execution -- which has already happened by then -- would be invisible
    from the client side. CloudWatch corroboration does not depend on it.

    The execution is counted HERE, where the work commits to running, and
    NOT on completion. Because the cold path is slow and the warm path is
    not, a reissued call routinely finishes BEFORE the call it duplicated;
    a completion-time counter reports 1 for what were two runs and so
    understates duplicates -- the one direction of error this probe must
    not have.
    """
    with _LOCK:
        warm = key in _WARM
        _WARM.add(key)
        _EXECUTIONS[key] = _EXECUTIONS.get(key, 0) + 1
        n = _EXECUTIONS[key]
    d = warm_delay_s if warm else delay_s
    if d > 0:
        time.sleep(d)
    return hashlib.sha256(f"{task_id}:{seq}".encode()).hexdigest()[:16], n


@app.entrypoint
def handler(payload, context=None):
    task_id = str(payload.get("task_id", ""))
    seq = payload.get("seq")
    key = str(payload.get("idem_key") or task_id)
    ingress_on = str(payload.get("ingress", "off")).lower() == "on"
    delay_s = float(payload.get("delay_s", DEFAULT_DELAY_S))
    warm_delay_s = float(payload.get("warm_delay_s", 0.0))
    entered_at = time.time()

    print(f"P7RETRY entry key={key} seq={seq} ingress={'on' if ingress_on else 'off'} worker={WORKER_ID} t={entered_at:.3f}",
          flush=True)
    with _LOCK:
        _ENTRIES[key] = _ENTRIES.get(key, 0) + 1
        entry_count = _ENTRIES[key]
        memo = _RESULTS.get(key) if ingress_on else None
        waiter = _INFLIGHT.get(key) if (ingress_on and memo is None) else None
        if ingress_on and memo is None and waiter is None:
            waiter = _INFLIGHT[key] = threading.Event()
            owner = True
        else:
            owner = False

    if ingress_on and memo is not None:
        # Duplicate suppressed after the first entry completed.
        return {"task_id": task_id, "seq": seq, "digest": memo,
                "entry_count": entry_count, "executed": False,
                "executions": _EXECUTIONS.get(key, 0),
                "worker_id": WORKER_ID, "ingress": "on",
                "suppressed_by": "memoized",
                "entered_at": entered_at, "completed_at": time.time()}

    if ingress_on and not owner:
        # Single flight: the first entry is still running. Wait for it
        # rather than starting the work a second time.
        waiter.wait(timeout=max(delay_s * 4, 30))
        return {"task_id": task_id, "seq": seq, "digest": _RESULTS.get(key),
                "entry_count": entry_count, "executed": False,
                "executions": _EXECUTIONS.get(key, 0),
                "worker_id": WORKER_ID, "ingress": "on",
                "suppressed_by": "single_flight",
                "entered_at": entered_at, "completed_at": time.time()}

    try:
        digest, executions = _work(key, task_id, seq, delay_s,
                                   warm_delay_s)
    except Exception as exc:
        if ingress_on and owner:
            with _LOCK:
                ev = _INFLIGHT.pop(key, None)
            if ev:
                ev.set()
        return {"task_id": task_id, "seq": seq,
                "status": f"error:{type(exc).__name__}",
                "entry_count": entry_count, "executed": False,
                "worker_id": WORKER_ID,
                "ingress": "on" if ingress_on else "off"}

    with _LOCK:
        if ingress_on:
            _RESULTS[key] = digest
            ev = _INFLIGHT.pop(key, None)
        else:
            ev = None
    if ev:
        ev.set()

    print(f"P7RETRY exec key={key} seq={seq} entry_count={entry_count} "
          f"executions={executions} worker={WORKER_ID}", flush=True)

    return {"task_id": task_id, "seq": seq, "digest": digest,
            "entry_count": entry_count, "executed": True,
            "executions": executions, "worker_id": WORKER_ID,
            "ingress": "on" if ingress_on else "off",
            "suppressed_by": None,
            "entered_at": entered_at, "completed_at": time.time()}


if __name__ == "__main__":
    app.run()
