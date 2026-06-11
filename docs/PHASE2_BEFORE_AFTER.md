# Phase 2 before/after — recalibrated study outputs (task 110)

**Before** = the Phase-1 `figures/table3.csv` produced on branch
`autonomous-build` at git revision `d8d08bb` (seed 42, n = 500 per
condition; that table is preserved in this document because `figures/`
was gitignored on `autonomous-build`, so the on-disk Phase-1 artifact —
generated at that revision and untouched since — is the snapshot
source). **After** = the regenerated `figures/table3.csv` from
`bash run.sh` on `phase2-calibration` after tasks 101–106 (seed 42,
n = 500 per condition; provenance in `results/manifest.json`).

## p50/p99 per scenario, patterns P1/P2/P4/P6

| Pattern | Platform | Scenario | p50 before (ms) | p99 before (ms) | p50 after (ms) | p99 after (ms) |
|---|---|---|---:|---:|---:|---:|
| P1 | agentforce | S1 | 1,179.4 | 3,189.8 | 5,880.0 | 13,437.6 |
| P1 | agentforce | S2 | 1,194.1 | 3,189.8 | 9,339.6 | 24,359.5 |
| P1 | agentforce | S3 | 1,117.8 | 2,929.9 | 6,233.6 | 19,524.5 |
| P1 | bedrock | S1 | 61,121.7 | 114,396.6 | 4,544.9 | 10,194.5 |
| P1 | bedrock | S2 | 73,020.8 | 122,260.8 | 6,690.2 | 12,599.3 |
| P1 | bedrock | S3 | 57,610.8 | 117,678.1 | 6,000.9 | 17,697.0 |
| P2 | agentforce | S1 | 443.8 | 862.1 | 1,607.3 | 4,550.6 |
| P2 | agentforce | S2 | 908.2 | 1,666.2 | 10,800.2 | 23,302.3 |
| P2 | agentforce | S3 | 443.3 | 862.1 | 6,374.5 | 23,795.7 |
| P2 | bedrock | S1 | 2,606.2 | 6,655.9 | 1,259.9 | 3,773.6 |
| P2 | bedrock | S2 | 88,055.5 | 188,916.5 | 8,313.4 | 18,599.0 |
| P2 | bedrock | S3 | 2,149.9 | 5,637.5 | 3,796.4 | 13,986.4 |
| P4 | agentforce | S1 | 43,275.4 | 81,365.1 | 6,368.4 | 20,062.1 |
| P4 | agentforce | S2 | 34,174.6 | 75,956.5 | 9,542.8 | 24,247.8 |
| P4 | agentforce | S3 | 49,829.3 | 86,685.8 | 10,562.6 | 28,288.8 |
| P4 | bedrock | S1 | 2,523.6 | 7,495.5 | 5,246.6 | 12,450.3 |
| P4 | bedrock | S2 | 2,500.8 | 5,017.5 | 5,011.5 | 12,359.2 |
| P4 | bedrock | S3 | 3,213.0 | 7,373.7 | 9,879.4 | 25,886.0 |
| P6 | agentforce | S1 | 750.2 | 2,398.6 | 1,997.9 | 62,813.4 |
| P6 | agentforce | S2 | 752.4 | 2,338.2 | 3,001.8 | 77,466.4 |
| P6 | agentforce | S3 | 764.5 | 2,355.2 | 4,681.1 | 58,318.8 |
| P6 | bedrock | S1 | 533.5 | 1,747.2 | 1,628.1 | 61,892.3 |
| P6 | bedrock | S2 | 531.5 | 1,747.2 | 1,767.6 | 81,918.7 |
| P6 | bedrock | S3 | 536.8 | 1,740.2 | 7,331.2 | 64,814.0 |

## Why each pattern's numbers changed (one paragraph each)

**P1 Supervisor–Collaborator.** Before, P1's latency was a
platform-config artifact: Agentforce sat at ~1.2 s p50 while Bedrock
exploded to 61–73 s p50 / 114–122 s p99 — an unbounded-queue artifact of
driving a five-invocation fan-out at a fixed 2 rps against c=4 servers,
contradicting the paper's structural story and the no-60–190 s rail.
After tasks 101/102, latency emerges from structure (plan +
max-of-collaborators + synthesis, tail-at-scale per Dean & Barroso) and
the load generator drives each condition at 0.7 × its measured
saturation, so both platforms now sit in a realistic multi-second band
(p50 ≈ 4.5–9.3 s; p99 ≈ 10–24 s), S2 exceeds S1 because each
collaborator sequentially handles its share of the multi-step item
(task 105), and the small Agentforce-vs-Bedrock gap is the documented
Atlas runtime overhead, not an accident.

**P2 Sequential Pipeline.** Before, P2's stages were modeled
asymmetrically — full model invocations on Bedrock (S2: 88 s p50 /
189 s p99, breaching the 60–190 s rail) versus near-free Agent Script
actions on Agentforce (S2: 0.9 s p50), an unexplained cross-platform
contradiction. After task 101 each stage is one model-backed step on
BOTH platforms and stage count follows the scenario (S1 = 1 stage,
S2 = 4–8), so the additive-over-stages consequence appears cleanly on
both: S2 p99 (≈ 18.6–23.3 s) is several times S1 p99 (≈ 3.8–4.6 s),
exactly the paper's claim, with no saturation artifact.

**P4 Shared-Memory Blackboard.** Before, P4 showed the same artifact in
mirror image — Agentforce queued unboundedly (43–50 s p50, 81–87 s p99)
while Bedrock stayed at ~2.5–3.2 s p50 — because per-platform service
prices, not structure, set the numbers. After task 101 the blackboard
is contention-bound on both platforms (a write-serialization term that
grows with concurrent writers) and runs below saturation, so P4 sits in
a 5–10.6 s p50 / 12–28 s p99 band with S3 (bursty, more concurrent
writers) its worst scenario on both platforms — the structural
consequence the paper states.

**P6 Human-in-the-Loop.** Before, P6 was among the FASTEST patterns
(p99 ≈ 1.7–2.4 s) because no human time was modeled at all —
contradicting the paper's latency-bound consequence for HITL. After
task 101 the configurable human decision delay
(`latency.shared.human_decision_delay`, lognormal p50 ≈ 30 s) dominates
the adjudicated fraction of requests: machine-path medians stay low
(p50 ≈ 1.6–7.3 s) but the tail is human-step-dominated (p99 ≈ 58–82 s),
making P6 the highest-latency pattern in every condition (agreement
claim 2) while remaining far below the old 190 s artifact range. The
waiting request releases its compute server (the human queue is a
separate resource), so the delay prices oversight without poisoning
throughput accounting.

## Cost ledger (context for the same regeneration)

The cost columns changed under task 105: one consistent unit (USD per
request, dated assumptions in `configs/costs.yaml`), Agentforce Agent
Script actions billed as Flex action credits (no zero-billed path), and
multi-step S2 work scaling token volume (Bedrock) and per-step actions
(Agentforce) so S2 > S1 per pattern and P1 fan-out > P2 single chain.
The persisted `figures/cost_ledger.csv` is now scenario-resolved (42
rows).

## Table 4 (context)

`figures/table4.csv` is now computed through the MWU/Holm
equivalence-group grade function (`docs/GRADES.md`): P6 grades C on
latency everywhere but A (uniquely) on the new metadata-derived
oversight column; P3 grades better than P2 under S3 on both platforms.
