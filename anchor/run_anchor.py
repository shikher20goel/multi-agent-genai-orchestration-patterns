"""Run the live-endpoint anchor (reviewer R1-1 / R2-2).

Issues the S1 baseline request set against live Bedrock and/or Agentforce
and/or deployed Bedrock AgentCore Runtime agents, for P1 and P2, and
writes REDACTED per-request records plus an aggregate summary. No number
is fabricated: if a platform is disabled or a run fails, that is recorded
honestly and compare_anchor.py will not invent it.

Two axes:

* platform -- ``bedrock`` (Converse API, orchestration in the harness),
  ``agentcore`` (orchestration inside the vendor's managed agent runtime),
  ``agentforce`` (Salesforce Agent API).
* offered concurrency -- ``concurrency: [1, 8]`` runs the same n requests
  at each level. Level 1 is the original sequential loop, unchanged, so
  earlier records stay reproducible.
"""
from __future__ import annotations

import argparse
import json
import statistics
from concurrent.futures import ThreadPoolExecutor
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


def _one(fn, i: int, pat: str, pcfg: dict) -> dict:
    try:
        return fn(_s1_task(i), pcfg)
    except Exception as exc:
        return {"pattern": pat, "latency_s": None, "invocations": None,
                "tokens_in": None, "tokens_out": None,
                "status": f"error:{type(exc).__name__}"}


def _aggregate(recs: list) -> dict:
    ok = [r for r in recs if r.get("status") == "ok"
          and r.get("latency_s") is not None]
    inner = [r["in_runtime_latency_s"] for r in ok
             if r.get("in_runtime_latency_s") is not None]
    agg = {
        "n_ok": len(ok), "n_total": len(recs),
        "median_latency_s": (round(statistics.median(r["latency_s"] for r in ok), 4)
                             if ok else None),
        "mean_invocations": (round(statistics.mean(r["invocations"] for r in ok), 3)
                             if ok else None),
    }
    if inner:
        # Only the managed-runtime arm reports this; it is the orchestration
        # time measured inside the runtime, never subtracted from latency.
        agg["median_in_runtime_latency_s"] = round(statistics.median(inner), 4)
    # A run that partly failed must say so rather than quietly shrink n.
    bad = [r.get("status") for r in recs if r.get("status") != "ok"]
    if bad:
        agg["error_statuses"] = sorted(set(bad))
    return agg


def _run_platform(name: str, runner, pcfg: dict, patterns: list, n: int,
                  concurrency: int = 1) -> dict:
    RESULTS.mkdir(parents=True, exist_ok=True)
    pcfg = {**pcfg, "n_collaborators": _n_collaborators()}
    out = {}
    for pat in patterns:
        fn = getattr(runner, f"run_{pat.lower()}")
        if concurrency <= 1:
            recs = [_one(fn, i, pat, pcfg) for i in range(n)]
        else:
            with ThreadPoolExecutor(max_workers=concurrency) as ex:
                recs = list(ex.map(lambda i: _one(fn, i, pat, pcfg), range(n)))
        suffix = "" if concurrency <= 1 else f"_c{concurrency}"
        with open(RESULTS / f"{name}_{pat}{suffix}.jsonl", "w") as f:
            for r in recs:
                f.write(json.dumps(r) + "\n")
        out[pat] = _aggregate(recs)
    return out


def _make_runner(plat: str, cfg: dict):
    if plat == "bedrock":
        from anchor.live_bedrock import LiveBedrock
        return LiveBedrock(region=cfg["region"],
                           model_id=cfg.get("model_id",
                                            "us.amazon.nova-micro-v1:0"))
    if plat == "agentcore":
        from anchor.live_agentcore import LiveAgentCore
        arns = cfg.get("runtime_arns")
        if not arns:
            # Written by deploy_agentcore.py; never hand-typed.
            rt = json.loads(
                (Path(__file__).resolve().parent / "agentcore"
                 / "runtimes.json").read_text())
            arns = rt["runtimes"]
        return LiveAgentCore(region=cfg["region"], runtime_arns=arns)
    if plat == "agentforce":
        from anchor.live_agentforce import LiveAgentforce
        return LiveAgentforce(cfg["domain"], cfg["agent_id"],
                              cfg.get("api_version", "v1"))
    raise ValueError(f"unknown platform {plat}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Live-endpoint anchor (R1-1/R2-2)")
    ap.add_argument("--config", default="anchor/anchor_config.yaml")
    ap.add_argument("--out-summary",
                    help="summary path (default anchor/results/summary.json)")
    ap.add_argument("--only",
                    help="comma-separated subset of enabled platforms to run, "
                         "e.g. 'agentcore,bedrock'. Lets arms that need "
                         "different credentials run in separate passes.")
    args = ap.parse_args(argv)
    cfg = yaml.safe_load(open(args.config))
    n = int(cfg.get("n_requests", 30))
    patterns = list(cfg.get("patterns", ["P1", "P2"]))
    levels = [int(c) for c in cfg.get("concurrency", [1])]
    summary = {"scenario": cfg.get("scenario", "S1"), "n_requests": n,
               "platforms": {}}
    if levels != [1]:
        summary["concurrency_levels"] = levels
        summary["by_concurrency"] = {}

    only = {x.strip() for x in args.only.split(",")} if args.only else None
    for plat in ("bedrock", "agentcore", "agentforce"):
        pcfg = cfg.get(plat, {})
        if not pcfg.get("enabled") or (only and plat not in only):
            continue
        runner = _make_runner(plat, pcfg)
        # record_prefix names the output files and the summary key. It
        # defaults to the platform, but a run that differs from an earlier
        # one in region or size MUST set it: reusing the name would
        # overwrite records the manuscript already cites.
        label = pcfg.get("record_prefix", plat)
        # A platform may cap its own concurrency (org API limits); honour it
        # and record what was actually offered rather than what was asked.
        plat_levels = [int(c) for c in pcfg.get("concurrency", levels)]
        for c in plat_levels:
            res = _run_platform(label, runner, pcfg, patterns, n, c)
            if c == plat_levels[0]:
                summary["platforms"][label] = res
            if "by_concurrency" in summary:
                summary["by_concurrency"].setdefault(label, {})[f"c{c}"] = res

    RESULTS.mkdir(parents=True, exist_ok=True)
    out_path = Path(args.out_summary) if args.out_summary \
        else RESULTS / "summary.json"
    json.dump(summary, open(out_path, "w"), indent=2)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
