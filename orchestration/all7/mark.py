"""Mark tasks passing in prd.json and append to progress.txt.

Refuses to mark a task whose dependencies are not yet passing, and refuses to
mark a HUMAN-gated task at all -- those two rules are the whole point of the
gates, and they should be enforced by a tool rather than by remembering.

Usage:  python orchestration/all7/mark.py 000 001 -m "note for progress.txt"
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("ids", nargs="+")
    ap.add_argument("-m", "--note", required=True)
    # A HUMAN gate that a human has actually cleared must be recordable, or
    # prd.json drifts from reality and every downstream AUTO task blocks
    # forever. The flag forces the approver to be named in the record, so
    # "approved" is never something the agent quietly assumed.
    ap.add_argument("--human-approved-by",
                    help="record explicit human approval for a HUMAN gate")
    a = ap.parse_args()

    prd_path = HERE / "prd.json"
    prd = json.loads(prd_path.read_text())
    by_id = {t["id"]: t for t in prd["tasks"]}

    for tid in a.ids:
        t = by_id.get(tid)
        if t is None:
            sys.exit(f"REFUSING: no task {tid}")
        if t["gate"] == "HUMAN-REVIEW-REQUIRED" and not a.human_approved_by:
            sys.exit(f"REFUSING: {tid} is HUMAN-REVIEW-REQUIRED. Pass "
                     f"--human-approved-by <name> only when a human has "
                     f"actually approved it.")
        for d in t["depends_on"]:
            if not by_id[d]["passes"] and d not in a.ids:
                sys.exit(f"REFUSING: {tid} depends on {d}, which is not passing")
    for tid in a.ids:
        by_id[tid]["passes"] = True

    prd_path.write_text(json.dumps(prd, indent=2) + "\n")
    with open(HERE / "progress.txt", "a") as f:
        approver = (f" [HUMAN GATE cleared by {a.human_approved_by}]"
                    if a.human_approved_by else "")
        f.write(f"TASK {' '.join(a.ids)} done{approver}: {a.note}\n")

    done = sum(1 for t in prd["tasks"] if t["passes"])
    human = sum(1 for t in prd["tasks"]
                if t["gate"] == "HUMAN-REVIEW-REQUIRED" and not t["passes"])
    nxt = next((t for t in prd["tasks"]
                if not t["passes"]
                and all(by_id[d]["passes"] for d in t["depends_on"])), None)
    print(f"marked {', '.join(a.ids)} | {done}/{len(prd['tasks'])} done | "
          f"{human} human gates outstanding")
    if nxt:
        print(f"next eligible: TASK {nxt['id']} [{nxt['gate']}] {nxt['title']}")
    else:
        print("no eligible AUTO task remains")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
