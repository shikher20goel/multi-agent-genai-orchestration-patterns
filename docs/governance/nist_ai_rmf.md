# NIST AI RMF 1.0 + Generative AI Profile (NIST AI 600-1) Mapping (Task 046, HUMAN-gated)

**Scope.** This document maps the four functions of the NIST AI Risk
Management Framework 1.0 (NIST AI 100-1, Jan. 2023) — **GOVERN, MAP,
MEASURE, MANAGE** — and selected actions of the **Generative AI
Profile (NIST AI 600-1, Jul. 2024)** to concrete artifacts in this
repository. The intent mirrors the manuscript's Section IV.G claim
that pattern P6 is "the structural means of satisfying human-oversight
obligations" under the NIST AI RMF.

## Mapping table — AI RMF functions

| Function | Subcategory (representative) | Repository evidence (concrete paths) | How the artifact supports the function |
|---|---|---|---|
| **GOVERN** | GOVERN 1.2 / 1.4 — policies, accountability structures, and risk documentation are in place | `CLAUDE.md` (HUMAN-gated task policy: any manuscript number, statistical decision, or compliance claim requires human sign-off), `docs/STATISTICAL_ANALYSIS_PLAN.md` (pre-committed analysis plan), `docs/RESULTS_TO_PAPER_MAP.md` (claim-to-evidence traceability), hash-chained `AuditLog` in `governance/hitl_example.py` | The build itself runs under an explicit accountability policy: machine-generated claims cannot self-approve. The append-only audit log gives a tamper-evident accountability record for oversight decisions (`verify_chain()`). |
| **GOVERN** | GOVERN 3.2 — human oversight roles and responsibilities are defined | `src/agentorch/patterns/p6_hitl.py` (`pause`/`resume` with named `reviewer`), `governance/hitl_example.py` (`human_decision` audit events carry `reviewer`) | The reviewer role is an explicit, logged actor in the control flow, not an informal step. |
| **MAP** | MAP 1.1 / 2.x — context, capabilities, and limitations of the AI system are documented | Nine-element `Pattern.meta()` for all seven patterns (`src/agentorch/patterns/p*.py`; keys include `context`, `problem`, `forces`, `consequences`, `governance_hooks`), `figures/decision_tree.png`, `docs/ARCHITECTURE_CONTRACT.md` | Each orchestration pattern's intended context, forces, and consequences are machine-checkable documentation (`validate_meta` in `src/agentorch/patterns/base.py`), and the decision tree maps workload context to pattern choice. |
| **MAP** | MAP 5.1 — impacts (likelihood/magnitude) of system behavior are characterized | `results/faults.csv` (336-cell fault campaign), `configs/default.yaml` (`faults.campaign` grid: 6 components x 4 fault types x 7 patterns x 2 platforms) | The fault campaign systematically enumerates failure modes per component and characterizes whether each is contained or propagates — an executed impact map. |
| **MEASURE** | MEASURE 2.5 — AI system performance is demonstrated to be valid and reliable; **rows must point at concrete rig outputs** | `figures/table3.csv` (p50/p95/p99 latency with 95% BCa CIs, error rate, throughput, cost per request, n=500 per condition), `figures/ccdf.png`, `figures/p99_ci.png`, `results/manifest.json` (seed=42, config hash, git revision) | Performance claims are measured, not asserted: every number is regenerable from `bash run.sh` with recorded provenance. |
| **MEASURE** | MEASURE 2.6 — system is evaluated in conditions similar to deployment, including failure modes | `figures/fault_matrix.png` (absorbed / isolated / propagated / not-exercised grid per platform), `results/faults.csv`, `src/agentorch/rig/faultcampaign.py` (Algorithm 2) | Fault-mode behavior is exercised and visualized per (pattern, component, fault type) cell rather than assumed. |
| **MEASURE** | MEASURE 2.9 / 4.2 — results of measurement are documented with statistical rigor | `docs/STATISTICAL_ANALYSIS_PLAN.md`, `src/agentorch/stats/bootstrap.py` (BCa CIs), `src/agentorch/stats/compare.py` (Mann-Whitney U, rank-biserial, Hodges-Lehmann), `src/agentorch/stats/correction.py` (Holm), `figures/table4.csv` (grades derived under that plan) | The measurement pipeline is pre-committed and multiple-comparison-corrected; effect sizes accompany p-values. |
| **MANAGE** | MANAGE 2.3 / 2.4 — mechanisms to respond to, recover from, and **deactivate/disengage** the system | `AuditLog.halt()` (`governance/hitl_example.py`; emergency stop closing the chain), P5 per-tool bulkheads (`src/agentorch/patterns/p5_gateway.py`), P7 fault-domain containment (`src/agentorch/patterns/p7_bridge.py`, `tests/test_p7.py`: full remote outage contained) | Disengagement (halt) and degradation-containment (bulkheads, bridge isolation) are implemented and tested, not aspirational. |
| **MANAGE** | MANAGE 4.1 — post-deployment monitoring and incident response | `TelemetrySink` (`src/agentorch/telemetry.py`) capturing latency/cost/fault records per request; scenario S3 (bursty incident triage with human-routing fraction, `src/agentorch/scenarios/`) | Incident-shaped load (S3) is a first-class evaluated scenario, with human routing below the HITL threshold. |

## Generative AI Profile (NIST AI 600-1) — selected actions

| AI 600-1 concern | Repository evidence | Note |
|---|---|---|
| Human-AI configuration: define when GAI output requires human review | Confidence gate + threshold (`HitlGovernor.confidence_threshold`, `governance/hitl_example.py`); P6 routing fraction in S3 (`configs/default.yaml`) | Threshold is an explicit, tunable governance parameter. |
| Information integrity / provenance of GAI artifacts | Draft hash (`draft_sha256`) recorded in each `draft_produced` audit event; hash-chained log (`verify_chain()`) | Output provenance is tamper-evident. |
| Content moderation hooks | `MockGuardrails.apply(mode="shadow")` (`src/agentorch/clients/bedrock.py`) — shadow-logs, never blocks, in this rig | Demonstrates the *hook placement*; real moderation efficacy is out of scope (mock). |
| Decommissioning / safe shutdown of GAI workflows | `AuditLog.halt()`; `tests/test_hitl_example.py::test_halt_stops_chain_mid_stream` | Stop semantics are tested. |

## Limitations

1. **Mock rig.** All measurements come from locally mocked platforms
   with synthetic lognormal service times (`configs/default.yaml`) and
   synthetic workloads; MEASURE evidence demonstrates the
   *measurement apparatus and method*, not production risk levels of
   any real GAI deployment.
2. **Subcategory identifiers are representative.** The RMF subcategory
   numbers above are the author's best-effort selection of the closest
   subcategories; the framework's playbook contains many more.
   [HUMAN: verify each subcategory ID against NIST AI 100-1 and the
   AI 600-1 action tables before citing them in the manuscript.]
3. **No claim of RMF conformance.** The AI RMF is voluntary and
   outcome-oriented; this mapping shows where the artifact provides
   supporting evidence, not that any organization "complies."
