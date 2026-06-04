# plan.md — Build Plan: IEEE Access Reproducibility Package & Measurement Study

**Project:** AgentOrchPatterns-RepoPackage
**Paper:** "A Pattern Catalog for Multi-Agent Generative AI Orchestration Across Enterprise CRM and Hyperscaler Cloud Platforms" (S. Goel, IEEE Access submission)
**Primary goal:** Build the runnable artifact + executed measurement study that converts the paper from *"catalog with a prospective rig"* into *"catalog with an executed, open, reproducible evaluation"* — the single highest-leverage change for acceptance. The build is autonomous (local mock rig, no cloud, no credentials); the human only approves HUMAN-gated decisions.
**Completion promise:** `PAPER_ARTIFACT_COMPLETE`

---

## Phase 1 — Buildable-System Extraction

**The artifact.** The paper promises but does not ship a *reproducibility package*: seven pattern reference-implementation **pairs** (one Salesforce Agentforce 360 instantiation + one Amazon Bedrock instantiation each), a three-component **evaluation rig** (synthetic open-loop load generator = Algorithm 1; fault-injection campaign = Algorithm 2; cost-capture harness), the synthetic scenario workloads (S1/S2/S3), and a pattern-enumeration record (incl. 6 rejected candidates). The paper is explicit that the rig is *prospective* and the GitHub/Code Ocean links are `[USER: INSERT ...]` placeholders. The buildable system is therefore: **that package, plus the measurement study the paper names as its immediate next step** — executed against faithful local mocks so the structural-consequence claims (Section VI) and the fit-for-purpose matrix (Table 4) are backed by real numbers with confidence intervals.

**Core components and interaction.** (1) Mock platform clients reproducing the *shapes* of Bedrock `invoke_agent` / AgentCore `invoke_agent_runtime` + gateway/memory/identity/observability + Guardrails, and Agentforce topics→actions / Agent Script / platform events / Omni-Channel handoff. (2) Seven pattern implementations, each parameterized by platform, coordinating the mock agents per the paper's nine-element template. (3) Three synthetic scenarios stressing throughput (S1), multi-step coordination (S2), bursty load + human routing (S3). (4) The rig drives patterns under load and faults, capturing latency + cost telemetry. (5) A statistics pipeline (BCa bootstrap CIs, Mann–Whitney U + effect sizes, Holm–Bonferroni) turns telemetry into the paper's tables/figures. (6) A governance module demonstrates the HITL pattern against EU AI Act Art. 14 / NIST AI RMF / ISO 42001. (7) Packaging (README, CITATION.cff, Dockerfile, run.sh, capsule) makes it badge-eligible.

**Implementable software vs. non-code claims.** *Implementable:* the seven patterns, both platform instantiations (as mocks), all three rig components, all three scenarios, the statistics, the figures/tables, the HITL example, the packaging. *NOT code:* the scholarly admission criteria, the directional-reasoning prose, the regulatory mappings (we generate the mapping *tables* + a runnable HITL demo, but the legal interpretation is a HUMAN-reviewed claim), and the manuscript text (we draft, the author approves).

**What the paper assumes exists → we mock.** Real Agentforce 360 org, real Bedrock/AgentCore account, real foundation models, real billing surfaces — all mocked locally with parameterized latency/fault/cost so the study runs with zero cloud spend and zero credentials.

**Mapping to the goal (acceptance).** Where the paper's *prospective* posture diverges from the goal (*get accepted*), the goal wins: we execute the rig and report results, because comparable accepted IEEE Access papers (Khamis's factorial experiment; Toprani's 85% detection-rate headline) all carried a real evaluation. The honest mock-fidelity caveat is kept throughout.

---

## Phase 2 — Architecture Decision

**Stack: Python 3.11+ (chosen).** Justification: (1) The Bedrock/AgentCore SDK is `boto3` (Python), so mock clients mirror real method signatures exactly and read as drop-in — the fidelity reviewers will probe. (2) The pre-committed statistical plan is native in Python: `scipy.stats.bootstrap` does BCa CIs, `scipy.stats.mannwhitneyu` + `statsmodels` covers the non-parametric test + Holm/Bonferroni, and the bootstrap on p99 is a few lines. (3) Algorithms 1 and 2 are language-neutral pseudocode; Python is the most readable instantiation and the default expectation for an IEEE reproducibility capsule. (4) `pytest` gives clean, machine-verifiable done-checks so the loop self-verifies. (5) `simpy`/`asyncio` model open-loop load; `matplotlib` (Agg) renders headless IEEE figures. A TypeScript build would fight all five.

**High-level architecture.**
```
                    configs/*.yaml (seeds, rates, costs, alpha)
                                  |
   scenarios/ (S1 RAG, S2 DocGen, S3 Triage)  --> synthetic WorkItems
                                  |
   patterns/ (P1..P7, platform-parameterized)
        |  uses
        v
   clients/ (MockBedrock + MockAgentCore + Guardrails) | (MockAgentforce + events + OmniChannel)
        |  every call routed through  -> latency model + fault injector + cost model
        v
   rig/ loadgen(Alg1, open-loop) + faultcampaign(Alg2) + costcapture --> domain/telemetry sink
                                  |
   stats/ percentiles -> BCa bootstrap CIs ; Mann-Whitney U + effect size ; Holm-Bonferroni
                                  |
   study/ run_study --> results/ (raw) --> make_table3/4 + figures_* --> figures/
                                  |
   governance/ hitl_example + Article14/NIST/ISO mapping tables
                                  |
   packaging: README(5-sec) + CITATION.cff + Dockerfile + run.sh + capsule/  --> badge-eligible
```

**Data model.** `Agent(id, role)`, `WorkItem(id, scenario, payload, created_at)`, `WorkResult(item_id, status, payload, error)`, `LatencyRecord(request_id, pattern, scenario, platform, mode, submit_ts, complete_ts, fault, success)`, `CostRecord(request_id, pattern, platform, model_invocations, tokens, service_calls, cost_units)`, `Pattern(NINE_ELEMENTS, run())`, `FaultRecord(component, fault, contained?, requests_affected)`.

**Verification strategy.** Unit tests per module; seeded determinism tests; statistics validated against known distributions (CI coverage ≈95%, MWU on synthetic shifts); a smoke study; a clean-clone `run.sh` regenerating every figure; a demo smoke test. A task stops only when its exact done-check passes — never on "looks done."

**External boundaries NEVER crossed autonomously.** No real cloud API calls; no publishing to GitHub/Code Ocean/Zenodo; no DOI minting; no license finalization without confirmation; no real GitHub URL/DOI in the manuscript; no fabricated/over-rounded numbers; no auto-approval of any HUMAN-gated task.

---

## Phase 3 — Milestones

| ID | Name | Goal | Verify-check | ~Tasks |
|----|------|------|--------------|--------|
| M0 | Scaffolding + test harness | Repo, packaging, pytest, lint/CI, config/seeds | `pytest -q` passes a trivial test | 4 |
| M1 | Domain model | Types, agents, work items, telemetry records | domain tests pass | 3 |
| M2 | Mock platform clients | Faithful Bedrock/AgentCore + Agentforce mocks w/ latency, faults, cost | client parity + fault tests pass | 7 |
| M3 | Seven patterns | All 7 patterns, each on both platforms | `test_registry.py` all 7 run | 9 |
| M4 | Scenarios | S1/S2/S3 synthetic workloads | per-scenario tests pass | 3 |
| M5 | Evaluation rig | Open-loop loadgen (Alg1), fault campaign (Alg2), cost capture | rig component tests pass | 4 |
| M6 | Statistics | BCa CIs, Mann-Whitney+effect size, Holm-Bonferroni, pre-committed plan | stats validated vs known distributions | 5 |
| M7 | Measurement study | Execute full study; Tables 3/4, latency/cost/fault figures, decision tree, results map | `run_study --smoke` + figure scripts produce outputs | 8 |
| M8 | Governance | Runnable HITL example + Art.14/NIST/ISO mapping tables | HITL test passes; mapping files exist | 4 |
| M9 | Reproducibility packaging | README(5-sec), CITATION.cff, Dockerfile, run.sh, rejected-candidates, capsule, LICENSE | `bash run.sh` regenerates all figures | 7 |
| M10 | Demo + manuscript drafts | One-command demo; comparison table; results/abstract/governance drafts | `bash demo.sh` + demo test pass | 6 |
| M11 | End-to-end verification | Full suite green; clean-clone reproduction; completion gate | `pytest --cov` + fresh-clone `run.sh` green | 3 |

Milestone 0 establishes a passing test harness before any feature work. Tasks are dependency-ordered; no task depends on a later-numbered task.

---

## Phase 4 — Executable Task Backlog

> Every task follows the uniform template. **HUMAN-REVIEW-REQUIRED** marks the research-integrity gates: anything that produces a number/claim that goes into the manuscript, any statistical-correctness decision, any governance/compliance claim, any manuscript edit, or anything that publishes externally / touches licensing. The autonomous loop *implements* these but must NOT mark them passing, commit-as-final, or self-approve.

**The full per-task detail (Context / Do / Constraints / Done-check / Gate for all 63 tasks across M0–M11) is carried in `prd.json` (machine-readable, in this same folder) and in the chat-delivered `plan.md`. Task IDs, gates, dependencies, and verify-checks are authoritative in `prd.json`.** A condensed index follows; consult `prd.json` for the exact done-check command per task.

- **M0 (001–004):** scaffold packaging; pytest harness + trivial test; ruff + offline CI; deterministic config/seeds.
- **M1 (005–007):** core enums/types (7 patterns, 3 scenarios, fault types, 2 platforms, 2 modes); Agent + WorkItem; telemetry records (separate submit/complete timestamps).
- **M2 (008–014):** latency model; fault-injection hooks; MockBedrockClient (invoke_agent / invoke_agent_runtime shapes); MockAgentCore (runtime/memory/gateway/identity/observability) + Guardrails; MockAgentforceClient (topics/actions/Agent Script); platform events + Omni-Channel handoff w/ fallback; **per-platform cost model [HUMAN]**.
- **M3 (015–023):** Pattern base + nine-element metadata; P1 Supervisor-Collaborator; P2 Sequential Pipeline; P3 Event-Driven Choreography; P4 Shared-Memory Blackboard; P5 Tool-Routed Gateway; P6 Human-in-the-Loop; P7 Federated Cross-Platform Bridge; registry + uniform smoke test (all on both platforms).
- **M4 (024–026):** S1 RAG QA; S2 long-horizon doc-gen; S3 bursty incident-triage (synthetic only).
- **M5 (027–030):** open-loop load generator (Algorithm 1, avoids coordinated omission); Little's Law headroom + saturation finder; fault-injection campaign (Algorithm 2); **cost-capture harness [HUMAN]**.
- **M6 (031–035):** percentiles (p50/p95/p99/p99.9); **BCa bootstrap CIs [HUMAN]**; **Mann-Whitney U + rank-biserial + Hodges-Lehmann [HUMAN]**; **Holm/Bonferroni over enumerated 21+ comparisons [HUMAN]**; **pre-committed Statistical Analysis Plan [HUMAN]**.
- **M7 (036–043):** orchestrate full study (headless, seeded); **Table 3 synoptic comparison w/ CIs [HUMAN]**; **Table 4 fit-for-purpose matrix [HUMAN]**; **latency figures [HUMAN]**; **cost figures [HUMAN]**; **fault-isolation figures [HUMAN]**; decision tree (Fig 2); **results-to-paper map [HUMAN]**.
- **M8 (044–047):** runnable HITL example (confidence gate → human stub → immutable log → halt); **EU AI Act Article 14 mapping [HUMAN]**; **NIST AI RMF + 600-1 mapping [HUMAN]**; **ISO/IEC 42001 mapping [HUMAN]**.
- **M9 (048–054):** IEEE five-section README; CITATION.cff (1.2.0 + preferred-citation); pinned Dockerfile; run.sh master script; **rejected candidates record [HUMAN]**; Code Ocean/Zenodo capsule layout; **LICENSE [HUMAN]**.
- **M10 (055–060):** single-command demo; demo smoke test; **comparison table vs 10 papers [HUMAN]**; **manuscript results section [HUMAN]**; **manuscript abstract/scope reframe + placeholder fills [HUMAN]**; **manuscript governance section + rebuttal prep [HUMAN]**.
- **M11 (061–063):** full suite green w/ coverage; clean-clone reproducibility verification; final completion gate (emit `PAPER_ARTIFACT_COMPLETE`).

**21 HUMAN-gated tasks:** 014, 030, 032, 033, 034, 035, 037, 038, 039, 040, 041, 043, 045, 046, 047, 052, 054, 057, 058, 059, 060. **42 AUTO.** See `prd.json` for the exact, runnable done-check on every task and `CLAUDE.md` for gate semantics. The chat-delivered `plan.md` contains the fully expanded Context/Do/Constraints/Done-check prose for each of the 63 tasks.
