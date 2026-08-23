"""Summarize the P7 probe runs.

C1/C2 exercise the CRM retry direction (ingress off/on in the bridge).
C3/C4 exercise the AWS SDK retry direction (ingress off/on at the target
boundary); they are analysed only if their results are present.

NO-FABRICATION GUARD: refuses to emit a comparison unless the
summary.json files exist and were produced by real runs (non-zero
deliveries, all tasks handled, not truncated). Prints the LaTeX table row
values for §VI-H verbatim from recorded data — nothing is typed by hand
into the manuscript. Whether the SDK retry actually fired is REPORTED,
never assumed: a C3/C4 pair in which it did not fire is printed as such
rather than being dressed up as a result.
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
    if not s.get("all_tasks_invoked"):
        sys.exit(f"REFUSING: {label} invoked only "
                 f"{s['distinct_tasks_invoked']}/{s['n_tasks']} logical "
                 f"tasks — the run did not complete, so its counts are "
                 f"not reportable.")
    if s.get("timed_out"):
        sys.exit(f"REFUSING: {label} hit max_run_seconds — truncated "
                 f"run, counts are not reportable.")
    return s


def load_retry(results_dir, label):
    """Loader for the C3/C4 summaries, which have their own shape."""
    p = Path(results_dir) / label / "summary.json"
    if not p.exists():
        return None
    s = json.loads(p.read_text())
    if s.get("logical_calls", 0) != s.get("n_tasks"):
        sys.exit(f"REFUSING: {label} made {s.get('logical_calls')} logical "
                 f"calls for {s.get('n_tasks')} tasks — incomplete run.")
    if s.get("timed_out"):
        sys.exit(f"REFUSING: {label} hit max_run_seconds — truncated run.")
    if s.get("calls_ok", 0) != s.get("logical_calls"):
        # duplicate_agent_executions is counted only over calls that came
        # back, because the counters ride on the response. If some calls
        # never returned, a low duplicate count would understate rather
        # than measure, so the pair is not reportable from client records
        # alone — read the agent's CloudWatch lines instead.
        sys.exit(f"REFUSING: {label} had "
                 f"{s['logical_calls'] - s.get('calls_ok', 0)} logical calls "
                 f"return no response; duplicate executions cannot be "
                 f"counted from client records. Use the agent's CloudWatch "
                 f"log lines (P7RETRY exec ...) for those tasks.")
    if s.get("redeliveries_observed", 0) != 0:
        # A CRM-side redelivery here would make duplicate executions
        # ambiguous between the two retry domains, which is the one thing
        # this condition exists to rule out.
        sys.exit(f"REFUSING: {label} saw "
                 f"{s['redeliveries_observed']} CRM redeliveries; duplicate "
                 f"executions could not be attributed to the AWS direction.")
    return s


def report_retry(c3, c4):
    print("\n=== P7 probe, AWS-retry direction (live) ===")
    for s in (c3, c4):
        print(f"  {s['run_label']} bridge_ingress={s['bridge_ingress']} "
              f"agent_ingress={s['agent_ingress']}: "
              f"published={s['published']} "
              f"deliveries={s['deliveries_observed']} "
              f"redeliveries={s['redeliveries_observed']} "
              f"logical_calls={s['logical_calls']} "
              f"wire_attempts={s['wire_attempts_total']} "
              f"retried_calls={s['calls_with_sdk_retry']} "
              f"agent_entries>1={s['agent_entries_gt_1']} "
              f"DUP_EXECUTIONS={s['duplicate_agent_executions']}")

    fired = c3["calls_with_sdk_retry"] > 0 and c4["calls_with_sdk_retry"] > 0
    print(f"\nSDK retry fired on the wire: {fired}")
    if not fired:
        print("  -> the AWS retry surface was NOT exercised in this pair; "
              "nothing here may be reported as having exercised it.")
        return
    holds = (c3["duplicate_agent_executions"] > 0
             and c4["duplicate_agent_executions"] == 0)
    print(f"P7 target-boundary ingress claim holds: {holds}")
    print("  note: the bridge-side ingress was ON in both conditions and "
          "suppressed nothing, because the bridge issued one logical call.")
    print("\nLaTeX rows (Table: §VI-H, AWS-retry direction):")
    for s in (c3, c4):
        print(f"  {s['run_label']} & {s['agent_ingress']} & "
              f"{s['published']} & {s['logical_calls']} & "
              f"{s['wire_attempts_total']} & {s['calls_with_sdk_retry']} & "
              f"{s['agent_entries_gt_1']} & "
              f"{s['duplicate_agent_executions']} \\\\")


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

    c3, c4 = load_retry(results_dir, "C3"), load_retry(results_dir, "C4")
    if c3 and c4:
        report_retry(c3, c4)
    else:
        print("\n(no C3/C4 results present — AWS-retry direction not run)")


if __name__ == "__main__":
    main()
