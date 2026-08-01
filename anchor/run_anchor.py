"""Run the live-endpoint anchor (reviewer R1-1 / R2-2).

Issues the S1 baseline request set against live Bedrock and/or Agentforce
for P1 and P2, and writes REDACTED per-request records plus an aggregate
summary. No number is fabricated: if a platform is disabled or a run
fails, that is recorded honestly and compare_anchor.py will not invent it.
"""
from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path

import yaml

RESULTS = Path(__file__).resolve().parent / "results"
_S1_BANK = (
    "What is the refund policy for order {k}?",
    "Summarize account {k} renewal terms.",
    "Which plan covers feature {k}?",
    "What is the SLA for ticket class {k}?",
)


def _s1_task(i: int) -> str:
    return _S1_BANK[i % len(_S1_BANK)].format(k=1000 + i)


def _n_collaborators() -> int:
    try:
        from agentorch.config import load_config
        return int(load_config().patterns.p1.n_collaborators)
    except Exception:
        return 2


def _run_platform(name: str, runner, pcfg: dict, patterns: list, n: int) -> dict:
    RESULTS.mkdir(parents=True, exist_ok=True)
    pcfg = {**pcfg, "n_collaborators": _n_collaborators()}
    out = {}
    for pat in patterns:
        recs = []
        fn = getattr(runner, f"run_{pat.lower()}")
        for i in range(n):
            try:
                r = fn(_s1_task(i), pcfg)
            except Exception as exc:
                r = {"pattern": pat, "latency_s": None, "invocations": None,
                     "tokens_in": None, "tokens_out": None,
                     "status": f"error:{type(exc).__name__}"}
            recs.append(r)
        with open(RESULTS / f"{name}_{pat}.jsonl", "w") as f:
            for r in recs:
                f.write(json.dumps(r) + "\n")
        ok = [r for r in recs if r.get("status") == "ok" and r.get("latency_s") is not None]
        out[pat] = {
            "n_ok": len(ok), "n_total": len(recs),
            "median_latency_s": (round(statistics.median(r["latency_s"] for r in ok), 4) if ok else None),
            "mean_invocations": (round(statistics.mean(r["invocations"] for r in ok), 3) if ok else None),
        }
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Live-endpoint anchor (R1-1/R2-2)")
    ap.add_argument("--config", default="anchor/anchor_config.yaml")
    args = ap.parse_args(argv)
    cfg = yaml.safe_load(open(args.config))
    n = int(cfg.get("n_requests", 30))
    patterns = list(cfg.get("patterns", ["P1", "P2"]))
    summary = {"scenario": cfg.get("scenario", "S1"), "n_requests": n, "platforms": {}}

    if cfg.get("bedrock", {}).get("enabled"):
        from anchor.live_bedrock import LiveBedrock
        bc = cfg["bedrock"]
        runner = LiveBedrock(region=bc["region"], model_id=bc.get("model_id", "us.amazon.nova-micro-v1:0"))
        summary["platforms"]["bedrock"] = _run_platform("bedrock", runner, bc, patterns, n)
    if cfg.get("agentforce", {}).get("enabled"):
        from anchor.live_agentforce import LiveAgentforce
        ac = cfg["agentforce"]
        runner = LiveAgentforce(ac["domain"], ac["agent_id"], ac.get("api_version", "v1"))
        summary["platforms"]["agentforce"] = _run_platform("agentforce", runner, ac, patterns, n)

    RESULTS.mkdir(parents=True, exist_ok=True)
    json.dump(summary, open(RESULTS / "summary.json", "w"), indent=2)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
