"""Smoke-test each live backend standalone, against the real service.

Every live method is proven alone before it is wired into a pattern. This is
not ceremony: the P7 retry probe's execution counter was wrong in a way that
UNDERSTATED duplicates, and it was caught exactly here rather than in a
recorded run.

Writes one record per backend under anchor/results/.
"""
from __future__ import annotations

import argparse
import json
import time
import uuid
from pathlib import Path

import boto3

HERE = Path(__file__).resolve().parent
RESULTS = HERE.parent / "results"
INVENTORY = HERE / "resources_all7.json"

import sys
sys.path.insert(0, str(HERE.parent.parent))
from anchor.agentcore.live_backends import (GatewayBackend,      # noqa: E402
                                            GuardrailBackend,
                                            MemoryBackend,
                                            ObservabilityBackend)


def smoke_memory(inv, region) -> dict:
    c = boto3.client("bedrock-agentcore", region_name=region)
    b = MemoryBackend(c, inv["memory"]["id"])
    key = f"smoke-{uuid.uuid4().hex[:8]}"
    value = [{"agent": "a", "note": 1}, {"agent": "b", "note": 2}]
    b.put(key, value)
    time.sleep(2)                     # eventual consistency on read-back
    got = b.get(key)
    missing = b.get(f"absent-{uuid.uuid4().hex[:8]}")
    b.put(key, value + [{"agent": "c", "note": 3}])
    time.sleep(2)
    over = b.get(key)
    return {"round_trip_equal": got == value,
            "missing_key_is_none": missing is None,
            "overwrite_reads_latest": over is not None and len(over) == 3,
            "round_trip_len": None if got is None else len(got)}


def smoke_gateway(inv, region) -> dict:
    c = boto3.client("bedrock-agentcore", region_name=region)
    b = GatewayBackend(c, inv["gateway"]["url"])
    out = []
    for tool in ("search", "lookup"):
        t0 = time.time()
        try:
            r = b.call(tool, {"item": "smoke"})
            out.append({"tool": tool, "ok": True,
                        "shape_ok": set(r) == {"tool", "result", "args"},
                        "latency_s": round(time.time() - t0, 4)})
        except Exception as exc:
            out.append({"tool": tool, "ok": False,
                        "error": f"{type(exc).__name__}: {str(exc)[:160]}"})
    return {"tools": out}


def smoke_observability(inv, region) -> dict:
    c = boto3.client("logs", region_name=region)
    stream = f"smoke-{uuid.uuid4().hex[:8]}"
    b = ObservabilityBackend(c, "/agentorch/all7/observability", stream)
    for i in range(3):
        b.emit({"event": "smoke", "item": f"i-{i}", "secret": "MUST NOT APPEAR"})
    time.sleep(5)
    r = c.get_log_events(logGroupName="/agentorch/all7/observability",
                         logStreamName=stream, startFromHead=True)
    msgs = [e["message"] for e in r.get("events", [])]
    return {"emitted": 3, "read_back": len(msgs),
            "redaction_holds": all("MUST NOT APPEAR" not in m for m in msgs),
            "sample": msgs[:1]}


def smoke_guardrails(inv, region) -> dict:
    c = boto3.client("bedrock-runtime", region_name=region)
    b = GuardrailBackend(c, inv["guardrail"]["id"],
                         inv["guardrail"].get("version", "DRAFT"))
    benign = b.apply("What is the refund policy for order 1000?", "shadow")
    spicy = b.apply("I will describe extreme graphic violence in detail.",
                    "shadow")
    return {"benign_blocked": benign["blocked"],
            "spicy_blocked": spicy["blocked"],
            "spicy_would_block": spicy.get("would_block"),
            "shadow_never_blocks": not benign["blocked"] and not spicy["blocked"]}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="memory,gateway,observability,guardrails")
    a = ap.parse_args(argv)
    inv = json.loads(INVENTORY.read_text())
    region = inv.get("region", "us-east-1")
    RESULTS.mkdir(parents=True, exist_ok=True)

    fns = {"memory": smoke_memory, "gateway": smoke_gateway,
           "observability": smoke_observability, "guardrails": smoke_guardrails}
    out, ok = {}, True
    for name in [x.strip() for x in a.only.split(",") if x.strip()]:
        try:
            out[name] = fns[name](inv, region)
            print(f"  {name:<14} {json.dumps(out[name])[:150]}")
        except Exception as exc:
            out[name] = {"error": f"{type(exc).__name__}: {str(exc)[:200]}"}
            ok = False
            print(f"  {name:<14} FAILED {out[name]['error']}")
    (RESULTS / "smoke_backends.json").write_text(json.dumps(out, indent=2) + "\n")
    print(f"\nwrote {RESULTS / 'smoke_backends.json'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
