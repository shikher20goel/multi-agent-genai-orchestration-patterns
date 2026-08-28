"""Drive all seven released patterns on their live AgentCore runtimes.

Deliberately NOT part of run_anchor.py. That is a timing harness; these are
not timing measurements. The released ``Pattern._parallel`` runs fan-out
branches sequentially and accounts only ``max`` of their durations, which is
right under the study's virtual clock and makes wall-clock here incomparable
to the anchor's. Keeping the two in separate files stops a reader combining
them by accident.

What IS asserted is structural: each pattern's own control flow produces the
invocation and service-call counts frozen in
``tests/fixtures/pattern_signatures.json`` from the offline run.

Usage:
    python anchor/agentcore/run_all7.py --patterns P3,P4 --n 30
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
SIGNATURES = HERE.parent.parent / "tests" / "fixtures" / "pattern_signatures.json"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--patterns", default="P1,P2,P3,P4,P5,P6,P7")
    ap.add_argument("--n", type=int, default=30)
    ap.add_argument("--prefix", default="all7",
                    help="record filename prefix; MUST differ from an "
                         "existing committed record set")
    a = ap.parse_args(argv)

    rt = json.loads(RUNTIMES.read_text())
    sigs = json.loads(SIGNATURES.read_text())
    want = [p.strip().upper() for p in a.patterns.split(",") if p.strip()]

    missing = [p for p in want if p not in rt.get("runtimes", {})]
    if missing:
        raise SystemExit(f"no deployed runtime for {missing}; deploy first")

    client = boto3.client("bedrock-agentcore", region_name=rt["region"],
                          config=Config(read_timeout=900, connect_timeout=15,
                                        retries={"mode": "standard",
                                                 "max_attempts": 3}))
    RESULTS.mkdir(parents=True, exist_ok=True)
    summary = {"scenario": "S1", "n_requests": a.n,
               "purpose": "released-module deployability and structure across "
                          "all seven patterns; NOT a timing arm",
               "image_digest": rt.get("image_digest"),
               "patterns": {}}

    for pid in want:
        arn = rt["runtimes"][pid]
        recs = []
        for i in range(a.n):
            t0 = time.time()
            try:
                resp = client.invoke_agent_runtime(
                    agentRuntimeArn=arn,
                    runtimeSessionId=f"all7-{uuid.uuid4().hex}{uuid.uuid4().hex}"[:64],
                    payload=json.dumps({"pattern": pid, "seq": i}).encode())
                body = resp["response"].read()
                r = json.loads(body) if body else {}
            except Exception as exc:
                r = {"status": f"error:{type(exc).__name__}",
                     "detail": str(exc)[:200]}
            r["client_latency_s"] = round(time.time() - t0, 4)
            recs.append(r)
            print(f"[{pid}] {i+1}/{a.n} status={r.get('status')} "
                  f"inv={r.get('invocations')} svc={r.get('service_calls')} "
                  f"module={r.get('released_module')}", flush=True)

        out = RESULTS / f"{a.prefix}_{pid}.jsonl"
        if out.exists():
            raise SystemExit(f"REFUSING: {out} exists; committed records are "
                             f"append-only evidence. Use a different --prefix.")
        with open(out, "w") as f:
            for r in recs:
                f.write(json.dumps(r) + "\n")

        ok = [r for r in recs if r.get("status") == "ok"]
        expected = sigs.get(pid, {})
        observed = {
            "invocations": sorted({r.get("invocations") for r in ok}),
            "service_calls": sorted({r.get("service_calls") for r in ok}),
            "guardrails_applied": sorted({r.get("guardrails_applied") for r in ok}),
        }
        # P6 is expected to vary: a below-threshold item pauses and touches
        # memory, a confident one does not. Its signature is therefore a set,
        # not a constant, and forcing a single value would be wrong.
        matches = (pid == "P6" or all(
            observed[k] == [expected[k]] for k in expected if k in observed))
        summary["patterns"][pid] = {
            "n_ok": len(ok), "n_total": len(recs),
            "released_module": next((r.get("released_module") for r in ok), None),
            "released_class": next((r.get("released_class") for r in ok), None),
            "observed": observed,
            "expected_from_offline_fixture": expected,
            "signature_matches": matches,
            "backends_live": next((r.get("backends_live") for r in ok), None),
            "paused_for_human": sum(1 for r in ok if r.get("paused_for_human")),
            "error_statuses": sorted({r.get("status") for r in recs
                                      if r.get("status") != "ok"}),
        }

    summary["all_seven_ok"] = (
        len(summary["patterns"]) == 7
        and all(p["n_ok"] == p["n_total"] and p["signature_matches"]
                for p in summary["patterns"].values()))
    (RESULTS / f"{a.prefix}_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))
    return 0 if all(p["n_ok"] == p["n_total"]
                    for p in summary["patterns"].values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
