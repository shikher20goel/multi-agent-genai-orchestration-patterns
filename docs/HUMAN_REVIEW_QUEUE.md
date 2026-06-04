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

- **What:** `figures/table3.csv` (42 rows: n=500/condition, p50/p95/p99 + BCa CIs, error rate, throughput, cost/req), `figures/table4.csv` (A/B/C equivalence-group grades + oversight column, per `docs/GRADES.md`), `figures/ccdf.png`, `p99_ci.png`, `cost_per_1k.png`, `fault_matrix.png`.
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

## Batch 9 — Manuscript drafts (tasks 058–060)
- **What:** `docs/manuscript/results_section.md` (every number carries an inline trace to figures/ or results/), `abstract_scope_reframe.md` (original abstract quoted verbatim, revision + 8-item change list, [USER: INSERT GITHUB URL]/[USER: INSERT DOI] slots), `governance_section.md`, `rebuttal_prep.md` (7 objections with grounded responses).
- **Decision needed:** approve each draft; paste final GitHub URL + DOI into the marked slots yourself. No real URL/DOI was inserted anywhere.

## Publish steps (HUMAN-only, in order, when you say go)
1. Provide GitHub credential -> push `autonomous-build`; review diff; merge to `main` when satisfied.
2. Flip repo public (submission time only).
3. Code Ocean: create capsule from `capsule/` layout (metadata.yml ready) OR Zenodo: new upload, attach release zip, CITATION.cff present; mint DOI.
4. Paste repo URL + DOI into the two manuscript slots; only then finalize abstract/data-availability text.
