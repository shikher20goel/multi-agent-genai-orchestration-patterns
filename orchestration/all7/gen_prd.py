"""Generate prd.json from BACKLOG.md.

Hand-transcribing seventy tasks into JSON is a transcription-error machine, and
a prd.json that disagrees with the backlog is worse than none: the agent
executes the JSON while the human reads the Markdown. So the JSON is derived,
and this script is the only thing allowed to write it.

Also enforces the invariants the orchestrator skill requires:
  - dependency order (no task depends on a higher id)
  - every task has a done-check or an explicit human flag
  - every task carries a review gate
  - every task starts passes=false
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BACKLOG = HERE / "BACKLOG.md"
OUT = HERE / "prd.json"

COMPLETION_PROMISE = "PROJECT_COMPLETE"
VERIFY_COMMAND = "python -m pytest -q"

FORBIDDEN = [
    "creating, modifying or deleting AWS resources without human approval",
    "changing IAM roles, policies or any access control",
    "overwriting or deleting any committed record under anchor/results/ or anchor/p7/results/",
    "editing the manuscript, the response letter, or any upload artifact",
    "publishing a git tag, GitHub release, or Zenodo DOI",
    "submitting anything to the IEEE portal",
    "committing secrets, keys or tokens",
    "recording model completion text in any result file",
]

TASK_RE = re.compile(r"^### TASK (\d{3}) — (.+)$")
FIELD_RE = re.compile(r"^- ([A-Za-z/ -]+?):\s*(.*)$")


def parse() -> list[dict]:
    tasks, cur = [], None
    for line in BACKLOG.read_text().splitlines():
        m = TASK_RE.match(line)
        if m:
            if cur:
                tasks.append(cur)
            cur = {"id": m.group(1), "title": m.group(2).strip()}
            continue
        if cur is None:
            continue
        f = FIELD_RE.match(line)
        if not f:
            continue
        key, val = f.group(1).strip().lower(), f.group(2).strip()
        if key == "milestone":
            cur["milestone"] = val.split("—")[0].strip()
        elif key == "depends on":
            cur["depends_on"] = ([] if val.lower().startswith("none")
                                 else re.findall(r"\d{3}", val))
        elif key == "done-check":
            cur["verify"] = val
        elif key == "review gate":
            cur["gate"] = val.strip()
    if cur:
        tasks.append(cur)
    return tasks


def check(tasks: list[dict]) -> list[str]:
    errs, seen = [], set()
    for t in tasks:
        tid = t["id"]
        if tid in seen:
            errs.append(f"{tid}: duplicate id")
        seen.add(tid)
        for field in ("milestone", "depends_on", "verify", "gate"):
            if field not in t:
                errs.append(f"{tid}: missing {field}")
        if t.get("gate") not in ("AUTO", "HUMAN-REVIEW-REQUIRED"):
            errs.append(f"{tid}: bad gate {t.get('gate')!r}")
        for d in t.get("depends_on", []):
            if d >= tid:
                errs.append(f"{tid}: forward dependency on {d}")
            if d not in seen:
                errs.append(f"{tid}: depends on unknown/later task {d}")
        v = t.get("verify", "")
        if t.get("gate") == "HUMAN-REVIEW-REQUIRED":
            if "FLAG FOR HUMAN REVIEW" not in v.upper():
                errs.append(f"{tid}: human-gated but no explicit flag in done-check")
        elif not v or v.lower().startswith(("looks", "should")):
            errs.append(f"{tid}: done-check is not machine-verifiable")
    return errs


def main() -> int:
    tasks = parse()
    errs = check(tasks)
    if errs:
        print(f"REFUSING to write prd.json — {len(errs)} invariant violation(s):")
        for e in errs:
            print("  -", e)
        return 1
    prd = {
        "project": "All Seven Patterns Live on AWS",
        "completion_promise": COMPLETION_PROMISE,
        "verify_command": VERIFY_COMMAND,
        "forbidden_autonomous_actions": FORBIDDEN,
        "tasks": [{"id": t["id"], "title": t["title"], "milestone": t["milestone"],
                   "depends_on": t["depends_on"], "verify": t["verify"],
                   "gate": t["gate"], "passes": False} for t in tasks],
    }
    OUT.write_text(json.dumps(prd, indent=2) + "\n")
    human = sum(1 for t in prd["tasks"] if t["gate"] == "HUMAN-REVIEW-REQUIRED")
    print(f"wrote {OUT.name}: {len(prd['tasks'])} tasks "
          f"({human} human-gated, {len(prd['tasks']) - human} auto)")
    for ms in sorted({t["milestone"] for t in prd["tasks"]}):
        n = sum(1 for t in prd["tasks"] if t["milestone"] == ms)
        print(f"   {ms}: {n}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
