"""Fail if any recorded artifact contains model completion text.

Every recorded surface in this repository is redacted to identifiers,
counters, timestamps and status. The risk is not malice but drift: a new
field added for debugging, a caught exception whose message carries a model
response. This makes that drift a test failure rather than a discovery made
by a reader of the released artifact.

The heuristic is deliberately blunt — long free-text values in unexpected
fields — because a precise one would need to know what a completion looks
like, and the point is to catch the case nobody anticipated.

Usage:  python scripts/check_redaction.py anchor/results/
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# Fields legitimately holding prose: identifiers, statuses and declared
# bounds. Everything else is expected to be short or numeric.
ALLOWED_LONG = {
    "detail", "error", "status", "purpose", "reason", "consequence",
    "to_close", "released_module", "released_class", "pattern_name",
    "image_uri", "image_digest", "arn", "url", "role_arn", "id",
    "seam", "sample", "log_groups",
}
MAX_LEN = 120


def offending(obj, path: str = "") -> list[str]:
    out: list[str] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            out += offending(v, f"{path}.{k}" if path else str(k))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            out += offending(v, f"{path}[{i}]")
    elif isinstance(obj, str):
        leaf = path.split(".")[-1].split("[")[0]
        if leaf not in ALLOWED_LONG and len(obj) > MAX_LEN:
            out.append(f"{path}: {len(obj)} chars — {obj[:60]!r}...")
    return out


def main(argv=None) -> int:
    args = argv or sys.argv[1:]
    if not args:
        sys.exit("usage: check_redaction.py <dir-or-file> [...]")
    problems, scanned = [], 0
    for arg in args:
        p = Path(arg)
        files = sorted(p.rglob("*.json*")) if p.is_dir() else [p]
        for f in files:
            scanned += 1
            try:
                if f.suffix == ".jsonl":
                    for n, line in enumerate(f.read_text().splitlines(), 1):
                        if line.strip():
                            problems += [f"{f}:{n} {x}"
                                         for x in offending(json.loads(line))]
                else:
                    problems += [f"{f} {x}"
                                 for x in offending(json.loads(f.read_text()))]
            except json.JSONDecodeError as exc:
                problems.append(f"{f}: unparseable ({exc})")
    if problems:
        print(f"REDACTION CHECK FAILED — {len(problems)} suspect value(s):")
        for x in problems[:40]:
            print("  -", x)
        return 1
    print(f"redaction check: OK ({scanned} files scanned, no long free text "
          f"outside allowed fields)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
