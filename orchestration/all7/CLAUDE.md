# CLAUDE.md — Persistent rules for this autonomous build

Completion promise: PROJECT_COMPLETE

> This file is NOT at the repo root, deliberately. This repository is a
> published artifact with a Zenodo DOI, and its scaffolding files were removed
> before v1.1.1. Do not move or copy this file to the root. The launch prompt
> must point at `orchestration/all7/CLAUDE.md` and `orchestration/all7/prd.json` explicitly.

## Stack & conventions
- Stack: Python 3.12; `agentorch` imported from `src/` via `PYTHONPATH`; boto3;
  `bedrock-agentcore` runtime SDK; Docker buildx `linux/arm64`; pytest.
- Follow existing patterns: live clients in `anchor/agentcore/`, tests in
  `tests/`, deployment in the style of `anchor/agentcore/deploy_released.py`,
  no-fabrication guards in the style of `anchor/p7/analyze_p7.py`.
- Verify command: `python -m pytest -q`
- Offline tests must run with **no AWS credentials**. If a test starts needing
  them, that is a defect in the test, not a reason to require credentials.

## How to work (every iteration)
1. Read this file and `orchestration/all7/prd.json`. Pick the lowest-numbered task whose
   `passes` is false and whose dependencies all pass.
2. AUTO task: implement following existing patterns. Make a **GENERAL,
   root-cause fix — never the minimum hack to pass one test.** No new
   dependencies unless the task says so. Do not touch `WorkItem`, `WorkResult`
   or `CallContext`.
3. HUMAN task: implement it, but do **NOT** mark passing and do **NOT** commit.
   Append to `orchestration/all7/progress.txt`: "TASK <id> implemented, awaiting human
   review". Move to the next eligible AUTO task.
4. Run the task's done-check exactly as written. On pass: set `passes: true` in
   `prd.json`, commit, note it in `progress.txt`. On fail: fix the cause and
   re-run; after 5 attempts, log the blocker and move on.
5. Re-read `progress.txt` before each task to avoid repeating a mistake.
6. Emit PROJECT_COMPLETE only when every AUTO task passes AND
   `python -m pytest -q` is green AND only HUMAN tasks remain.

## Rules specific to this repository

- **`agentorch` is not to be edited.** The entire claim under test is that the
  *released* modules run unmodified behind a swapped client. Editing a pattern,
  subclassing it, or monkey-patching it destroys the result you are producing.
  If a pattern will not run through a live client, that is a finding to report,
  not a defect to patch around.
- **Live clients must never call `ctx.boundary_call(...)`.** That drives the
  virtual clock and fault injection for the deterministic study. A live client
  invoking it contaminates the emulated timing model.
- **Never overwrite a committed record.** Everything under `anchor/results/` and
  `anchor/p7/results/` is evidence cited by a manuscript. New runs write new
  filenames. `released_P1.jsonl` and `released_P2.jsonl` in particular are
  already cited.
- **Redaction is absolute.** Record ids, counters, timestamps and status. Never
  model completion text, never event payload content.
- **Smoke-test every live method standalone before wiring it into a pattern.**
  This is not ceremony: a counter bug in the P7 retry probe was caught exactly
  this way, and it would have silently understated the result.
- **A rebuilt image gets a new tag.** Updating a runtime while reusing a tag can
  leave it serving the cached image, and the run then measures the old code.

## Forbidden autonomous actions (never do these without a human)
- Creating, modifying or deleting **any AWS resource** — these cost money and
  deletion is irreversible
- Changing **IAM** roles, policies or any access control
- Overwriting or deleting any committed record under `anchor/results/` or
  `anchor/p7/results/`
- Editing `paper/`, the manuscript, the response letter, or any upload artifact
- Publishing a git tag, GitHub release, or Zenodo DOI
- Submitting anything to the IEEE portal
- Committing secrets, keys or tokens (the AWS access-key ID counts)
- Recording model completion text in any result file
- Merging any HUMAN-REVIEW-REQUIRED task

## Human-review domains (always HUMAN-gated here)
The generic categories map onto this project as follows, and the mapping is the
reason each gate exists:

| Generic category | Here |
|---|---|
| Money | Cloud spend: provisioning, deployment, recorded runs |
| Permissions | IAM role and policy changes |
| Irreversible | Deleting resources; overwriting cited records |
| Advice a reader acts on | **Manuscript claims.** A reviewer acts on what the paper asserts, and no passing test can establish that a claim is proportionate to its evidence |

## Grounding
- Human work idioms do not apply: no "break", no "end of workday". Keep going.
- "I believe it's done" is not done. "Every done-check passes" is done.
- If a done-check cannot be made to pass honestly, say so and stop. A green
  suite obtained by weakening an assertion is worse than a red one.
