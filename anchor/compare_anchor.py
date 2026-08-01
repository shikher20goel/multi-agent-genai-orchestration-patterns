"""Evaluate the anchor's two directional claims from REAL run output.

Refuses to run without results produced by an actual live run (no
fabrication). Writes anchor/results/anchor_findings.json and prints a
table for Section VI-G.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

RESULTS = Path(__file__).resolve().parent / "results"


def main() -> int:
    summ = RESULTS / "summary.json"
    if not summ.exists():
        sys.exit("No anchor/results/summary.json - run `python -m anchor.run_anchor` "
                 "against live endpoints first. This tool never invents numbers.")
    data = json.loads(summ.read_text())
    findings = {"scenario": data.get("scenario"), "per_platform": {}}
    rows = []
    for plat, pats in data.get("platforms", {}).items():
        p1, p2 = pats.get("P1", {}), pats.get("P2", {})
        l1, l2 = p1.get("median_latency_s"), p2.get("median_latency_s")
        i1, i2 = p1.get("mean_invocations"), p2.get("mean_invocations")
        lat_ok = (l1 is not None and l2 is not None and l1 > l2)
        inv_ok = (i1 is not None and i2 is not None and i1 > i2)
        findings["per_platform"][plat] = {
            "p1_median_latency_s": l1, "p2_median_latency_s": l2,
            "p1_mean_invocations": i1, "p2_mean_invocations": i2,
            "latency_ordering_holds": lat_ok,
            "invocation_ordering_holds": inv_ok,
            "p1_n_ok": p1.get("n_ok"), "p2_n_ok": p2.get("n_ok")}
        rows.append((plat, l1, l2, lat_ok, i1, i2, inv_ok))
    json.dump(findings, open(RESULTS / "anchor_findings.json", "w"), indent=2)
    print(f"{'platform':<12}{'P1 lat':>9}{'P2 lat':>9}{'lat P1>P2':>11}"
          f"{'P1 inv':>8}{'P2 inv':>8}{'inv P1>P2':>11}")
    for plat, l1, l2, lo, i1, i2, io in rows:
        print(f"{plat:<12}{str(l1):>9}{str(l2):>9}{str(lo):>11}"
              f"{str(i1):>8}{str(i2):>8}{str(io):>11}")
    print("\nWrote", RESULTS / "anchor_findings.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
