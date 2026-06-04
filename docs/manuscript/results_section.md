# Draft manuscript section: "Executed Measurement Study" (Task 058; recalibrated under Phase 2 tasks 101–106, 108 — HUMAN-gated)

> Drafted for insertion in place of / alongside the manuscript's
> Section V ("Reference Implementation and Prospective Evaluation
> Rig") and Section VI. IEEE voice. Every number below is copied
> verbatim-rounded (rounding indicated) from the repository's
> regenerated outputs (task 110 run: seed 42, n = 500/condition,
> git revision and config hash in results/manifest.json) and carries
> an inline trace. [HUMAN: verify every number against the regenerated
> `figures/` and `results/` files before insertion; figures are
> referenced by repository filename and must be renumbered to the
> manuscript's figure sequence.]

---

## Section: Executed Measurement Study

### A. Scope of the Evidence (read first)

**All results in this section are RELATIVE, STRUCTURAL comparisons
obtained under identical, controlled, locally mocked platform
conditions. They are not production service-level measurements, not
vendor benchmarks, and not absolute performance claims about
Salesforce Agentforce or Amazon Bedrock.** The mocked clients
reproduce the documented *interface shapes* of the real platforms and
draw service times from configured, documented distributions
(configs/default.yaml), so what the study isolates is the effect of
*coordination topology* — which pattern queues, fans out, chains,
contends, waits on a human, or crosses a platform boundary — with
everything else held equal. Absolute magnitudes are calibrated to
realistic hosted-LLM agent ranges (single model step p50 ≈ 1.1–1.3 s)
solely so that relative effects appear at a plausible scale; they
inherit the rig's assumptions, all of which are flagged for human
verification in the repository. The same caveat is restated in the
threats-to-validity discussion below.

### B. Setup Recap

We executed the measurement study that Section V specifies, on an
open, deterministic mock rig released with this paper. The seven
patterns of Section IV are instantiated twice each, against locally
mocked Salesforce Agentforce 360 and Amazon Bedrock/AgentCore platform
clients that reproduce the *interface shapes* of the real platforms
(`invoke_agent`, AgentCore gateway/memory/identity/observability,
topics→actions, Agent Script, platform events, Omni-Channel handoff).
Latency EMERGES from pattern structure (task 101): P1 pays
plan + max-of-collaborators (tail-at-scale), P2 is additive over
scenario stages, P3 consumes from a decoupled bus, P4 pays a
write-contention term, P5 one gateway hop, P6 a configurable human
decision delay (lognormal, p50 ≈ 30 s; trace: configs/default.yaml
latency.shared.human_decision_delay), and P7 a cross-platform RTT.
The baseline grid crosses 7 patterns × 2 platforms × 3 scenarios = 42
conditions with n = 500 requests per condition (trace:
results/manifest.json fields n_baseline_conditions, n_per_condition).
The open-loop Poisson load generator first probes each condition's
single-replica saturation and then offers 0.7 × that rate (trace:
results/manifest.json fields utilization_target and per-condition
conditions.*.offered_utilization, all < 1), so no reported percentile
is an unbounded-queue artifact; submit and completion timestamps are
recorded separately, so reported latencies include queueing and are
free of coordinated omission. Every (pattern, platform, scenario)
condition draws from independent child random streams (SAP Option A,
task 103). The fault campaign sweeps 336 cells = 7 patterns × 2
platforms × 6 components × 4 fault types at 40 requests per cell on
scenario S1, with cross-request OUTAGE windows (trace:
results/manifest.json fields fault_campaign_cells,
fault_campaign_n_per_cell, fault_campaign_scenario;
configs/default.yaml faults.campaign.outage_window_fraction). The
master seed is 42 and the configuration hash, git revision, and wall
time (2.652 s) are recorded in the run manifest (trace:
results/manifest.json fields seed, config_hash, git_rev, wall_time_s).
All percentile estimates carry 95% BCa bootstrap confidence intervals;
pairwise pattern comparisons use Mann–Whitney U with rank-biserial and
Hodges–Lehmann effect estimates under Holm correction over the 21-pair
family per condition, per the pre-committed plan
(docs/STATISTICAL_ANALYSIS_PLAN.md). Table 4 — the fit-for-purpose
matrix — is figures/fit_matrix.csv: one platform-independent grade in
{Weak, Moderate, Strong} per (pattern, scenario), 21 cells, computed
from these Holm-corrected comparisons under the PRE-REGISTERED rule of
docs/FIT_RULE.md (stressed property per scenario, both-platform
pooling, structural capability gate); 10 of the paper's 21 published
cells reproduce, and the 11 that do not are recorded with measured
rationale in docs/FIT_DISCREPANCIES.md rather than forced (trace:
figures/fit_matrix.csv col fit_grade;
tests/fixtures/fit_agreed_cells.json pins the 10 agreed cells). A
richer per-platform four-dimensional quality view (A/B/C
equivalence-group grades on latency, reliability, cost, oversight) is
released as supplementary material
(figures/table4_supplementary.csv, grade function in docs/GRADES.md);
it is NOT the fit-for-purpose matrix. An automated agreement gate
(tests/test_paper_agreement.py) asserts the paper's directional
claims AND the 10 agreed Table-4 fit cells on every regeneration.

### C. Latency Results

Table 3 (figures/table3.csv) reports p50/p95/p99 with CIs for all 42
conditions; Fig. ccdf.png and Fig. p99_ci.png visualize the
distributions. Four structural effects dominate, each predicted by the
catalog's consequence analysis.

First, the pipeline's latency is additive over stages: P2 under the
multi-step S2 scenario (4–8 stages) records a p99 of 18,599.0 ms (95%
CI 16,499.8–19,905.7) on Bedrock versus 3,773.6 ms (CI 3,409.9–4,257.6)
for single-stage S1 — a ≈4.9× tail inflation — and 23,302.3 ms versus
4,550.6 ms (≈5.1×) on Agentforce (trace: figures/table3.csv rows
P2,bedrock,{S1,S2} and P2,agentforce,{S1,S2} cols p99_ms, p99_ci_lo,
p99_ci_hi; values rounded to 0.1 ms).

Second, the human-in-the-loop pattern P6 is latency-bound by the human,
not the machine: with a configurable human decision delay (p50 ≈ 30 s)
applied to the adjudicated fraction of requests, P6's p99 is the
highest of all patterns in every condition — e.g. 61,892.3 ms (CI
52,709.6–77,302.5) on Bedrock/S1 and 62,813.4 ms (CI
56,249.6–81,530.8) on Agentforce/S1, against machine-path medians of
1,628.1 ms and 1,997.9 ms respectively (trace: figures/table3.csv rows
P6,bedrock,S1 and P6,agentforce,S1 cols p50_ms, p99_ms and CI cols).
Oversight has a measured latency price; the supplementary
per-platform table (figures/table4_supplementary.csv) records it as a
C latency grade alongside the pattern's unique A oversight grade,
while Table 4 (figures/fit_matrix.csv) still grades P6 Strong for S3
— its tail inflation under burst is the smallest measured (p99
S3/S1 = 0.93 on Agentforce and 1.05 on Bedrock; trace: computed from
figures/table3.csv rows P6,*,{S1,S3} col p99_ms, rounded to 0.01) and
its selective human routing is the scenario's required capability.

Third, event-driven choreography absorbs bursts: under the bursty S3
scenario, P3's p99 inflation relative to its own S1 baseline is 1.03×
on Agentforce and 1.05× on Bedrock, versus 1.45×/1.74× for the
supervisor P1 and 5.23×/3.71× for the fixed chain P2 (trace: computed
from figures/table3.csv rows {P1,P2,P3},{agentforce,bedrock},{S1,S3}
col p99_ms; ratios rounded to 0.01). The decoupled consumer pool soaks
arrival bursts that a supervisor or a chain must queue.

Fourth, shared-state coordination is contention-bound: the blackboard
P4 degrades most under burst-driven concurrency, with S3 its worst
scenario on both platforms (p99 28,288.8 ms on Agentforce/S3 and
25,886.0 ms on Bedrock/S3 versus 20,062.1 / 12,450.3 ms under S1;
trace: figures/table3.csv rows P4,*,{S1,S3} col p99_ms).

Cross-platform deltas are small and configured (Agentforce model steps
carry a documented ≈+15% runtime-overhead median; Bedrock tool calls
pay one AgentCore gateway hop; trace: configs/default.yaml latency
section comments); no condition reaches the 60–190 s artifact range of
the pre-calibration run for machine-path patterns (P6's tail reflects
the modeled human, not queueing). Across all 42 baseline conditions
the measured error rate is 0.0 (trace: figures/table3.csv col
error_rate, all rows), as expected with fault injection disarmed;
reliability differences appear under the fault campaign below.

### D. Cost Results

Fig. cost_per_1k.png and the scenario-resolved ledger
(figures/cost_ledger.csv, 42 rows) report cost in USD per request
under the dated, HUMAN-gated pricing assumptions of configs/costs.yaml
(Bedrock: published token prices as of 2025-06; Agentforce: $2 per
conversation decomposed at 4 reasoning steps per conversation plus
$0.10 Flex action credits as of 2025-05 — all marked for human
verification). Three relative-cost properties are structural. (i)
Multi-step work costs more for every pattern: S2 exceeds S1 in all 14
(pattern, platform) pairs — e.g. P2 on Agentforce rises from $0.600 to
$3.677 per request and on Bedrock from $0.0056 to $0.0339 (trace:
figures/cost_ledger.csv rows P2,agentforce,{S1,S2} and
P2,bedrock,{S1,S2} col mean_cost_units; USD rounded to 3–4 decimals) —
because token volume scales with step count on Bedrock and per-step
Flex-credit actions accrue on Agentforce. (ii) Fan-out multiplies
spend: P1 (plan + 3 collaborators + synthesis, 5 model invocations)
costs $2.800 per request on Agentforce and $0.0281 on Bedrock under
S1, versus $0.600 / $0.0056 for the single-step chain P2 (trace:
figures/cost_ledger.csv rows P1,*,S1 and P2,*,S1 cols mean_cost_units,
mean_model_invocations). (iii) No path is zero-billed: Agentforce
Agent Script actions consume conversation/credit cost even without an
LLM call; the minimum mean per-request cost over all 42 conditions is
$0.0056 (P7 and P2 on Bedrock under S1; trace:
figures/cost_ledger.csv col mean_cost_units, minimum over all 42
rows, rounded to 4 decimals). The human reviewer's time in P6 is NOT billed as platform
cost; it is an out-of-scope operational cost (noted in
configs/costs.yaml) and appears only as latency. Per-scenario
cost-per-request values appear in Table 3's cost_per_request column
(trace: figures/table3.csv col cost_per_request). Sensitivity caveat:
the absolute Agentforce-versus-Bedrock cost gap (about two orders of
magnitude) is dominated by the $2/conversation Agentforce pricing
assumption (configs/costs.yaml, dated), not by topology; only the
WITHIN-platform pattern ordering is robust to that assumption
[HUMAN: confirm].

### E. Fault-Isolation Results

Because the model backend sits on every pattern's critical path, a
hard model_backend fault propagates across most patterns; the
fault-isolation DIFFERENTIATION among patterns is carried by the
orchestration-specific components (event_bus, gateway/tool,
memory_store, human_queue, bridge), and the matrix should be read
column-wise with that in mind (the figure caption states the same).

Fig. fault_matrix.png classifies each of the 336 campaign cells as
PROPAGATED (failures spread to requests that never traversed the
faulted component, or the structural unit's failure cascades),
ISOLATED (only requests traversing the faulted unit are affected),
ABSORBED (requests traverse the fault yet still succeed, at elevated
latency), or NOT_EXERCISED (the component is structurally irrelevant
to the pattern). The executed campaign yields 73 propagated, 15
isolated, 40 absorbed, and 208 not-exercised cells (trace:
results/faults.csv col classification, value counts). The mix matches
Table 3's consequences: the supervisor P1 and the blackboard P4
exhibit single-point-of-failure behavior (model-backend outage and
memory-store outage respectively are PROPAGATED on both platforms;
trace: results/faults.csv rows P1,*,model_backend,outage and
P4,*,memory_store,outage), the pipeline P2 propagates a stage fault
downstream (P2,*,model_backend,outage PROPAGATED), while the
choreography P3 ABSORBS a bus outage through buffered redelivery
(mean latency under fault 20.3–27.4 s versus 3.9–4.7 s baseline, with
requests still succeeding; trace: results/faults.csv rows
P3,*,event_bus,outage cols fault_mean_latency_s,
baseline_mean_latency_s, rounded to 0.1 s), the gateway P5 confines a
tool outage behind its bulkhead (ISOLATED: traversing requests
complete degraded — traversing_degraded_rate 1.0 — and non-traversing
success stays 1.0; trace: results/faults.csv row
P5,bedrock,S1,tool,outage), and the bridge P7 confines a remote-cluster
outage to the bridged work (ISOLATED with traversing_degraded_rate
1.0 on both platforms; trace: results/faults.csv rows
P7,*,model_backend,outage). The human-queue cells for P6 show
correctness isolation: under all four human_queue fault types on both
platforms, affected decisions are DEFERRED — latency rises but
traversing_success_rate remains 1.0 and no item is auto-approved
(trace: results/faults.csv rows P6,*,human_queue,* cols
classification == absorbed, traversing_success_rate). Throttle faults
are absorbed broadly (32 of the 40 absorbed cells; trace:
results/faults.csv, absorbed cells grouped by col fault) because
throttling delays but does not fail a request.

### F. Threats to Validity

*Construct (mock fidelity) — the principal limitation.* **The
platforms are local mocks; every result is a relative, structural
comparison under identical controlled mock conditions, not a
production SLA, vendor benchmark, or absolute performance claim.**
The mocks reproduce documented interface shapes and configured
latency/cost distributions, not the real Agentforce or Bedrock
services; the lognormal parameters (configs/default.yaml latency
section) and unit prices (configs/costs.yaml, dated and
HUMAN-flagged) are assumptions. What survives the mock boundary is
the *topology-induced ordering and isolation structure* — additive
stages, fan-out tails, burst absorption, contention growth,
human-dominated tails, SPOF versus bulkhead behavior — because those
follow from coordination structure under any service-time
distribution with comparable shape. The full study reruns in 2.652 s
wall time (trace: results/manifest.json field wall_time_s), so
sensitivity to these assumptions is cheap to explore.

*Internal.* All randomness is seeded (seed 42; trace:
results/manifest.json field seed) with independent child streams per
condition (SAP Option A), and same-seed runs are bit-identical,
eliminating run-to-run variance as a confounder but meaning the
reported CIs quantify sampling variability within the run, not
environmental variability.

*External (synthetic workloads).* The three scenarios are synthetic
stress shapes (S1 single-step retrieval QA, S2 4–8 step document
generation, S3 bursty triage with burst factor 5.0; trace:
configs/default.yaml scenarios section); real enterprise traffic mixes
will differ. The operating point (0.7 × measured saturation per
condition) is chosen to stress coordination below instability, not to
model any production deployment.

*Statistical.* Error rates of 0.0 in baseline mode make reliability
grades depend entirely on the fault campaign; with n = 40 per fault
cell, per-cell proportions are coarse. The Holm-corrected pairwise
family controls the comparisons behind Table 4's fit grades and the
supplementary table's quality grades, but no correction spans the
full 42-condition grid; the fit rule's stressed-property endpoints
(per-request S1 latency/cost, S2 growth factors, S3 slowest-decile
tail inflation; docs/FIT_RULE.md) and the supplementary table's
slowest-decile tail samples (docs/GRADES.md) are pre-committed but
human-reviewable choices, and 11 of 21 published fit cells did not
reproduce under the pre-registered rule (docs/FIT_DISCREPANCIES.md,
flagged for author adjudication).

---

[HUMAN: verify (1) each traced value against freshly regenerated
outputs of `bash run.sh`; (2) rounding conventions (0.1 ms for
latency, 3–4 decimals USD for cost, 0.01 for ratios) are acceptable
to the venue; (3) that figure filenames are replaced by manuscript
figure numbers; (4) the framing of P6's human-dominated tail and the
fault-matrix mix as confirmations of Table 3's consequences.]
