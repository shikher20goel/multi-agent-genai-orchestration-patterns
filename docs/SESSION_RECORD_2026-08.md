# Session record — 23 to 28 August 2026

Everything done in one working session, so a later reader (or a later
session) can pick this up without reconstructing it from commit messages.
Two bodies of work ran here: strengthening the IEEE Access resubmission, and
then deploying all seven catalog patterns live on AWS.

Repo state at close: `main` at v1.3.0, 280 tests passing, study reproduces
bit-for-bit under `environment/requirements.lock`. Nothing submitted to IEEE.

---

## Part A — Access-2026-28862 resubmission (v3 → v4)

Goal: push three reviewer comments scoring 90% to ≥95%.

### What was measured live

**Managed-runtime anchor (R1.1).** The v3 anchor timed a *model call*, not a
managed *agent runtime*, and the letter had to concede an AgentCore anchor as
follow-up work. P1 and P2 were deployed as agents on Bedrock AgentCore
Runtime and the S1 set reissued at n=100 per pattern.

| Arm | P1 | P2 | ratio | ok |
|---|---|---|---|---|
| AgentCore, c=1 | 2.03 s | 1.06 s | 1.91× | 100/100 |
| — in-runtime component | 1.54 s | 0.59 s | — | — |
| AgentCore, c=8 | 6.87 s | 3.60 s | 1.91× | 89/100 |
| Direct Converse, us-east-1 | 1.65 s | 0.58 s | 2.86× | 100/100 |
| Direct Converse, us-east-2 (1 Aug, n=30) | 1.56 s | 0.57 s | 2.8× | 30/30 |

The same-region control was added unprompted: without it, any
AgentCore-vs-direct difference would be confounded with the us-east-2 →
us-east-1 move. It reports 2.86× against 2.8×, so region is not the
explanation.

What separates the two paths is a **near-constant additive overhead** —
0.50 s for P1, 0.47 s for P2, essentially pattern-independent — and being
additive on P2's smaller baseline is what compresses 2.86× to 1.91×. The
overhead is reported, never subtracted out.

The 11 failures at c=8 are all `ThrottlingException` and all on P1; P2 had
none. That is the invocation-count difference appearing as *capacity* rather
than latency. The c=8 P1 median therefore covers 89 completions and is
labelled survivor-biased.

**P7 retry direction (R1.Q2).** v3 conceded that AgentCore-managed retry was
"a distinct, unexercised retry surface". Conditions C3/C4 exercise it.

| Run | Agent ingress | Logical calls | Wire attempts | Retried | Entries>1 | Dup executions |
|---|---|---|---|---|---|---|
| C3 | off | 30 | 60 | 30 | 30 | **30** |
| C4 | on | 30 | 60 | 30 | 30 | **0** |

Attribution is measured, not assumed: no crash injected, and both runs record
30 published / 30 delivered / 0 redeliveries, so the CRM direction
contributed nothing. CloudWatch reproduces both counts independently of the
harness. The bridge's own ingress was ON in both runs and suppressed nothing
— the duplicate is created below it, which is why the ingress must sit at the
target boundary.

**Released modules on a real platform (R2.2).** The first pass deployed
*rebuilt counterparts* of P1/P2, which only shows that code *matching* the
released implementation runs. So the released `agentorch` modules themselves
were packaged and run: 60/60 requests, exactly 5 and 1 invocations, no
variation. The container puts the repo's own `src/` on `PYTHONPATH` rather
than installing a resolved distribution, and each response names the module
and class that executed.

### Audit outcome

| Comment | v3 | v4 |
|---|---|---|
| R1.1 emulated, not live/under load | 90 | **96** |
| R1.Q2 AgentCore↔CRM conflicts | 90 | **96** |
| R2.2 instantiations unverified | 90 | **96** |
| R1.Q1 mock→live effort | 95 | 98 |
| R2.4 design parameters | 95 | 97 |
| others | 97 | 97–98 |

**11 of 11 at ≥95%.**

### Deliverables

`paper/v4_upload/` — manuscript PDF (20 pp), LaTeX zip, highlighted PDF (335
annotations), Author Response `.docx`. All four in Drive **Version 2.2**,
byte-verified. **Deliberately not in git** (see "Decisions" below).

---

## Part B — all seven patterns live on AWS

Planned with the `autonomous-build-orchestrator` skill in REPO mode: 70
atomic tasks, 9 milestones, 57 AUTO / 13 HUMAN-gated. Artefacts in
`orchestration/all7/`. 66/70 complete; the 4 remaining are M8 paper
decisions, held by choice.

### Result

All seven released modules on Bedrock AgentCore Runtime, n=30 each,
**210/210 successful**, every structural signature matching the fixture
frozen from the offline run.

| Pattern | | invocations | service calls | guardrail |
|---|---|---|---|---|
| P1 Supervisor | 30/30 | 5 | 0 | 0 |
| P2 Pipeline | 30/30 | 1 | 0 | 0 |
| P3 Choreography | 30/30 | 3 | 3 | 0 |
| P4 Blackboard | 30/30 | 3 | 8 | 0 |
| P5 Gateway | 30/30 | 1 | 6 | 0 |
| P6 HITL | 30/30 | 1 | 0 or 1 | 1 |
| P7 Bridge | 30/30 | 1 | 0 | 0 |

Live seams: Bedrock model runtime, AgentCore Memory, AgentCore Gateway (MCP
over SigV4 to a Lambda target), Bedrock Guardrails, CloudWatch Logs.

The whole substitution is `attach_live_clients(pattern, ...)` — at most three
attribute assignments. Nothing in `agentorch` is edited, subclassed or
monkey-patched, which is the point: it makes §V-A's "single call-context
seam" claim a demonstration rather than an assertion.

### Bounds (full list in `docs/ALL7_LIVE_BOUNDS.md`)

- **One platform.** Nothing deployed to Agentforce.
- **P6's human step is modelled, not staffed.** 7 of 30 items paused — the
  confidence gate firing, not a person deciding.
- **P5's hop is real; its tools are stand-ins.** Real gateway, real Lambda,
  real MCP call per tool, but the tools are echo functions.
- **Not a timing arm.** The released fan-out helper is sequential under a
  virtual clock, so wall-clock is not comparable to the anchor.
- S1 only; live runs stay outside the deterministic study.

---

## Bugs and findings caught

Every one of these was found by running something, not by reading it.

1. **Reproduction depends on the pinned lock.** Under current PyPI defaults
   the study still runs and `verify_repro.py` still exits 0, but
   `table3.csv` drifts by 1–2 ULPs in bootstrap CI bounds. `verify_repro.py`
   only checks that outputs *exist*; the real gate is `git status figures/`.
2. **A counter that understated duplicates.** The P7 retry agent counted an
   execution on *completion*. The reissued call takes the warm path and
   finishes *before* the cold call it duplicated, so the counter read 1 where
   the work had run twice — an error that could only ever understate the
   result. Caught by a single-task smoke test before the recorded run.
3. **A false claim in the manuscript.** §V-A said "nothing in the released
   package has been deployed to either vendor's control plane". That became
   false the moment `anchor/agentcore/agent/` shipped and ran. Corrected, and
   the correction recorded in the letter rather than quietly dropped.
4. **`pdftotext -layout` interleaves two-column text.** Four claims read as
   *missing* from the manuscript that were present. Any audit using `-layout`
   produces false negatives.
5. **P6 was silently doing nothing.** It never paused across 30 hand-built
   items, so its human path and memory seam went unexercised while the test
   passed. `_confidence()` defaults to 0.9 when the payload lacks a
   `confidence` field; the *scenario generators* supply it. Fixed by using
   the repo's own `generate_s1`. Had the live run not been fixed the same
   way, P6 would have reported 30/30 and proved nothing.
6. **An image that could not import its own clients.** All seven runtimes
   failed with `RuntimeClientError` and *no log output*. The Dockerfile
   copied only `src/`, `configs/` and `agent_app.py` — sufficient while the
   live client was inline, insufficient once M1 moved it. Silence in
   CloudWatch was the diagnostic: a container that dies during import never
   reaches its own logging.
7. **A dry-run that lied.** `provision_all7.py --dry-run` printed "+1
   stand-in target" and `ensure_gateway` never created one.
8. **`requests` missing from the container.** The MCP gateway client needs
   it; P5 failed 30/30 while the other six passed.
9. **Guessed tool names.** The gateway target exposed `search`/`lookup`;
   P5 reads `search, calculator, crm_lookup` from `configs/default.yaml`. The
   seam refused rather than substituting a different tool — working as
   intended — and the target now reads the same config the pattern does.

---

## Decisions taken, and why

- **Paper files are not in git.** The repo is a public artifact with a Zenodo
  DOI; the manuscript is unsubmitted. Three sources (`main-v4.tex`, the
  letter, the audit) had been force-added earlier in the session and were
  pushed briefly; they were purged from branch history with `git-filter-repo`
  and force-pushed. `main` never held them. The objects may persist as
  unreferenced blobs on GitHub until garbage collection.
- **State files live in `orchestration/all7/`, not the repo root.** The
  orchestrator skill specifies the root, but this repo's scaffolding was
  deliberately removed before v1.1.1. Consequence: a launch prompt must point
  at `orchestration/all7/CLAUDE.md` explicitly, since Claude Code will not
  auto-load a non-root one.
- **`prd.json` is generated from `BACKLOG.md`.** Transcribing 70 tasks twice
  is a drift machine, and the agent executes the JSON while a human reads the
  Markdown. `gen_prd.py` enforces the skill's invariants and refuses to write
  on violation — it caught 140 on first run.
- **M8 (paper integration) is HELD, not abandoned.** Tasks 080–083 remain
  `passes=false` because they were not performed. R2.2 already clears the bar
  at 96%; folding the seven-pattern result in would spend part of the single
  permitted resubmission improving a sufficient answer.
- **AWS resources retained, not retired** (TASK 079), for reproducibility.

---

## Current state

**Paper.** v4 complete and unsubmitted. 11/11 ≥95%. 20 pp (at the gate; page
20 is the required author biography, not prose spill). Files in Drive
Version 2.2, byte-verified. **Nothing submitted anywhere.**

**Repo.** `main` at **v1.3.0**, released on GitHub, Zenodo mints a version
DOI under the concept DOI the paper cites (no manuscript change needed).
280 tests. Study reproduces bit-for-bit under the pinned lock.

**AWS (billing, ~$0.20–0.50/month).**

| Resource | Id |
|---|---|
| Memory | `agentorch_all7_mem-EeJ36664JO` |
| Gateway + target | `agentorch-all7-gw-iambvbawex` / `CMD4LD9EZG` |
| Lambda | `agentorch-all7-tool` |
| Guardrail | `0rwf5fcew9ss` |
| Runtimes (11) | `anchorp1`, `anchorp2`, `anchorp{1..7}rel`, `p7probe`, `p7retry` |

`anchorp1`/`anchorp2` are superseded by the `rel` versions and are the
obvious candidates to retire first.

**Salesforce.** `Anchor API Client CC` now holds `api`, `chatbot_api`,
`sfap_api`. The Agentforce load arm (c ∈ {1,4}) is unblocked but **was never
run** — §VI-G states plainly that Agentforce remains sequential at n=30.

---

## Open items

1. **Submit, or fold in the seven-pattern result first.** Recommendation:
   submit v4 as it stands.
2. **Agentforce load arm** — now unblocked; would close R1.1's remaining
   residual ("under load" is evidenced on one platform only).
3. **Retire redundant runtimes** — irreversible, so not done unprompted.
4. **Post-submission security cleanup** — AWS access key, ECA consumer
   secret, stale branches. Correctly deferred until after submission.

## How to verify any of this

```bash
python -m pytest -q                                    # 280
PYTHON=<pinned-venv>/bin/python bash run.sh            # then: git status figures/  -> clean
python anchor/agentcore/analyze_all7.py --summary anchor/results/all7final_summary.json
python anchor/p7/analyze_p7.py anchor/p7/results       # C1-C4
python scripts/verify_manuscript_numbers.py paper/v3/main.tex
python scripts/check_redaction.py anchor/results/ anchor/p7/results/
```

Each analyser refuses rather than reporting: `analyze_all7.py` on a partial
run, a signature mismatch, an undeclared stubbed seam or mixed image digests;
`analyze_p7.py` on a truncated run or one where CRM redelivery makes
attribution ambiguous; `verify_manuscript_numbers.py` on any value that has
drifted from its artifact.
