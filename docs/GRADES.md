# Table 4 grade function (Phase 2 task 106, HUMAN-gated)

`figures/table4.csv` is COMPUTED from the calibrated study results by
`src/agentorch/study/make_table4.py` through the pre-committed
Mann-Whitney/Holm comparison machinery (`agentorch/stats/compare.py`,
`agentorch/stats/correction.py`). No grade is hand-assigned.

## The grade function

Within each (platform, scenario) condition the seven patterns are
compared pairwise (21 pairs — the pre-committed family of
`docs/STATISTICAL_ANALYSIS_PLAN.md`) with two-sided Mann-Whitney U
tests, Holm-corrected at `stats.alpha` (configs/default.yaml). Pattern
X is **significantly dominated by** pattern Y on an endpoint when the
Holm-corrected test rejects AND the Hodges-Lehmann shift X−Y > 0
(higher = worse on every endpoint below). The corrected pairwise tests
induce statistical equivalence groups:

| Grade | Rule |
|---|---|
| **A** | X is in the **best Holm-significant equivalence group**: no other pattern significantly dominates X (X is statistically indistinguishable from the best performer in the condition). |
| **C** | X is significantly dominated by **most** others (≥ 4 of the 6) — the worst group. |
| **B** | otherwise. |

## Endpoints per column

| Column | Per-request endpoint (from results/) |
|---|---|
| `latency_grade` | **Tail latency — the paper's primary endpoint (p99).** Each pattern's baseline per-request latencies restricted to the condition's slowest decile (the p90–p100 order statistics containing p99); pairwise MWU on these conditional tail samples tests stochastic tail dominance, so the grade follows the p99 ordering rather than the median. (Essential for P6: its median is machine-fast, its tail is human-decision-dominated.) |
| `reliability_grade` | Per-request **failure indicator under the fault campaign** (`mode == "fault"` rows of `results/latency.csv`). The campaign runs on S1, so this grade is a per-(pattern, platform) **structural property** applied to all scenario rows. |
| `cost_grade` | Per-request **cost_units** (USD per request under the dated assumptions of `configs/costs.yaml`), within the same (platform, scenario). |
| `oversight_grade` | **Capability metadata, not measurement** (latency-independent): A if the pattern's catalog `solution`/`intent` contains a structural human decision point (P6 pause → human queue → resume); B if its `governance_hooks` include an inline policy gate/check (P1, P2, P4, P5, P7); C if hooks are audit-trail-only (P3). |
| `overall_grade` | Worst (max) of the three **measured** grades. Oversight is reported separately because the paper's fit-for-purpose matrix treats oversight as a capability axis, not a performance axis. |

## Directional agreement with the paper (asserted in tests/test_paper_agreement.py)

- **S3 (bursty triage):** P3's latency grade is strictly better than
  P2's on both platforms (burst absorption vs fixed chain).
- **S2 (long-horizon multi-step):** P1 and P2 are in the best
  equivalence group on **completion** (baseline S2 success rate equals
  the condition's maximum; both natively orchestrate every scenario
  step) — the paper's S2 fitness claim is a completion/structural
  claim, not a raw-speed claim.
- **P6 HITL:** latency grade C (worst group — human-dominated tail) in
  every condition, while its oversight grade is A and unique (the only
  pattern with a structural human decision point).

## Degenerate-sample handling

Pairs whose two samples are identical constants (e.g. both all-zero
failure indicators) are equivalence by definition and contribute no
domination; ties inside MWU use scipy's tie-corrected normal
approximation. [HUMAN: verify the grade thresholds (best group = 0
dominators; worst group ≥ 4) and the tail-decile choice before the
manuscript cites Table 4.]
