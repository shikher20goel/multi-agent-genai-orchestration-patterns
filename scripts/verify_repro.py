#!/usr/bin/env python3
"""Clean-clone reproducibility manifest check (task 062).

Verifies that after ``bash run.sh`` the figures/ directory contains
table3.csv, fit_matrix.csv (paper Table 4), table4_supplementary.csv and ALL expected PNGs, and that results/ holds
the raw study outputs and a sane manifest. Exits 0 on success,
non-zero with a listing of what is missing otherwise.

Usage: ``python3 scripts/verify_repro.py [--root <repo-root>]``
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

EXPECTED_FIGURES = [
    "table3.csv",
    "fit_matrix.csv",
    "table4_supplementary.csv",
    "ccdf.png",
    "p99_ci.png",
    "cost_per_1k.png",
    "fault_matrix.png",
    "decision_tree.png",
    "cost_ledger.csv",
]
EXPECTED_RESULTS = ["latency.csv", "cost.csv", "faults.csv", "manifest.json"]


def verify(root: Path) -> list[str]:
    """Return a list of problems (empty list == reproduction verified)."""
    problems: list[str] = []
    for name in EXPECTED_FIGURES:
        p = root / "figures" / name
        if not p.is_file():
            problems.append(f"missing figures/{name}")
        elif p.stat().st_size == 0:
            problems.append(f"empty figures/{name}")
    pngs = [n for n in EXPECTED_FIGURES if n.endswith(".png")]
    for name in pngs:
        p = root / "figures" / name
        if p.is_file() and p.read_bytes()[:8] != b"\x89PNG\r\n\x1a\n":
            problems.append(f"figures/{name} is not a valid PNG")
    for name in EXPECTED_RESULTS:
        p = root / "results" / name
        if not p.is_file():
            problems.append(f"missing results/{name}")
        elif p.stat().st_size == 0:
            problems.append(f"empty results/{name}")
    manifest = root / "results" / "manifest.json"
    if manifest.is_file():
        try:
            m = json.loads(manifest.read_text())
        except json.JSONDecodeError as exc:
            problems.append(f"results/manifest.json unparsable: {exc}")
        else:
            for key in ("seed", "config_hash", "n_per_condition",
                        "n_baseline_conditions", "fault_campaign_cells"):
                if key not in m:
                    problems.append(f"manifest missing key {key!r}")
    return problems


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", default=".", help="repository root (default: cwd)")
    args = ap.parse_args(argv)
    root = Path(args.root).resolve()
    problems = verify(root)
    if problems:
        print("verify_repro: FAILED")
        for p in problems:
            print(f"  - {p}")
        return 1
    print(f"verify_repro: OK ({len(EXPECTED_FIGURES)} figures outputs, "
          f"{len(EXPECTED_RESULTS)} results outputs present under {root})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
