# PHASE3_SPEC.md — Fit-Matrix Reconciliation (binding)

Completion promise: `PAPER_FIT_MATRIX_RECONCILED`. Branch: `phase3-fitmatrix` (off phase2-calibration). All prior HUMAN gates stay. Platforms mocked; no cloud; no publish/DOI/visibility change; no real URL/DOI; no fabricated numbers; NO reverse-engineering the fit rule to force agreement with the paper; never self-approve HUMAN tasks.

Context: Phase 2's table4.csv is a per-platform four-dimensional quality rollup ("overall") that contradicts the paper's Table 4, which is a single platform-independent fit-for-purpose grade in {Weak, Moderate, Strong} per (pattern, scenario). The agreement suite only checks sub-dimension claims, so it cannot catch the contradiction. Fix per the tasks below.

## Paper Table 4 (published cells; platform-independent)
| Pattern | S1 | S2 | S3 |
|---|---|---|---|
| P1 | Moderate | Strong | Moderate |
| P2 | Weak | Strong | Weak |
| P3 | Moderate | Moderate | Strong |
| P4 | Weak | Strong | Moderate |
| P5 | Strong | Moderate | Strong |
| P6 | Weak | Moderate | Strong |
| P7 | Strong | Moderate | Strong |

## Tasks (prd 201–207)
- **201 (AUTO) Pre-registered fit rule + fit matrix.** `study/make_fit_matrix.py` -> `figures/fit_matrix.csv`: ONE platform-independent grade per (pattern, scenario) in {Weak, Moderate, Strong}. Rule documented FIRST in `docs/FIT_RULE.md` (pre-registered: write the rule, then compute; never adjust the rule to flip specific cells — any rule change after first computation must be recorded in FIT_RULE.md §Changelog with reason). Rule shape:
  - Stressed property per scenario: S1 = throughput + per-request cost efficiency; S2 = multi-step coordination (latency/cost over stages + adaptive-vs-fixed decomposition capability); S3 = burst tolerance (p99 inflation S3 vs S1) AND capability for selective human routing / event absorption.
  - Pool both platforms (platform-independent): e.g., combine per-platform measurements or require agreement; document the pooling choice.
  - Strong = top Holm-significant equivalence group on the stressed property, or workload-required capability present (capability gate from pattern metadata); Weak = dominated on the stressed property or required capability absent; Moderate = otherwise. Document tie-breaking and how the capability gate composes with the measured standing.
- **202 (AUTO) Compare to paper; record discrepancies honestly.** Compare computed grades to the 21 paper cells. Agreement -> assert in suite (203). Disagreement -> do NOT force; record in `docs/FIT_DISCREPANCIES.md`: cell, paper grade, computed grade, measured rationale (numbers + stats), and whether it reads as a calibration issue vs a legitimate evidence-based refinement; flag [HUMAN]. Append "TASK 202: N fit-cell discrepancies flagged, awaiting human review" to progress.txt if N>0.
- **203 (AUTO) Extend agreement suite.** tests/test_paper_agreement.py: keep the existing 13 assertions; add assertions over the paper's actual Table 4 cells for EVERY cell where the fit rule reproduces the paper (parameterized over the agreed cells; the agreed-cell list generated from the comparison, committed as a fixture file e.g. tests/fixtures/fit_agreed_cells.json so the gate is stable and explicit). The gate must fail if fit_matrix.csv later contradicts any agreed cell.
- **204 (AUTO) Supplementary table rename.** The four-dimensional per-platform grade table becomes `figures/table4_supplementary.csv` (make_table4.py renamed/redirected accordingly, run.sh + RESULTS_TO_PAPER_MAP + verify_repro manifest updated); docs/GRADES.md labels it a richer per-platform quality view (latency/reliability/cost/oversight) and its docstring states it is NOT the paper's fit-for-purpose matrix.
- **205 (AUTO) Cosmetic + honesty fixes.** (a) cost figure y-axis: exactly one unit — "USD per 1k requests (configs/costs.yaml assumptions, dated)" — no mixing of "cost units"/"USD"; (b) fault-matrix figure caption/title note + results draft one-liner: model_backend is a shared dependency on every pattern's critical path, so a hard model_backend fault propagates across most patterns; fault-isolation DIFFERENTIATION is carried by orchestration-specific components (event_bus, gateway/tool, memory_store, human_queue, bridge); (c) cost results note: one-line sensitivity caveat that the Agentforce-vs-Bedrock gap is dominated by the $2/conversation assumption [HUMAN: confirm].
- **206 (HUMAN) Manuscript update.** docs/manuscript/results_section.md references figures/fit_matrix.csv as Table 4 and table4_supplementary.csv as supplementary; re-trace changed numbers; commit as awaiting review.
- **207 (HUMAN) Re-flag.** Fit-cell discrepancies (202) + the cost sensitivity caveat flagged for author review in progress.txt and docs/HUMAN_REVIEW_QUEUE.md (append a Phase-3 batch section).
- **208 (AUTO) Regenerate + final gate.** bash run.sh regenerates all outputs incl. fit_matrix.csv, table4_supplementary.csv, corrected cost figure; fresh-clone verification; agreement suite (incl. fit cells) green; pytest --cov green; fit_matrix.csv reproduces the paper on every non-flagged cell; only HUMAN items remain. Append PAPER_FIT_MATRIX_RECONCILED to progress.txt.

## DONE
Agreement suite (incl. Table-4 fit cells) green AND pytest --cov green AND run.sh green AND fit_matrix.csv reproduces paper's Table 4 on every non-flagged cell AND only HUMAN items remain. Report matched vs flagged cells with measured rationale per flag.
