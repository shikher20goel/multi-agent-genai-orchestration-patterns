# Reviewer-Rebuttal Preparation (Task 060, HUMAN-gated)

Anticipated reviewer objections to the reframed submission (executed
study on an open mock rig), each with a grounded response referencing
repository artifacts. [HUMAN: verify each response's factual claims
against the cited artifacts before use; adapt tone to the actual
review.]

---

## Objection 1 — Mock fidelity: "You measured mocks, not Agentforce or Bedrock. The numbers are meaningless."

**Response.** The study's claims are explicitly comparative and
structural, never absolute (see the threats-to-validity subsection,
docs/manuscript/results_section.md §E, and the revised abstract's
caveat, docs/manuscript/abstract_scope_reframe.md). The mocks
reproduce the documented *interface shapes* of both platforms
(`src/agentorch/clients/bedrock.py`, `src/agentorch/clients/agentforce.py`)
and the patterns' *coordination topologies* exactly; service times and
prices are configured assumptions, isolated in two files
(`configs/default.yaml` latency section, `configs/costs.yaml`) and
flagged HUMAN-gated. The structural conclusions — fan-out topologies
saturate first under open-loop load, event choreography minimizes
per-request work, bulkheads and the bridge contain faults
(0 propagated cells of 336; trace: results/faults.csv) — follow from
topology, not from the particular lognormal parameters, and any reader
can re-run the entire study under different assumptions in under three
seconds of wall time (trace: results/manifest.json field wall_time_s =
2.663). The catalog tradition the paper sits in ([1], [2]) accepts
catalogs with *no* measurement; this artifact strictly adds executed,
reproducible evidence. Measuring the real platforms requires paid
accounts, NDAs on internal latencies, and non-determinism that defeats
exact reproduction; the mock rig is what makes the study *open*.

## Objection 2 — Synthetic workloads: "S1–S3 are invented; real enterprise traffic differs."

**Response.** Acknowledged in threats-to-validity (results_section.md
§E, External). The three scenarios are platform-stress shapes chosen
to span the design dimensions the catalog claims to discriminate:
single-step throughput (S1), long-horizon sequential coordination
(S2, 4–8 stages), and bursty load with human routing (S3, burst factor
5.0) (trace: configs/default.yaml scenarios section). They are not
claimed to model any production trace; they are the controlled stimuli
under which structural differences become measurable — e.g., S2 is
what separates P2's two platform instantiations by two orders of
magnitude at p99 (trace: figures/table3.csv rows P2,bedrock,S2 p99_ms
188916.5 vs P2,agentforce,S2 p99_ms 1666.2). Scenario generators are
seeded, parameterized, and open (`src/agentorch/scenarios/`), so a
reviewer or reader can substitute their own workload shape.

## Objection 3 — Single author: "One author; no independent validation of the catalog or the study."

**Response.** The artifact is designed so that validation does not
rest on author authority: every number regenerates from one command
(`run.sh`), provenance is recorded (results/manifest.json: seed,
config hash, git revision), the analysis plan was committed before
results were drafted (docs/STATISTICAL_ANALYSIS_PLAN.md), every
manuscript number carries a machine-checkable trace
(docs/RESULTS_TO_PAPER_MAP.md), and the test suite (185+ tests,
`pytest --cov`) pins the rig's semantics, including
coordinated-omission correctness of the load generator
(tests/test_loadgen.py). The pattern-admission methodology is likewise
auditable: criteria are stated (manuscript Section III.A) and the six
rejected candidates are recorded with criterion-failure rationales
(docs/REJECTED_CANDIDATES.md). Independent reproduction is exactly
what the IEEE Access badge process provides; the artifact targets it.

## Objection 4 — Cost-model assumptions: "Cost units from a YAML file are not costs."

**Response.** Correct, and the paper says so: prices live solely in
`configs/costs.yaml` with sources and dates in comments, are flagged
as HUMAN-gated assumptions, and results are reported in *cost units*,
not currency (results_section.md §C). The load-bearing findings are
ratio and mechanism findings that survive any monotone re-pricing
within a platform: P4 on Agentforce costs 3x P1 on the same platform
because it makes 3 model invocations plus 6 service calls per request
versus P1's 1 invocation (trace: figures/cost_ledger.csv rows
P4,agentforce cols mean_cost_units 1.5000045, mean_model_invocations
3.0, mean_service_calls 6.0; row P1,agentforce mean_cost_units
0.500003, mean_model_invocations 1.0); P2/P3 on Agentforce are ~5
orders cheaper because they invoke no model at all (trace:
figures/cost_ledger.csv rows P2,agentforce 4.013e-06 and P3,agentforce
3.0e-06 col mean_cost_units). The invocation and service-call *counts*
are structural facts of the topologies; the prices are a transparent,
swappable lens.

## Objection 5 — Statistical choices: "Why BCa bootstrap, Mann–Whitney, Holm? Why n = 500?"

**Response.** The choices are pre-committed and justified in
docs/STATISTICAL_ANALYSIS_PLAN.md: latency distributions are heavy-
tailed (lognormal service times compounded by queueing), so
nonparametric methods are appropriate — Mann–Whitney U for pairwise
location comparison with rank-biserial and Hodges–Lehmann estimates
for effect size and interpretable magnitude
(`src/agentorch/stats/compare.py`), BCa bootstrap for percentile CIs
because BCa corrects bias and skew where percentile bootstrap fails on
tail quantiles (`src/agentorch/stats/bootstrap.py`, scipy
method='BCa'), and Holm over the 21-pair family per condition because
it controls FWER uniformly more powerfully than Bonferroni without
independence assumptions (`src/agentorch/stats/correction.py`). n =
500 per condition gives stable p99 estimation (the 99th percentile of
n = 500 rests on ~5 order statistics, with CI width reported rather
than hidden; trace: figures/table3.csv cols p99_ci_lo/p99_ci_hi).
The implementations are unit-tested against analytic distributions
(tests/test_percentiles.py, tests/test_bootstrap.py). [HUMAN: verify
the plan's wording matches docs/STATISTICAL_ANALYSIS_PLAN.md before
quoting it.]

## Objection 6 — "The governance mappings are compliance theater: a mock cannot comply with the EU AI Act."

**Response.** The paper claims structural feasibility, not compliance:
each mapping document opens and closes with that limitation
(docs/governance/eu_ai_act_article14.md Limitations §1–2; iso42001.md
Limitations; nist_ai_rmf.md Limitations) and the manuscript draft
repeats it (docs/manuscript/governance_section.md §D). What the
artifact adds over a narrative claim is *runnable evidence* that the
required mechanisms compose: a confidence gate, an attributable human
decision, a tamper-evident audit chain, and tested stop semantics
(governance/hitl_example.py; tests/test_hitl_example.py, including
halt-stops-chain and tamper-detection tests). To the author's
knowledge, peer catalogs in this space (docs/COMPARISON_TABLE.md,
governance-mapping column) offer no equivalent runnable artifact.
[HUMAN: verify the comparison-table cells before asserting this.]

## Objection 7 — "Zero propagated cells looks too clean; is the containment metric rigged?"

**Response.** The containment contract is stated up front
(docs/ARCHITECTURE_CONTRACT.md, rig/faultcampaign.py: contained iff
non-traversing requests' success rate ≥ 0.95; trace:
configs/default.yaml faults.containment_threshold) and the campaign
distinguishes *absorbed* (traversing requests still succeed: 28 cells,
of which 25 are throttle cells, since throttling delays rather than
fails) from *isolated* (traversing requests fail but others do not: 72
cells) — so the matrix is not claiming faults are harmless, only that
they did not spread (trace: results/faults.csv classified per
agentorch/study/figures_fault.py rules; min
non_traversing_success_rate = 1.0 over all 336 rows). Zero propagation
is a property of the *patterns as implemented with the catalog's
prescribed boundaries* (bulkheads, fault-domain separation); the rig
is capable of recording propagation, and the classification logic is
unit-tested (tests/test_faultcampaign.py). The honest caveat — n = 40
per cell makes per-cell proportions coarse — is in
threats-to-validity. [HUMAN: confirm this framing; a reviewer may
reasonably ask for a deliberately propagating anti-pattern as a
positive control, which would be a good revision experiment.]

---

[HUMAN: verify every number and artifact path above; decide which
responses to fold into the paper proactively (Objections 1, 4, 7 are
candidates for the threats-to-validity text) versus hold for rebuttal.]
