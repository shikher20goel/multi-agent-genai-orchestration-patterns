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
    a = ap.parse_args()

    prd_path = HERE / "prd.json"
    prd = json.loads(prd_path.read_text())
    by_id = {t["id"]: t for t in prd["tasks"]}

    for tid in a.ids:
        t = by_id.get(tid)
        if t is None:
            sys.exit(f"REFUSING: no task {tid}")
        if t["gate"] == "HUMAN-REVIEW-REQUIRED":
            sys.exit(f"REFUSING: {tid} is HUMAN-REVIEW-REQUIRED and cannot be "
                     f"marked passing by the agent")
        for d in t["depends_on"]:
            if not by_id[d]["passes"] and d not in a.ids:
                sys.exit(f"REFUSING: {tid} depends on {d}, which is not passing")
    for tid in a.ids:
        by_id[tid]["passes"] = True

    prd_path.write_text(json.dumps(prd, indent=2) + "\n")
    with open(HERE / "progress.txt", "a") as f:
        f.write(f"TASK {' '.join(a.ids)} done: {a.note}\n")

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
