# Rejected Candidate Patterns (Task 052, HUMAN-gated)

The manuscript (Section III.A) states that applying the four
pattern-admission criteria "admitted seven patterns and rejected six
candidate topologies (recorded, with their criterion-failure
rationale, in the reproducibility package)". The submitted PDF does
**not** enumerate the six rejected candidates itself — this file is
the record the paper points to.

Because the paper does not name the candidates, the six below are
**derived from the paper's own admission criteria** (a topology must
be (1) *recurring*, (2) *platform-independent*, (3) *structurally
distinct* in coordination topology, and (4) have *distinct
consequences* in the latency/cost/fault-isolation trade-off space) and
from the surrounding multi-agent literature the paper engages. Every
entry is marked for human verification: the human author must confirm
each candidate matches the six actually considered during catalog
construction, or replace it.

| # | Candidate topology | Failed criterion | Rationale |
|---|---|---|---|
| 1 | **Debate / Adversarial Critique** (two or more agents argue; a judge agent selects) | Structurally distinct | Its coordination topology is a supervisor fanning out to peer agents and aggregating their outputs — structurally a specialization of P1 Supervisor–Worker with a particular aggregation function (judging), not a new topology. [HUMAN: verify rationale] |
| 2 | **Reflection / Self-Refinement Loop** (one agent iteratively critiques and revises its own output) | Structurally distinct (and borderline on recurring *as a multi-agent* topology) | With a single agent looping on itself there is no inter-agent coordination structure; rendered with a separate critic agent it collapses to a two-stage P2 Pipeline executed repeatedly. It differs in prompt strategy, not in coordination topology. [HUMAN: verify rationale] |
| 3 | **Swarm / Emergent Marketplace** (many homogeneous agents bid for or claim work with no coordinator) | Distinct consequences (and platform-independent in practice) | Under measurement its latency/cost/fault-isolation profile is not separable from P3 Choreography (peer agents reacting to a shared event medium); claimed "emergent" benefits do not occupy a distinct point in the trade-off space at enterprise scale, and neither Agentforce nor Bedrock exposes a primitive for unmediated agent-to-agent bidding. [HUMAN: verify rationale] |
| 4 | **Hierarchical Supervisor-of-Supervisors** (multi-level tree of supervisors) | Structurally distinct | Recursion over P1 Supervisor–Worker: every level is itself a supervisor fan-out, so the topology is P1 composed with P1 and inherits its consequence profile (deeper fan-out latency, multiplied invocation cost) rather than occupying a new point. [HUMAN: verify rationale] |
| 5 | **Platform-Native Auto-Orchestrator delegation** (handing the whole plan to one vendor's built-in planner, e.g. a single platform's routing/planning service) | Platform-independent | By definition expressible only in terms of a single vendor's planner primitive; it cannot be stated without reference to that vendor's offering, so it fails the platform-independence criterion outright even though it recurs in practice. [HUMAN: verify rationale] |
| 6 | **Shared-Nothing Replica Voting** (N identical agents answer independently; majority vote) | Distinct consequences (and recurring as a *multi-agent coordination* form is doubtful) | An ensembling/reliability tactic rather than a coordination topology: its structure is a degenerate P1 fan-out with a fixed vote aggregator, and its consequence profile (N-times cost for modest tail-latency change) is a scalar multiple of P1's rather than a distinct trade-off point. [HUMAN: verify rationale] |

## Notes

- The criterion names above quote the manuscript's Section III.A
  criteria verbatim in shortened form: *recurring*,
  *platform-independent*, *structurally distinct*, *distinct
  consequences*.
- Rejection is part of the method: "a catalog that admits every
  topology has no discriminating power" (manuscript, Section III.A).
- Recalibration note (Phase 2 task 109): the "distinct consequences"
  criterion is now empirically sharper — the recalibrated study shows
  structurally distinct latency/cost/fault profiles per admitted
  pattern (structural latency derivation, four-way fault
  classification, scenario-resolved cost ledger), so a candidate whose
  profile collapses onto an admitted pattern's (rows 3, 6) remains
  rejected under measurement, not only argument. [HUMAN: re-verify
  rows 3 and 6 against the regenerated `figures/table3.csv`,
  `figures/table4.csv`, and `figures/fault_matrix.png`.]
- [HUMAN: verify rationale] applies to every row — confirm these are
  the six candidates actually weighed during catalog construction, and
  adjust names/rationales to match the author's notes before the
  camera-ready references this file.
