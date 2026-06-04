# Draft manuscript section: governance (rewrite) (Task 060, HUMAN-gated)

> Rewrite of the manuscript's governance discussion (currently
> embedded in Section IV.G, P6 Human-in-the-Loop Adjudication, citing
> EU AI Act Article 14 [42], NIST AI RMF [43], [44], and ISO/IEC 42001
> [62]). Grounded in the three mapping documents
> (docs/governance/eu_ai_act_article14.md, docs/governance/nist_ai_rmf.md,
> docs/governance/iso42001.md) and the runnable HITL example
> (governance/hitl_example.py). IEEE voice. [HUMAN: verify all
> regulatory paraphrases and approve before insertion; none of this is
> legal advice.]

---

## Section: Governance Alignment of the Catalog

The catalog's governance claim in Section IV.G — that the
Human-in-the-Loop Adjudication pattern (P6) is the structural means of
satisfying human-oversight obligations — is made concrete in the
released artifact in three steps: a runnable oversight mechanism,
three framework mappings with evidence paths, and an executed
measurement of the oversight pattern's cost.

### A. A Runnable Oversight Mechanism

The artifact ships a self-contained, tested oversight demo
(`governance/hitl_example.py`; tests in `tests/test_hitl_example.py`)
that composes the four mechanisms regulators ask for. A *confidence
gate* routes any agent draft below a configurable threshold to a human
queue rather than presenting it as a finished decision. A *human stub*
records an approve/reject decision attributable to a named reviewer.
Every event — draft production (with a content hash), routing, the
human decision — is appended to a *hash-chained, append-only audit
log* whose entries are immutable and whose integrity is checkable
(`verify_chain()`); tampering with any committed entry is detected.
Finally, *halt()* implements the stop-button semantics: it closes the
chain mid-stream with a final, immutable record of the reason, after
which no further entries can be appended, and the halted chain still
verifies. The same mechanisms appear inside the measured P6 pattern
(`src/agentorch/patterns/p6_hitl.py`: pause/resume with a logged
reviewer decision), so the governance demo and the measured pattern
share one design.

### B. Framework Mappings with Evidence Paths

Three mapping documents in the artifact connect frameworks to code and
to executed rig outputs, clause by clause.

**EU AI Act Article 14** (docs/governance/eu_ai_act_article14.md). All
five oversight-measure clauses of Article 14(4) are addressed:
(a) understanding and monitoring maps to the executed study's
capability evidence (figures/table3.csv, figures/fault_matrix.png) and
per-call observability; (b) automation-bias awareness maps to the
confidence gate, which surfaces the system's own uncertainty;
(c) output interpretability maps to the nine-element pattern metadata
and logged confidence-versus-threshold context; (d) the ability to
disregard or override maps to the human reject path, itself audited;
and (e) the stop button maps to `halt()` with its tested
cannot-append-after-halt semantics. The mapping document states, and
the manuscript should repeat, that the rig is a mock and the mapping
is an engineering illustration, not a legal conformity assessment.

**NIST AI RMF 1.0 and the Generative AI Profile (AI 600-1)**
(docs/governance/nist_ai_rmf.md). The mapping covers all four
functions. GOVERN maps to the artifact's accountability policy
(machine-generated claims cannot self-approve) and the tamper-evident
audit chain. MAP maps to the machine-checked pattern metadata and the
enumerated 336-cell fault grid. MEASURE rows point at concrete rig
outputs — figures/table3.csv (percentiles with BCa CIs),
figures/fault_matrix.png (executed failure-mode evaluation),
results/manifest.json (provenance) — under the pre-committed
statistical plan. MANAGE maps to halt(), the gateway bulkheads (P5),
and the bridge's fault-domain containment (P7), each of which is
tested, plus the incident-shaped scenario S3.

**ISO/IEC 42001:2023** (docs/governance/iso42001.md). Clauses 4–10 and
the most relevant Annex A control areas (A.2–A.10) are mapped, with
each entry marked as *implemented* by the artifact (e.g., clause 8
operational control via the deterministic single-command reproduction;
clause 9 performance evaluation via the executed tables and the
verifiable audit chain) or merely *documented*. The mapping also
states the standard's **agentic-AI gap**: ISO/IEC 42001 does not
address inter-agent compositional risk, oversight *placement* within
an agent chain, or cross-platform agent federation — precisely the
concerns the catalog's fault matrix, P6 placement guidance, and P7
bridge address. The catalog can therefore be read as a technical
complement that gives an AI management system the structural
vocabulary it currently lacks for agentic systems.

### C. The Measured Cost of Oversight

Because the study is executed, the oversight pattern's machine-side
overhead is a measured quantity rather than a directional claim: P6's
no-human-think-time floor is p50 533.5 ms / p99 1747.2 ms on the
mocked Bedrock instantiation under S1 (trace: figures/table3.csv row
P6,bedrock,S1 cols p50_ms, p99_ms) and p50 750.2 ms / p99 2398.6 ms on
mocked Agentforce (trace: figures/table3.csv row P6,agentforce,S1),
with per-request cost 0.006318 and 0.500001 cost units respectively
(trace: figures/cost_ledger.csv rows P6,bedrock and P6,agentforce col
mean_cost_units). The human's own latency dominates in deployment, as
Section IV.G argues; the measurement shows the pattern's machinery
adds little on top.

### D. Limitations

All three mappings are illustrative engineering mappings over a mock
rig: no real platform, model, or human reviewer is involved; clause
and control paraphrases await verification against the authoritative
texts ([HUMAN: verify], flagged inline in each mapping document); and
nothing in this section constitutes legal advice or a conformity
claim.
