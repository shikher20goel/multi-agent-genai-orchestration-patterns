# HUMAN decision queue — AgentOrchPatterns-RepoPackage
All 21 HUMAN-gated tasks are implemented, tested, committed on `autonomous-build`, and flagged in `progress.txt`. Nothing below is marked passing or self-approved. Review order is the recommended batch order.

## Batch 1 — Cost model assumptions (tasks 014, 030; REVISED by Phase 2 task 105)
**Phase 2 task 105 update:** the unit is now explicitly USD per request under dated assumptions; Agentforce Agent Script actions bill one Flex action credit each (USD 0.10 list, 2025-05 Flex pricing announcement, [HUMAN: verify]) so no path is zero-billed; multi-step S2 work scales token volume (Bedrock) and per-step actions (Agentforce), making S2 > S1 cost per pattern and P1 fan-out > P2 single chain; HITL human time is documented as out-of-scope operational cost, not platform cost; the ledger is scenario-resolved (42 rows). Decisions needed: verify the Flex-credit price + the $2/conversation decomposition, and the content-scaling assumption (tokens proportional to step count).

- **What:** `src/agentorch/cost.py` + `configs/costs.yaml` (every unit price carries a source comment + as-of date) and `rig/costcapture.py` -> `figures/cost_ledger.csv`, `figures/cost_per_1k.png`.
- **Produced:** Bedrock token prices referenced to the AWS public pricing page (as-of 2025-06, marked [HUMAN: verify]); AgentCore per-service-call prices are labeled PLACEHOLDERS (no authoritative public price assumed); Agentforce $2/conversation decomposition referenced to the Salesforce 2024-09 announcement, PLACEHOLDER.
- **Decision needed:** confirm or replace each unit price and its dated source; decide whether AgentCore service-call pricing stays in the model or is folded into a single per-invocation overhead; confirm P2-on-Agentforce billing 0 model invocations (Agent Script actions only) is the intended semantics.
- **Default:** keep current structure, update the four AgentCore placeholders + Agentforce decomposition from current public pages, re-run `bash run.sh` (regenerates ledger + figures deterministically).

## Batch 2 — Statistics (tasks 032–035)
- **What:** `stats/bootstrap.py` (BCa via scipy, coverage-tested ~95%), `stats/compare.py` (Mann–Whitney U + rank-biserial + Hodges–Lehmann, validated on synthetic shifts), `stats/correction.py` (Holm, family = 21 pairwise pattern comparisons per platform×scenario, FWER-simulated), `docs/STATISTICAL_ANALYSIS_PLAN.md` (pre-committed SAP referencing the implemented functions).
- **Decision needed:** sign off each method choice and the SAP, including: alpha=0.05; family definition (21 per condition, not a global family across all 6 conditions); and the noted caveat that all conditions share a common latency RNG stream (common random numbers — variance-reducing but conditions are correlated; SAP documents it).
- **Default:** accept as implemented; the CRN caveat stays disclosed in the SAP and threats-to-validity.

## Batch 3 — Tables and figures (tasks 037–041; Table 4 REWRITTEN by Phase 2 task 106)
**Phase 2 task 106 update:** Table 4 grades are now equivalence-group grades computed through the MWU/Holm machinery on per-request data (A = best Holm-significant equivalence group; C = dominated by ≥4 others; B otherwise), with latency graded on the slowest-decile tail (the p99 region), reliability on the per-request failure indicator under the fault campaign, cost on per-request USD, and a NEW oversight column derived from pattern capability metadata (P6 = A, unique). Grade function documented in `study/make_table4.py` docstring + `docs/GRADES.md`; directional paper agreement asserted in `tests/test_paper_agreement.py`. Decisions needed: confirm the grade thresholds, the tail-decile choice, and the oversight metadata rule.

- **What:** `figures/table3.csv` (42 rows: n=500/condition, p50/p95/p99 + BCa CIs, error rate, throughput, cost/req), `figures/table4_supplementary.csv` (supplementary per-platform A/B/C grades + oversight column, per `docs/GRADES.md`; the paper-Table-4 fit matrix is `figures/fit_matrix.csv`), `figures/ccdf.png`, `p99_ci.png`, `cost_per_1k.png`, `fault_matrix.png`.
- **Decision needed:** verify numbers match `results/` (regenerate with `bash run.sh`; deterministic seed=42), the Table-4 grading rules are the story you want, labeling is right. Fault matrix: of 336 cells, 28 absorbed / 72 isolated / 0 propagated / rest not-exercised; "traversal" operationalized as "fault fired on the request" — confirm this matches the paper's containment definition.
- **Default:** accept; tweak only labels/captions at manuscript time.

## Batch 4 — Results-to-paper map (task 043)
- **What:** `docs/RESULTS_TO_PAPER_MAP.md` — every output mapped to its paper element with generating command + source CSV.
- **Decision needed:** confirm completeness against your target paper structure.

## Batch 5 — Governance mappings (tasks 045–047)
- **What:** `docs/governance/eu_ai_act_article14.md` (all Art. 14(4)(a)–(e) clauses -> code/rig evidence), `nist_ai_rmf.md` (4 functions + AI 600-1; MEASURE rows point at rig outputs), `iso42001.md` (clauses 4–10 + Annex A; agentic gap noted). All carry mock-rig/not-legal-advice limitations.
- **Decision needed:** accuracy sign-off on every regulatory claim; these are the highest-risk reviewer-facing claims.

## Batch 6 — Rejected candidates (task 052)
- **What:** `docs/REJECTED_CANDIDATES.md`. The paper PDF does NOT enumerate the six rejected candidates, so six were derived from the paper's admission criteria — each marked [HUMAN: verify rationale].
- **Decision needed:** replace/confirm the six candidates and their criterion-failure rationales with your actual enumeration record.

## Batch 7 — LICENSE (task 054)
- **What:** Full Apache-2.0 text, copyright 2026 Shikher Goel. Recommendation: Apache-2.0 (patent grant; standard for IEEE artifacts).
- **Decision needed:** confirm Apache-2.0 or choose another.

## Batch 8 — Comparison table (task 057)
- **What:** `docs/COMPARISON_TABLE.md` — 10 related works extracted from the paper's Related Work ([1],[5],[8],[9],[14],[45],[46],[52],[60]...) vs this paper across artifact/eval/stats/cross-platform/governance columns. Citations marked [HUMAN: verify].
- **Decision needed:** verify the 10 selections + each cell's claim about the cited work.

## Batch 9 — Manuscript drafts (tasks 058–060; plus Phase 2 task 107 AI-use disclosure)
**Phase 2 task 108:** `docs/manuscript/results_section.md` fully rewritten to the RECALIBRATED numbers (every value traced to the task-110 regeneration) with the mock-fidelity caveat PROMINENT: a "Scope of the Evidence" first paragraph and the threats-to-validity section both state results are relative structural comparisons under identical controlled mock conditions, not production SLAs; `abstract_scope_reframe.md` re-checked (no stale numbers). Decision needed: verify every traced number against a fresh `bash run.sh` and approve the framing.
**Phase 2 task 107:** `docs/manuscript/ai_use_disclosure.md` — accurate disclosure that a Claude-based agentic AI pipeline generated the reference implementations, the evaluation rig, the executed study, the figures/tables, and drafted manuscript sections, with the author specifying the design, verifying everything, and taking full responsibility. Decision needed: verify current IEEE AI-disclosure wording/placement and approve the statement.

- **What:** `docs/manuscript/results_section.md` (every number carries an inline trace to figures/ or results/), `abstract_scope_reframe.md` (original abstract quoted verbatim, revision + 8-item change list, [USER: INSERT GITHUB URL]/[USER: INSERT DOI] slots), `governance_section.md`, `rebuttal_prep.md` (7 objections with grounded responses).
- **Decision needed:** approve each draft; paste final GitHub URL + DOI into the marked slots yourself. No real URL/DOI was inserted anywhere.

## Publish steps (HUMAN-only, in order, when you say go)
1. Provide GitHub credential -> push `autonomous-build`; review diff; merge to `main` when satisfied.
2. Flip repo public (submission time only).
3. Code Ocean: create capsule from `capsule/` layout (metadata.yml ready) OR Zenodo: new upload, attach release zip, CITATION.cff present; mint DOI.
4. Paste repo URL + DOI into the two manuscript slots; only then finalize abstract/data-availability text.

## Phase 3 batch — fit-matrix reconciliation (tasks 201–207)

**Context.** Phase 2's per-platform A/B/C table contradicted the
paper's Table 4 (a single platform-independent Weak/Moderate/Strong
fit grade per pattern × scenario). Phase 3 pre-registered a fit rule
(`docs/FIT_RULE.md`, written BEFORE first computation; no
post-computation rule changes — Changelog empty after the initial
entry), computed `figures/fit_matrix.csv` from the measured results,
and compared to the paper's 21 published cells. The old table is now
`figures/table4_supplementary.csv` and is explicitly labeled NOT the
fit-for-purpose matrix.

### Decision 1 — 11 discrepant fit cells [HUMAN]

10 of 21 published cells reproduce (pinned in
`tests/fixtures/fit_agreed_cells.json` and asserted by the agreement
suite). The 11 that do not are recorded with measured numbers and an
honest calibration-vs-refinement read in `docs/FIT_DISCREPANCIES.md`:

- **Evidence-based refinement candidates (3):** P1-S1
  (Moderate→Weak: 5-invocation fan-out is worst-group on both
  throughput proxy and cost), P3-S1 (Moderate→Weak: per-event-hop
  latency/cost price), P7-S2 (Moderate→Weak: per-step bridge cost
  amplification, the paper's own stated mechanism, measured as
  worst-group).
- **Calibration/construct issues (8):** P1-S2, P2-S1, P2-S2, P5-S1,
  P5-S3, P6-S1, P7-S1, P7-S3 — in each, the rig's pre-registered
  stressed property (latency/cost growth, p99 inflation) does not
  capture the axis the paper's cell rationale names (order-match/
  completion, fault containment, conditional cross-platform reach,
  parallel dispatch/cost attributability, closed-loop human
  throttling, adaptive-decomposition payoff, multi-stage S1 chain).
  The orthogonal claims (e.g. P5 bulkhead ISOLATED, P7 remote-cluster
  outage ISOLATED, P1/P2 best S2 completion) ARE separately confirmed
  by the fault campaign and the Phase-2 agreement suite.

**Decision needed:** per cell, either (a) keep the paper grade and
treat the rig result as a documented calibration limitation, (b)
revise the paper cell to the computed grade (refinement), or (c)
direct a scenario/rig recalibration (e.g. closed-loop human queue for
P6-S1, multi-stage S1 for P2) and recompute. The computed grades stay
as computed until you decide; nothing was forced.

### Decision 2 — $2/conversation cost sensitivity caveat [HUMAN: confirm]

The cost results note (manuscript draft + figures_cost output note)
now states that the Agentforce-vs-Bedrock absolute cost gap (~two
orders of magnitude) is dominated by the $2/conversation Agentforce
pricing assumption in `configs/costs.yaml`, with only the
within-platform pattern ordering robust to it. **Decision needed:**
confirm the caveat wording and the underlying $2/conversation
decomposition (links to Batch 1).

### Also in this batch

- Task 206 manuscript update (fit_matrix.csv as Table 4,
  table4_supplementary.csv as supplementary, numbers re-traced) —
  awaiting review like the rest of Batch 9.
- The pre-registered rule itself (`docs/FIT_RULE.md`: stressed
  properties, pooling, upgrade-only capability gate, capability
  flags with structural justifications) is reviewable; any change you
  direct goes through its §Changelog.
