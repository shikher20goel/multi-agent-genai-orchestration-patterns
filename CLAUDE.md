# CLAUDE.md — Persistent Project Rules

**Project:** AgentOrchPatterns-RepoPackage
**Completion promise:** `PAPER_ARTIFACT_COMPLETE`
**Purpose:** Build the runnable reproducibility package + executed measurement study that makes the IEEE Access paper *"A Pattern Catalog for Multi-Agent Generative AI Orchestration Across Enterprise CRM and Hyperscaler Cloud Platforms"* acceptable: convert its *prospective* rig into an *executed, open, reproducible* evaluation. Read this file every iteration.

## Stack & conventions
- **Python 3.11+.** Package `agentorch` under `src/`. Tests under `tests/`. Figures to `figures/`, raw results to `results/` (gitignored).
- Dependencies: numpy, scipy, statsmodels, pandas, matplotlib (Agg/headless), simpy, pyyaml, pytest, pytest-cov, ruff. **No cloud SDKs hitting real endpoints. No paid or network-calling deps.**
- Style: `ruff` clean. Type-hint public functions. One module per concern. All tunables live in `configs/*.yaml` — no scattered magic numbers.
- Determinism: everything seeded via `config.get_rng(seed)`. Same seed → identical output. Record `submit_ts` and `complete_ts` **separately** (open-loop / coordinated-omission correctness).

## Test / verify commands
- Primary: `pytest -q` (and `pytest --cov` for the final gate).
- Lint: `ruff check src tests`.
- Smoke study: `python -m agentorch.study.run_study --smoke`.
- Full reproduction: `bash run.sh` (must regenerate every figure from a clean state).
- Demo: `bash demo.sh`.
A task is done ONLY when its exact done-check command in `prd.json`/`plan.md` passes. "Looks done" is not done.

## The generic-fix rule
For any task touching logic (patterns, rig, statistics), make a **general, root-cause fix**, never the minimum hack to pass one test. Do not add dependencies unless the task says to. Do not change the data model unless the task says to.

## HUMAN-gated tasks (research-integrity gates)
A task with `gate: HUMAN` is the research-integrity analog of "money math." It covers anything that:
1. produces a **number or claim that goes into the manuscript** (Tables 3/4, latency/cost/fault figures, comparison table, results section),
2. is a **statistical-correctness decision** (BCa bootstrap, Mann–Whitney, Holm/Bonferroni, the statistical plan),
3. is a **governance/compliance claim** (EU AI Act Art. 14, NIST AI RMF/600-1, ISO 42001 mappings, rejected-candidate rationale),
4. **edits the manuscript** (results/abstract/governance/rebuttal drafts, placeholder fills),
5. **publishes externally or touches licensing** (GitHub/Code Ocean/Zenodo publish, DOI mint, LICENSE choice).

For a HUMAN task: **implement it, but do NOT mark `passes: true`, do NOT commit it as final, do NOT self-approve.** Append to `progress.txt`: `TASK <id> implemented, awaiting human review` and move to the next eligible AUTO task.

## Forbidden autonomous actions (never do these without the human)
- No real Bedrock/Agentforce/cloud API calls — platforms stay **mocked locally**.
- No publishing to GitHub/Code Ocean/Zenodo; no DOI minting; no changing repo permissions/secrets.
- No inserting a **real** GitHub URL or DOI into the manuscript — leave clearly-marked slots for the human.
- No **fabricated, invented, or rounded-beyond-the-data** numbers in any manuscript draft. Every number must trace to `results/`.
- No finalizing the LICENSE without human confirmation.
- No deleting data, no committing credentials, no editing access controls.

## Loop discipline
- Pick the single lowest-numbered task whose `passes` is false and whose dependencies are all `passes: true`.
- AUTO task: implement → run done-check → on PASS set `passes: true`, commit with a clear message, append one line to `progress.txt`; on FAIL fix the cause and retry up to 5 times, else log the blocker and move on.
- Re-read `progress.txt` before each task to avoid repeating mistakes.
- Human work idioms do not apply: no breaks, no "end of day," no hour estimates. Keep executing.
- Emit `PAPER_ARTIFACT_COMPLETE` ONLY when every AUTO task has `passes: true` AND `pytest --cov` passes AND `bash run.sh` regenerates all figures AND the only remaining tasks are HUMAN-gated (implemented + flagged). "I believe it's done" is not done; "every AUTO done-check passes" is done.
