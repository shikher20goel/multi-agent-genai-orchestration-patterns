# AI-Use Disclosure (Phase 2 task 107, HUMAN-gated)

> Draft disclosure statement for the manuscript ("Use of AI" /
> acknowledgment section, per the venue's placement rules). Wording is
> drafted to be consistent with IEEE's expectations for disclosing the
> use of AI-generated content in submissions: the use of AI in
> producing article content must be disclosed in the article, and the
> authors remain fully responsible for all content.
> [HUMAN: verify the current IEEE AI-disclosure wording and required
> placement in the IEEE Author Center / journal author guidelines
> before submission; no specific policy number is cited here because
> none has been verified.]

---

## Proposed disclosure statement

**Use of Artificial Intelligence.** Substantial portions of this work
were produced with the assistance of an AI pipeline — an agentic
coding system based on Anthropic's Claude models — operating under the
author's direction. Specifically, the AI pipeline: (i) generated the
reference implementations of the seven orchestration patterns and the
locally mocked platform clients; (ii) generated the evaluation rig
(open-loop load generator, fault-injection campaign, cost-capture
harness, and statistical pipeline); (iii) executed the measurement
study reported in Section [X] and produced the resulting figures and
tables from the recorded outputs; and (iv) drafted portions of the
manuscript text, including the results section. The author specified
the research design, the pattern catalog, the measurement methodology,
and the acceptance criteria; reviewed and verified all generated code,
executed results, figures, tables, and text; and takes full
responsibility for the integrity, validity, and originality of the
entire content of this article. All AI-generated artifacts are
released in the accompanying reproducibility package, where their
provenance (configuration, seeds, and generation history) is recorded.

---

## Accuracy notes for the human reviewer (not for the manuscript)

- The statement above is deliberately specific: the AI pipeline did
  not merely "assist with editing" — it generated the reference
  implementations, the rig, ran the study, produced figures/tables,
  and drafted manuscript sections. Understating this would be an
  inaccurate disclosure.
- The platforms remain locally mocked; no AI system accessed real
  Salesforce/AWS endpoints. The results are the rig's executed
  outputs, not fabricated numbers: every manuscript value traces to
  `results/` per `docs/RESULTS_TO_PAPER_MAP.md`.
- Human-gated review: all manuscript numbers, statistical decisions,
  and governance claims are flagged for the author's verification in
  `docs/HUMAN_REVIEW_QUEUE.md`; nothing was self-approved by the
  pipeline.
- [HUMAN: confirm the section placement (IEEE typically expects the
  disclosure in the acknowledgments or a dedicated section), confirm
  the model/system naming ("Claude-based agentic coding system"), and
  insert the section cross-reference at "[X]".]
