"""Summarize the P7 probe runs (C1 ingress-off, C2 ingress-on).

NO-FABRICATION GUARD: refuses to emit a comparison unless both
summary.json files exist and were produced by real runs (non-zero
deliveries). Prints the LaTeX table row values for §VI-H verbatim
from recorded data — nothing is typed by hand into the manuscript.
"""
import json
import sys
from pathlib import Path


def load(results_dir, label):
    p = Path(results_dir) / label / "summary.json"
    if not p.exists():
        sys.exit(f"REFUSING: {p} missing — run the probe first.")
    s = json.loads(p.read_text())
    if s["deliveries_observed"] == 0:
        sys.exit(f"REFUSING: {label} recorded zero deliveries — not a "
                 f"real run.")
    return s


def main():
    results_dir = sys.argv[1] if len(sys.argv) > 1 else "anchor/p7/results"
    c1, c2 = load(results_dir, "C1"), load(results_dir, "C2")

    print("=== P7 probe comparison (live) ===")
    for s in (c1, c2):
        print(f"  {s['run_label']} ingress={s['ingress']}: "
              f"published={s['published']} "
              f"deliveries={s['deliveries_observed']} "
              f"redeliveries={s['redeliveries_observed']} "
              f"crashes={s['injected_crashes']} "
              f"invocations={s['invocations']} "
              f"DUP_INVOCATIONS={s['duplicate_invocations']} "
              f"inversions={s['ordering_inversions']}")

    ok_direction = (c1["duplicate_invocations"] > 0
                    and c2["duplicate_invocations"] == 0
                    and c2["distinct_tasks_invoked"] == c2["n_tasks"])
    print(f"\nP7 structural claim holds: {ok_direction}")
    print("\nLaTeX rows (Table: §VI-H):")
    for s in (c1, c2):
        print(f"  {s['run_label']} & "
              f"{'off' if s['ingress']=='off' else 'on'} & "
              f"{s['published']} & {s['deliveries_observed']} & "
              f"{s['redeliveries_observed']} & {s['invocations']} & "
              f"{s['duplicate_invocations']} & "
              f"{s['ordering_inversions']} \\\\")


if __name__ == "__main__":
    main()
