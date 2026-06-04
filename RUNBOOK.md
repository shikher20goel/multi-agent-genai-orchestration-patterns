# RUNBOOK.md — Claude Code Autonomy Runbook (this project)

Operational guide that turns the backlog into a project Claude Code builds with minimal babysitting. **[YOU]** = the human; **[CC]** = goes to Claude Code (in `CLAUDE.md` or the launch prompt). The three autonomy levers: remove permission stops, give an objective finish line (`PAPER_ARTIFACT_COMPLETE`), give a verification loop (`pytest` + `run.sh`).

---

## [YOU] One-time setup
1. **Install Claude Code** and confirm it runs in the repo: `npm install -g @anthropic-ai/claude-code`, then `cd <repo>`, then `claude`. Check your plan's usage limits — long autonomous runs consume a lot.
2. **Throwaway branch:** `git checkout -b autonomous-build`. Never run on `main`. This is your blast radius.
3. **Drop in state files** at repo root: `plan.md`, `prd.json`, `progress.txt`, `CLAUDE.md` (and this `RUNBOOK.md`).
4. **Confirm the verify command works:** run `pytest -q` by hand. Task 002 establishes the trivial passing test; the loop is blind without it.
5. **Sandbox posture:** run on the throwaway branch with frequent commits so every step is revertible (or run in a container). Pick one.
6. **Install the autonomy mechanism** (below) — the official Ralph-loop plugin for most cases.
7. **Watch the first 10–15 minutes** of run one: confirm it reads `plan.md`, picks tasks in order, runs `pytest`, and is not inventing structure. Cancel if behavior looks wrong.

## [YOU] Choose your autonomy mechanism
- **Tier 1 (simplest):** `claude --dangerously-skip-permissions` pointed at this rich spec. Good for an hour-plus. Sandbox/branch only.
- **Tier 2 (recommended):** the **Ralph-loop / Stop-hook** plugin (`ralph-loop`/`ralph-wiggum`). A Stop hook fires when the agent tries to end its turn; if the completion promise + verification aren't satisfied it feeds the task prompt back. Always set `--max-iterations` and a `--completion-promise`.
- **Tier 3 (hands-off cadence):** Claude Code **cloud routines** for scheduled, laptop-independent runs (e.g., nightly build-and-test). Verify current feature names/limits in the docs.

## [CC] The loop instruction (paste into the launch prompt)
```
Read CLAUDE.md and prd.json. Then loop:
1. From prd.json, pick the single lowest-numbered task whose "passes" is false
   and whose dependencies are all "passes": true.
2. If that task's gate is "HUMAN": implement it, but do NOT mark it passing and do
   NOT commit it as final. Append to progress.txt: "TASK <id> implemented, awaiting
   human review" and SKIP to the next eligible AUTO task.
3. If the task's gate is "AUTO": implement it following existing patterns. Make a
   general, root-cause fix — never the minimum hack to pass the test. Do not add
   dependencies unless the task says to. Do not touch the data model unless told to.
4. Run the task's done-check command exactly as written.
   - PASS: set "passes": true, commit with a clear message, append one line to progress.txt.
   - FAIL: read the error, fix the cause, re-run. Up to 5 tries; if still failing,
     log the blocker to progress.txt, set the task aside, move to the next eligible task.
5. Before each new task, re-read progress.txt.
6. Output "PAPER_ARTIFACT_COMPLETE" ONLY when every AUTO task has "passes": true AND
   `pytest --cov` passes AND `bash run.sh` regenerates all figures AND the only
   remaining tasks are HUMAN-gated. Otherwise keep working — do not stop, do not ask
   questions, make reasonable assumptions and note them in progress.txt.
```

## [CC] Grounding rules that prevent premature stopping
```
- No human work idioms: no "break", no "end of day", no "rest". Don't suggest stopping.
- Don't estimate effort in human hours; keep executing tasks.
- If you think you're finished, re-verify against prd.json + the test suite + run.sh
  before emitting the completion promise. "I believe it's done" is not done.
```

## Safety & guardrails (read twice) — research-integrity edition
1. **The numbers and the regulatory/governance claims are HUMAN gates, always.** Any value that lands in Tables 3/4 or a figure, any statistical method, and the EU AI Act / NIST / ISO mappings — the loop may *write* them, but the author must *review* before they go in the paper. "Tests pass" does not mean "the statistic is correct or the compliance claim is accurate."
2. **Never let the agent do irreversible / boundary-crossing things autonomously:** no real cloud API calls, no GitHub/Code Ocean/Zenodo publish, no DOI mint, no real URL/DOI in the manuscript, no fabricated numbers, no license finalization, no committing secrets.
3. **Always set `--max-iterations` and a usage ceiling.** ~40 is a reasonable start; the backlog is ~63 tasks but AUTO tasks dominate.
4. **Always run on a throwaway branch or sandbox.** `--dangerously-skip-permissions` lets the agent run any command.
5. **Watch the first run; review the diff afterward** before merging to `main` — long runs occasionally over-engineer.

## [YOU] Monitoring & running it
- Kick off on desktop/terminal; watch 10–15 min; then monitor from the Claude mobile app.
- Check `progress.txt` and `git log` periodically for what landed and what's blocked.
- On `PAPER_ARTIFACT_COMPLETE`: run `pytest --cov` and `bash run.sh` yourself, read the diff, and hand-review every HUMAN-gated task (the numbers, the stats, the governance mappings, the manuscript drafts) before merging.

## Troubleshooting
| Symptom | Cause | Fix |
|---|---|---|
| Stops/asks constantly | Permission prompts on, or task too vague | Skip-permissions in sandbox; tasks here already carry explicit done-checks |
| Quits early "done" | Promise string alone | Gate on `pytest` + `run.sh` too |
| Loops forever / burns usage | No `--max-iterations` or weak done-checks | Set the cap; done-checks here are runnable |
| Quality degrades late | Context bloated | Lean on `progress.txt`/`prd.json`; restart session — it resumes from state files |
| Minimal hacks | Missing generic-fix rule | It's in `CLAUDE.md`; reinforce on logic tasks |

## One-page quick start
1. `git checkout -b autonomous-build`
2. Copy `plan.md`, `prd.json`, `progress.txt`, `CLAUDE.md`, `RUNBOOK.md` into the repo.
3. `pytest -q` by hand (after task 002 exists) to confirm the harness.
4. Install the Ralph-loop plugin.
5. `claude --dangerously-skip-permissions` (sandbox/branch).
6. `/ralph-loop "Work the backlog in prd.json per CLAUDE.md" --max-iterations 40 --completion-promise "PAPER_ARTIFACT_COMPLETE"`
7. Watch 10–15 min; then let it run, monitor from mobile.
8. On `PAPER_ARTIFACT_COMPLETE`: run full tests + `run.sh`, review the diff, hand-review every HUMAN task, then merge.
