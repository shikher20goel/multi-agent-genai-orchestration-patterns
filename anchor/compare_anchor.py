"""Evaluate the anchor's directional claims from REAL run output.

Refuses to run without results produced by an actual live run (no
fabrication). Writes anchor/results/anchor_findings.json (or --out) and
prints the tables Section VI-G quotes.

Reports, per platform:
  * the two orderings (P1 latency > P2; P1 invocations > P2),
  * the latency RATIO P1/P2 -- a directional magnitude, not a benchmark,
  * for the managed-runtime arm, the median orchestration time measured
    INSIDE the runtime alongside the client-side median, so the platform
    overhead is visible rather than subtracted away,
  * for runs with more than one offered-concurrency level, per-level
    medians and whether the ordering is preserved at each level.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

RESULTS = Path(__file__).resolve().parent / "results"


def _ratio(a, b):
    if a is None or b is None or not b:
        return None
    return round(a / b, 2)


def _pair(pats: dict) -> dict:
    p1, p2 = pats.get("P1", {}), pats.get("P2", {})
    l1, l2 = p1.get("median_latency_s"), p2.get("median_latency_s")
    i1, i2 = p1.get("mean_invocations"), p2.get("mean_invocations")
    out = {
        "p1_median_latency_s": l1, "p2_median_latency_s": l2,
        "latency_ratio_p1_over_p2": _ratio(l1, l2),
        "p1_mean_invocations": i1, "p2_mean_invocations": i2,
        "latency_ordering_holds": (l1 is not None and l2 is not None and l1 > l2),
        "invocation_ordering_holds": (i1 is not None and i2 is not None and i1 > i2),
        "p1_n_ok": p1.get("n_ok"), "p2_n_ok": p2.get("n_ok"),
        "p1_n_total": p1.get("n_total"), "p2_n_total": p2.get("n_total"),
    }
    for k, pat in (("p1", p1), ("p2", p2)):
        if pat.get("median_in_runtime_latency_s") is not None:
            out[f"{k}_median_in_runtime_latency_s"] = \
                pat["median_in_runtime_latency_s"]
        if pat.get("error_statuses"):
            out[f"{k}_error_statuses"] = pat["error_statuses"]
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--summary", default=str(RESULTS / "summary.json"))
    ap.add_argument("--out", default=str(RESULTS / "anchor_findings.json"))
    a = ap.parse_args(argv)

    summ = Path(a.summary)
    if not summ.exists():
        sys.exit(f"No {summ} - run `python -m anchor.run_anchor` against live "
                 "endpoints first. This tool never invents numbers.")
    data = json.loads(summ.read_text())
    findings = {"scenario": data.get("scenario"),
                "n_requests": data.get("n_requests"),
                "per_platform": {}}
    rows = []
    for plat, pats in data.get("platforms", {}).items():
        f = _pair(pats)
        findings["per_platform"][plat] = f
        rows.append((plat, f))

    print(f"{'platform':<12}{'P1 lat':>9}{'P2 lat':>9}{'ratio':>7}"
          f"{'lat P1>P2':>11}{'P1 inv':>8}{'P2 inv':>8}{'inv P1>P2':>11}")
    for plat, f in rows:
        print(f"{plat:<12}{str(f['p1_median_latency_s']):>9}"
              f"{str(f['p2_median_latency_s']):>9}"
              f"{str(f['latency_ratio_p1_over_p2']):>7}"
              f"{str(f['latency_ordering_holds']):>11}"
              f"{str(f['p1_mean_invocations']):>8}"
              f"{str(f['p2_mean_invocations']):>8}"
              f"{str(f['invocation_ordering_holds']):>11}")

    by_c = data.get("by_concurrency")
    if by_c:
        findings["by_concurrency"] = {}
        print(f"\n{'platform':<12}{'level':>7}{'P1 lat':>9}{'P2 lat':>9}"
              f"{'ratio':>7}{'ordering held':>15}{'P1 ok':>7}{'P2 ok':>7}")
        for plat, levels in by_c.items():
            findings["by_concurrency"][plat] = {}
            for lvl, pats in levels.items():
                f = _pair(pats)
                findings["by_concurrency"][plat][lvl] = f
                print(f"{plat:<12}{lvl:>7}{str(f['p1_median_latency_s']):>9}"
                      f"{str(f['p2_median_latency_s']):>9}"
                      f"{str(f['latency_ratio_p1_over_p2']):>7}"
                      f"{str(f['latency_ordering_holds']):>15}"
                      f"{str(f['p1_n_ok']):>7}{str(f['p2_n_ok']):>7}")
            held = [f["latency_ordering_holds"]
                    for f in findings["by_concurrency"][plat].values()]
            findings["by_concurrency"][plat]["ordering_preserved_at_all_levels"] = \
                all(held)

    json.dump(findings, open(a.out, "w"), indent=2)
    print("\nWrote", a.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
