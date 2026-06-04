# Comparison vs. Similar Papers (Task 057, HUMAN-gated)

Comparison of this paper + artifact against the ten most similar works
**from the manuscript's own Related Work section (Section II)** and
its enterprise agentic-AI citations. Reference numbers `[n]` are the
manuscript's bibliography numbers; titles/authors/venues are extracted
from the submitted PDF's reference list. Every extracted citation is
marked [HUMAN: verify] — verify against the published version of each
work before the camera-ready cites this table.

Column definitions:

- **Artifact shipped?** — a public, runnable code/data artifact
  accompanies the paper.
- **Executed evaluation?** — the paper reports measurements from runs
  the authors executed (vs. conceptual/structural argument or survey).
- **Statistical rigor (CIs/tests)?** — reported results carry
  confidence intervals and/or hypothesis tests with multiple-
  comparison handling.
- **Cross-platform?** — the contribution is instantiated on two or
  more independent platforms (here: an enterprise CRM *and* a
  hyperscaler cloud).
- **Governance mapping?** — explicit mapping to governance/regulatory
  frameworks (EU AI Act, NIST AI RMF, ISO/IEC 42001).

| Work (manuscript ref) | Venue / year | Artifact shipped? | Executed evaluation? | Statistical rigor (CIs/tests)? | Cross-platform? | Governance mapping? |
|---|---|---|---|---|---|---|
| Wu et al., "AutoGen: Enabling next-gen LLM applications via multi-agent conversation" [5] [HUMAN: verify] | arXiv 2023 | Yes (open-source framework) | Yes (application case studies/benchmarks) | No (no CIs/corrected tests reported) | No (framework, not CRM+hyperscaler instantiations) | No |
| Hong et al., "MetaGPT: Meta programming for a multi-agent collaborative framework" [8] [HUMAN: verify] | ICLR 2024 | Yes (open-source) | Yes (code-generation benchmarks) | Partial (benchmark scores; no CI/correction regime) [HUMAN: verify] | No | No |
| Li et al., "CAMEL: Communicative agents for 'mind' exploration of LLM society" [9] [HUMAN: verify] | NeurIPS 2023 | Yes (open-source) | Yes (role-playing studies) | Partial [HUMAN: verify] | No | No |
| Park et al., "Generative agents: Interactive simulacra of human behavior" [14] [HUMAN: verify] | ACM UIST 2023 | Yes (released later) [HUMAN: verify] | Yes (simulation + human eval) | Partial (human-eval stats) [HUMAN: verify] | No | No |
| Hohpe & Woolf, *Enterprise Integration Patterns* [1] [HUMAN: verify] | Addison-Wesley 2003 (book) | No (catalog; vendor-neutral descriptions) | No (accepted on shared abstraction, per manuscript Sec. II.B) | No | Yes in spirit (platform-independent patterns), but pre-cloud/pre-CRM-agent | No |
| Acharya, Kuppan & Divya, "Agentic AI: Autonomous intelligence for complex goals — a comprehensive survey" [45] [HUMAN: verify] | IEEE Access 2025 | No (survey) | No | No | N/A (survey) | Partial (discusses governance themes) [HUMAN: verify] |
| Khamis, "Agentic AI systems: Architecture and evaluation using a frictionless parking scenario" [46] [HUMAN: verify] | IEEE Access 2025 | [HUMAN: verify] | Yes (single scenario) | [HUMAN: verify] | No (single architecture/scenario) | [HUMAN: verify] |
| Sarferaz, "Implementing agentic AI into ERP software" [47] [HUMAN: verify] | IEEE Access 2025 | No [HUMAN: verify] | [HUMAN: verify] | [HUMAN: verify] | No (single ERP platform) | [HUMAN: verify] |
| Toprani & Madisetti, "LLM agentic workflow for automated vulnerability detection and remediation in infrastructure-as-code" [52] [HUMAN: verify] | IEEE Access 2025 | [HUMAN: verify] | Yes (workflow evaluation) | [HUMAN: verify] | No (single workflow domain) | No [HUMAN: verify] |
| Liu et al., "AgentBench: Evaluating LLMs as agents" [60] [HUMAN: verify] | ICLR 2024 | Yes (benchmark suite) | Yes (LLM-as-agent benchmark) | Partial (benchmark scores) [HUMAN: verify] | No (benchmarks models, not orchestration topologies on enterprise platforms) | No |
| **This paper + artifact** (pattern catalog + executed open mock-rig study) | IEEE Access (submitted, 2026) | **Yes** — this repository: `run.sh` regenerates the full study; `environment/requirements.lock` + `Dockerfile`; `CITATION.cff`; capsule layout (`capsule/`) | **Yes** — 42 baseline conditions, n=500 each, + 336-cell fault campaign (`results/manifest.json`: seed 42, config-hashed) | **Yes** — 95% BCa bootstrap CIs, Mann–Whitney U with rank-biserial + Hodges–Lehmann, Holm correction over the 21-pair family (`docs/STATISTICAL_ANALYSIS_PLAN.md`, `figures/table3.csv`, `figures/table4_supplementary.csv`) | **Yes** — every pattern instantiated on mocked Agentforce 360 *and* mocked Bedrock/AgentCore (`src/agentorch/clients/`) | **Yes** — EU AI Act Art. 14, NIST AI RMF + AI 600-1, ISO/IEC 42001 mappings (`docs/governance/`) plus a runnable HITL example (`governance/hitl_example.py`) |

## Caveats

1. The differentiator columns for the ten compared works are filled
   from the manuscript's characterization of them (Section II) and the
   author's knowledge of the cited works; several cells could not be
   verified against full texts in this offline build and are
   explicitly marked [HUMAN: verify]. None of these cells may be
   quoted in the manuscript before verification.
2. "Cross-platform" is judged against this paper's specific axis
   (enterprise CRM + hyperscaler cloud); frameworks like AutoGen are
   model-agnostic but do not ship parallel CRM/hyperscaler pattern
   instantiations.
3. This paper's evaluation runs on **locally mocked** platforms; the
   executed-evaluation claim is about the open, deterministic
   measurement study, with mock fidelity discussed as a threat to
   validity (`docs/manuscript/results_section.md`).
