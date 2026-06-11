# Pre-registered fit-for-purpose rule (Phase 3 task 201)

**Status: PRE-REGISTERED.** This rule was written in full BEFORE
`figures/fit_matrix.csv` was computed for the first time. Per
PHASE3_SPEC.md, the rule may not be adjusted afterwards to flip
specific cells; any post-computation change must be recorded in the
§Changelog below with a content-neutral reason (e.g., a bug in the
pooling code), never "to match cell X". Disagreements with the paper's
Table 4 are recorded in `docs/FIT_DISCREPANCIES.md`, not resolved by
editing this rule.

## Output

`study/make_fit_matrix.py` reads ONLY `results/` (latency.csv,
cost.csv) plus pattern capability metadata and writes
`figures/fit_matrix.csv`: ONE platform-independent grade per
(pattern, scenario) cell, 7 x 3 = 21 cells, each in
{Weak, Moderate, Strong}. This file is the artifact's analog of the
paper's Table 4 (fit-for-purpose matrix). The four-dimensional
per-platform A/B/C table (`figures/table4_supplementary.csv`) is a
richer supplementary quality view, NOT the fit matrix.

## Statistical machinery (reused, pre-committed)

All measured standings use the existing pre-committed machinery:
two-sided Mann-Whitney U (`stats/compare.py`) over the 21 pairwise
pattern comparisons within one (platform, scenario, endpoint) family,
Holm-corrected at `stats.alpha` = 0.05 (`stats/correction.py`,
`configs/default.yaml`). "X significantly dominated by Y" means the
Holm-corrected test rejects AND the Hodges-Lehmann shift X-Y > 0
(higher = worse on every endpoint below); HL = 0 with a rejected test
falls back to the rank-biserial sign (same tie-breaking as
`make_table4._dominated_grades`, reused verbatim). Pairs of identical
constant samples are equivalence by definition (no domination).

Per-platform **standing** of a pattern on one endpoint:

- **TOP**    -- in the best Holm-significant equivalence group:
               significantly dominated by NO other pattern;
- **BOTTOM** -- significantly dominated by >= 4 of the 6 others
               (the worst group; same threshold as docs/GRADES.md);
- **MID**    -- otherwise.

## Stressed property per scenario

Higher is worse on every endpoint sample below. Data: baseline-mode
rows of `results/latency.csv` and the scenario-tagged
`results/cost.csv` from the full study (n = 500/condition, seed 42).

### S1 -- RAG question answering: throughput + per-request cost

Composite of two endpoints, combined **pessimistically** (the worse of
the two standings, where TOP < MID < BOTTOM):

1. **Throughput (latency-derived):** per-request baseline S1
   latency_ms, full distribution. Sustainable throughput at fixed
   resources is monotone in per-request work (saturation rate ~
   1/mean service time, and the rig offers 0.7 x measured saturation
   per condition), so the per-request latency distribution is the
   sample-based throughput endpoint; the scalar `throughput_rps`
   column of table3.csv has no per-request distribution and is used
   only as a sanity cross-check, never in the rule.
2. **Cost efficiency:** per-request `cost_units` (USD under
   configs/costs.yaml dated assumptions) in S1.

No capability gate in S1.

### S2 -- document generation: multi-step growth + capability

Composite of two **growth** endpoints (multi-step coordination
overhead relative to the pattern's own single-step baseline, removing
each pattern's baseline speed/cost level), combined pessimistically:

1. **Latency growth over stages:** each per-request S2 latency divided
   by the SAME pattern/platform's S1 median latency (per-request
   growth-factor samples).
2. **Cost growth over stages:** each per-request S2 cost_units divided
   by the same pattern/platform's S1 mean cost_units.

Capability gate: `adaptive_decomposition` (see section Capability flags).

### S3 -- bursty incident triage: tail inflation + capability

Single endpoint:

1. **p99 inflation S3-vs-S1:** the slowest decile (p90-p100 order
   statistics, the region holding p99 -- same TAIL_FRACTION = 0.10 as
   make_table4) of each pattern's per-request S3 latencies, each
   divided by the SAME pattern/platform's S1 p99. MWU/Holm on these
   normalized tail samples is the sample-based version of the paper's
   "p99 inflation under burst".

Capability gate: `selective_human_routing` OR `event_absorption`.

## Platform pooling (platform-independent grade)

Standings are computed per platform (agentforce, bedrock) and pooled:

- both platforms TOP    -> pooled TOP;
- both platforms BOTTOM -> pooled BOTTOM;
- anything mixed        -> pooled MID (both-MID is MID by identity).

I.e. Strong/Weak require the SAME extreme standing on BOTH platforms;
mixed evidence is Moderate.

## Grade composition

1. Base grade from pooled standing: TOP -> **Strong**, MID ->
   **Moderate**, BOTTOM -> **Weak**.
2. Capability gate (S2, S3 only): if the scenario's required
   capability is PRESENT in the pattern's metadata, the grade is
   upgraded ONE level (Weak -> Moderate, Moderate -> Strong, Strong
   stays Strong). Absence never downgrades. Rationale
   (content-neutral, fixed before computation): measurement is the
   primary evidence; structural capability metadata corroborates and
   can lift a standing the load level may understate, but a pattern
   is never penalized twice for the same structure (a missing
   capability's cost already appears in the measured standing when it
   is real).

No other modifiers. Ties inside the MWU machinery resolve per the
Statistical-machinery section; the pessimistic composite resolves
S1/S2 endpoint disagreement; pooling resolves platform disagreement.

## Capability flags (pattern structure, one-line justifications)

Flags are explicit booleans in each pattern class's `capabilities()`
classmethod (separate from the nine-element catalog `meta()`), set
from the pattern's ACTUAL implemented structure:

| Pattern | adaptive_decomposition | selective_human_routing | event_absorption |
|---|---|---|---|
| P1 Supervisor-Collaborator | **True** -- the supervisor plans the decomposition per request and dispatches collaborators adaptively | False | False |
| P2 Sequential Pipeline | False -- stage list is fixed in order; no runtime re-decomposition | False | False |
| P3 Event-Driven Choreography | False -- the event chain is a fixed typed sequence | False | **True** -- durable bus + decoupled consumer pool buffer arrival bursts ahead of processing |
| P4 Shared-Memory Blackboard | **True** -- specialists contribute opportunistically against shared state; decomposition is emergent, not fixed up front | False | False |
| P5 Tool-Routed Gateway | False -- the gateway routes calls; it does not decompose tasks | False | False -- bulkheads contain tool faults but the gateway does not buffer arrivals |
| P6 Human-in-the-Loop | False | **True** -- the confidence gate routes ONLY below-threshold items to the human queue (selective by design) | False -- the human queue defers decisions; it is not an arrival-burst buffer for the request stream |
| P7 Federated Bridge | False -- the bridge mediates cross-cluster calls on a fixed topology | False | False |

## Reporting

`figures/fit_matrix.csv` columns: pattern, scenario, fit_grade, plus
transparency columns (per-platform standings per endpoint, pooled
standing, capability_applied) so every grade is auditable from the
file alone. The computed grade is NEVER hand-edited; discrepancies
with the paper live in docs/FIT_DISCREPANCIES.md.

## Changelog

- 2026-06-04: Initial pre-registration (written before the first
  computation of fit_matrix.csv).
