"""Demonstrate that the RELEASED pattern modules run on a live agent runtime.

Reviewer R2.2 asked for proof that the reference implementations "actually
deploy and function on real Agentforce 360 / Bedrock". The anchor of
Section VI-G answers the latency question with hand-written agents; this
answers the deployability question with the released modules themselves,
executing inside Bedrock AgentCore Runtime behind the documented client
seam.

Deliberately NOT part of run_anchor.py. That is a timing harness, and
these records are not timing measurements: the released
``Pattern._parallel`` runs fan-out branches sequentially and accounts only
``max`` of their durations, which is correct under the study's virtual
clock but makes wall-clock here incomparable to the anchor. Keeping the
two in separate files keeps a reader from combining them by accident.

What IS asserted is structural: the deployed P1 issues five live model
invocations per request and P2 issues one, from the released modules'
own control flow, and each response names the module and class that ran.

Usage:
    python anchor/agentcore/run_released_check.py [--n 30]
"""
from __future__ import annotations

import argparse
import json
import time
import uuid
from pathlib import Path

import boto3
from botocore.config import Config

HERE = Path(__file__).resolve().parent
RESULTS = HERE.parent / "results"
RUNTIMES = HERE / "runtimes_released.json"

_S1_BANK = (
    "What is the refund policy for order {k}?",
    "Summarize account {k} renewal terms.",
    "Which plan covers feature {k}?",
    "What is the SLA for ticket class {k}?",
)


def _task(i: int) -> str:
    return _S1_BANK[i % len(_S1_BANK)].format(k=1000 + i)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=30)
    a = ap.parse_args(argv)

    rt = json.loads(RUNTIMES.read_text())
    client = boto3.client("bedrock-agentcore", region_name=rt["region"],
                          config=Config(read_timeout=300, connect_timeout=15,
                                        retries={"mode": "standard",
                                                 "max_attempts": 3}))
    RESULTS.mkdir(parents=True, exist_ok=True)
    summary = {"scenario": "S1", "n_requests": a.n,
               "purpose": "released-module deployability check, not a timing arm",
               "patterns": {}}

    for pat, arn in rt["runtimes"].items():
        recs = []
        for i in range(a.n):
            t0 = time.time()
            try:
                resp = client.invoke_agent_runtime(
                    agentRuntimeArn=arn,
                    runtimeSessionId=f"rel-{uuid.uuid4().hex}{uuid.uuid4().hex}"[:64],
                    payload=json.dumps({"task": _task(i), "pattern": pat}).encode())
                body = resp["response"].read()
                r = json.loads(body) if body else {}
            except Exception as exc:
                r = {"status": f"error:{type(exc).__name__}"}
            r["client_latency_s"] = round(time.time() - t0, 4)
            recs.append(r)
            print(f"[{pat}] {i+1}/{a.n} status={r.get('status')} "
                  f"invocations={r.get('invocations')} "
                  f"module={r.get('released_module')}", flush=True)
        with open(RESULTS / f"released_{pat}.jsonl", "w") as f:
            for r in recs:
                f.write(json.dumps(r) + "\n")
        ok = [r for r in recs if r.get("status") == "ok"]
        invs = sorted({r["invocations"] for r in ok if r.get("invocations") is not None})
        summary["patterns"][pat] = {
            "n_ok": len(ok), "n_total": len(recs),
            "live_invocations_per_request": invs,
            "released_module": next((r.get("released_module") for r in ok), None),
            "released_class": next((r.get("released_class") for r in ok), None),
            "pattern_name": next((r.get("pattern_name") for r in ok), None),
            "result_statuses": sorted({r.get("result_status") for r in ok}),
            "error_statuses": sorted({r.get("status") for r in recs
                                      if r.get("status") != "ok"}),
        }

    # Structural expectations, asserted rather than assumed: five live model
    # invocations for the supervisor fan-out, one for the single-stage
    # pipeline, straight from the released modules' control flow.
    exp = {"P1": [5], "P2": [1]}
    summary["structure_as_expected"] = all(
        summary["patterns"].get(p, {}).get("live_invocations_per_request") == v
        for p, v in exp.items())
    (RESULTS / "released_module_check.json").write_text(
        json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))
    return 0 if summary["structure_as_expected"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
