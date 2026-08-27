"""Summarise the seven-pattern live run, and refuse to summarise a bad one.

Follows the discipline of ``anchor/p7/analyze_p7.py``: a partial or
unattributable run must not produce a publishable-looking table. Every guard
here exists because the corresponding mistake would be invisible downstream.

Refuses when:
  * any pattern returned fewer successes than requests -- a partial run's
    counts are not reportable;
  * an observed structural signature disagrees with the offline fixture --
    that means the deployed code is not doing what the released module does;
  * patterns ran against different image digests -- the records would not
    describe one artifact;
  * a seam fell back to its in-memory stub while the summary would otherwise
    read as live evidence.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
RESULTS = HERE.parent / "results"
BOUNDS = HERE / "known_bounds.json"


def refuse(msg: str) -> None:
    print(f"REFUSING: {msg}")
    sys.exit(1)


def analyse(summary: dict, require_live_backends: bool = True) -> None:
    pats = summary.get("patterns", {})
    if not pats:
        refuse("summary contains no patterns")

    for pid, p in sorted(pats.items()):
        if p["n_ok"] != p["n_total"]:
            refuse(f"{pid} completed {p['n_ok']}/{p['n_total']} requests; "
                   f"a partial run's counts are not reportable "
                   f"({p.get('error_statuses')})")
        if not p.get("signature_matches"):
            refuse(f"{pid} structural signature disagrees with the offline "
                   f"fixture: observed {p.get('observed')} vs expected "
                   f"{p.get('expected_from_offline_fixture')}. The deployed "
                   f"code is not reproducing the released module's control flow.")
        mod = p.get("released_module") or ""
        if not mod.startswith("agentorch.patterns"):
            refuse(f"{pid} reports module {mod!r}; the released module is not "
                   f"what executed")

    if require_live_backends:
        # A pattern whose seam silently used the in-memory stub has not
        # demonstrated anything about the live service. A bound may be
        # TOLERATED only if it is DECLARED in known_bounds.json with a reason
        # -- an undeclared stub is still a refusal, and a declared one is
        # printed loudly rather than passing quietly.
        declared = {}
        if BOUNDS.exists():
            declared = json.loads(BOUNDS.read_text()).get("declared", {})
        needs = {"P4": "memory", "P5": "gateway", "P6": "guardrail",
                 "P3": "observability"}
        for pid, seam in needs.items():
            p = pats.get(pid)
            if not p:
                continue
            live = (p.get("backends_live") or {}).get(seam)
            if live:
                continue
            key = f"{pid}.{seam}"
            if key not in declared:
                refuse(f"{pid} ran with the {seam} seam on its in-memory stub, "
                       f"not the live service, and that bound is not declared "
                       f"in known_bounds.json. An undeclared stub is not live "
                       f"evidence.")
            print(f"!! DECLARED BOUND {key}: {declared[key]['consequence']}")

    digests = {p.get("image_digest") for p in pats.values()}
    digests.discard(None)
    if len(digests) > 1:
        refuse(f"patterns ran against different image digests {digests}; "
               f"the records do not describe one artifact")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--summary",
                    default=str(RESULTS / "all7_summary.json"))
    ap.add_argument("--self-test", action="store_true",
                    help="prove the guards reject a synthetic bad run")
    a = ap.parse_args(argv)

    if a.self_test:
        bad = {"patterns": {"P1": {"n_ok": 28, "n_total": 30,
                                   "signature_matches": True,
                                   "released_module": "agentorch.patterns.p1_supervisor",
                                   "error_statuses": ["error:Timeout"]}}}
        try:
            analyse(bad, require_live_backends=False)
        except SystemExit:
            print("self-test: guards correctly refused a partial run")
            return 1
        print("self-test FAILED: a partial run was accepted")
        return 2

    path = Path(a.summary)
    if not path.exists():
        refuse(f"{path} missing — run anchor/agentcore/run_all7.py first. "
               f"This tool never invents numbers.")
    summary = json.loads(path.read_text())
    analyse(summary)

    print("=== All seven patterns, live on AgentCore Runtime ===")
    print(f"{'pat':<5}{'ok':>8}{'module':<38}{'invocations':>13}"
          f"{'service':>10}{'guardrail':>11}")
    for pid, p in sorted(summary["patterns"].items()):
        o = p["observed"]
        print(f"{pid:<5}{p['n_ok']}/{p['n_total']:<5} "
              f"{(p.get('released_class') or '?'):<38}"
              f"{str(o['invocations']):>13}{str(o['service_calls']):>10}"
              f"{str(o['guardrails_applied']):>11}")
    p6 = summary["patterns"].get("P6")
    if p6:
        print(f"\nP6 paused for a human on {p6['paused_for_human']} of "
              f"{p6['n_total']} items (below-confidence items only; the human "
              f"wait itself is MODELLED, not staffed).")
    print(f"\nall_seven_ok: {summary.get('all_seven_ok')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
