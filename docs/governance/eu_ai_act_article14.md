# EU AI Act Article 14 — Human Oversight Mapping (Task 045, HUMAN-gated)

**Scope.** This document maps the human-oversight requirements of
Regulation (EU) 2024/1689 ("EU AI Act"), Article 14, to concrete,
runnable artifacts in this repository — principally pattern **P6
Human-in-the-Loop Adjudication** (`src/agentorch/patterns/p6_hitl.py`)
and the standalone governance demo
(`governance/hitl_example.py`, tested by `tests/test_hitl_example.py`).
Article 14 applies to high-risk AI systems (Annex III), with the
relevant obligations applicable from August 2, 2026 (as stated in the
manuscript, Section IV.G).

Article 14(1)–(3) require that high-risk AI systems be designed and
developed such that they **can be effectively overseen by natural
persons** during use, through measures built into the system by the
provider and/or identified for implementation by the deployer. The
operative design measures are enumerated in **Article 14(4)(a)–(e)**,
each mapped below.

## Mapping table — Article 14(4)(a)–(e)

| Clause | Requirement (paraphrase) | Repository evidence (concrete paths) | How the evidence addresses the clause |
|---|---|---|---|
| **14(4)(a)** | The overseer can properly understand the relevant capacities and limitations of the system and duly monitor its operation, including detecting anomalies, dysfunctions, and unexpected performance. | `figures/table3.csv`, `figures/table4.csv`, `figures/ccdf.png`, `figures/p99_ci.png`, `figures/fault_matrix.png`; observability hooks `MockAgentCore.observability_emit` (`src/agentorch/clients/bedrock.py`); telemetry schema `src/agentorch/telemetry.py`; provenance `results/manifest.json` | The recalibrated executed study quantifies each pattern's measured capacities (latency percentiles with 95% BCa CIs, error rates, throughput, cost per request) and limitations (four-way PROPAGATED/ISOLATED/ABSORBED/NOT_EXERCISED fault classification in `fault_matrix.png`, including P6 `human_queue` fault cells showing deferred-not-auto-approved behavior), and Table 4 now carries an explicit metadata-derived oversight column (`docs/GRADES.md`). This gives an overseer an empirical baseline against which anomalies and dysfunctions can be detected. Every boundary call emits telemetry an overseer can monitor. |
| **14(4)(b)** | The overseer remains aware of the possible tendency to automatically rely on the output ("automation bias"), in particular for systems providing information or recommendations for decisions by natural persons. | Confidence gate in `governance/hitl_example.py` (`HitlGovernor.review`, `confidence_threshold`); P6 `pause()` in `src/agentorch/patterns/p6_hitl.py`; test `tests/test_hitl_example.py::test_confidence_gate_routes_low_confidence_to_human_stub` | The design counteracts automation bias structurally: low-confidence outputs are *not presented as finished decisions* — they are paused and routed to a human queue with the confidence score and threshold explicitly logged (`routed_to_human` audit event), so the human sees that the system itself flagged uncertainty rather than an authoritative answer. |
| **14(4)(c)** | The overseer can correctly interpret the system's output, taking into account the available interpretation tools and methods. | Nine-element pattern metadata via `Pattern.meta()` (`src/agentorch/patterns/base.py`), including `consequences` and `governance_hooks` per pattern; `figures/decision_tree.png`; audit payloads carrying `confidence`, `threshold`, and a draft hash in `governance/hitl_example.py` | Each output reaching a human is accompanied by interpretable context: which pattern produced it, the pattern's documented consequences, and the quantitative confidence relative to the gate threshold. The decision tree documents *why* a given pattern (and thus a given output pathway) was selected. |
| **14(4)(d)** | The overseer can decide not to use the system, or otherwise disregard, override, or reverse its output. | `HitlGovernor.review` approve/reject path and `human_decision` audit event (`governance/hitl_example.py`); P6 `resume(token, decision)` in `src/agentorch/patterns/p6_hitl.py` accepting "approve" or "reject"; tests `tests/test_p6.py`, `tests/test_hitl_example.py::test_custom_human_stub_decision_is_logged` | The human stub can **reject** any draft, which terminates that output's path — a concrete override/disregard mechanism. The decision (either way) is recorded in the hash-chained `AuditLog` so the override is itself auditable and non-repudiable (`verify_chain()`). |
| **14(4)(e)** | The overseer can intervene in the operation or interrupt the system through a "stop" button or similar procedure, bringing it to a halt in a safe state. | `AuditLog.halt(reason)` in `governance/hitl_example.py`; test `tests/test_hitl_example.py::test_halt_stops_chain_mid_stream` proves no further entries can be appended after a halt and the halted chain still verifies | `halt()` is the stop-button analog: it closes the chain mid-stream with a final, immutable `halt` record stating the reason; any attempt to continue raises `AuditLogHalted`. The halted state is "safe" in the sense that the audit trail remains complete and verifiable up to the stop point. |

Supporting Article 14(1)–(3) context: the oversight measures above are
*built into* the artifact by design (provider-side measures under
Art. 14(3)(a)); the confidence threshold is a deployer-tunable
parameter (Art. 14(3)(b)-style measure identified for the deployer to
implement).

## Limitations (read before relying on this mapping)

1. **This is a mock rig.** All platform behavior (Bedrock, AgentCore,
   Agentforce, Omni-Channel) is locally mocked
   (`src/agentorch/clients/`). No real high-risk AI system, no real
   model, and no real human reviewer is involved; the "human" is a
   deterministic stub (`default_human_stub`). The mapping demonstrates
   *structural feasibility* of the oversight measures, not compliance
   of any deployed system.
2. **Illustrative, not legal advice.** This mapping is an engineering
   illustration of how the catalog's P6 pattern can host Article 14
   measures. It is not a legal conformity assessment, does not
   substitute for one, and has not been reviewed by counsel.
   [HUMAN: verify the clause paraphrases against the final text of
   Regulation (EU) 2024/1689, Article 14, and confirm the August 2,
   2026 applicability statement carried over from the manuscript.]
3. **Oversight has a measured latency price.** In the recalibrated
   study P6's end-to-end latency is dominated by the configurable
   human decision delay (p50 ~30 s; `latency.shared.human_decision_delay`)
   and is the highest of all patterns — the cost of the oversight point
   is quantified rather than hidden, and `human_queue` faults defer
   decisions (never auto-approve), asserted in
   `tests/test_paper_agreement.py`.
4. **Confidence scores are synthetic.** The gate operates on supplied
   confidence values; in a real system, calibration of those scores is
   itself a validity question that this rig does not address.
5. **Annex III classification is out of scope.** Whether a concrete
   deployment is "high-risk" is a deployment-specific legal question.
   [HUMAN: verify before any compliance claim is made in the
   manuscript.]
