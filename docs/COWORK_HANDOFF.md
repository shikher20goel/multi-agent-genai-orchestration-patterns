# Cowork handoff — Access-2026-28862 and the all-seven live deployment

Paste the "Brief" section below into Claude Cowork. It is written for a
browser-driven agent: every task names an exact URL and exact values, and
everything that must NOT be done is stated rather than implied.

Full engineering detail is in `docs/SESSION_RECORD_2026-08.md`. This file is
only the part a browser agent can act on.

---

## BRIEF — paste from here down

You are picking up a research-artifact project. Work in Chrome. The owner
logs in; you drive.

### Situation

Two things were completed in a prior session by Claude Code:

1. **IEEE Access paper Access-2026-28862** — revision **v4** is finished and
   **NOT submitted**. An adversarial audit scores all 11 reviewer comments at
   ≥95% confidence. Four upload files sit in Google Drive folder
   **"Version 2.2"**, byte-verified.
2. **The public code artifact** — released as **v1.3.0**, with all seven
   orchestration patterns executed live on AWS (210/210 requests). Nothing
   about this is in the paper; that was a deliberate decision.

### Ground rules — do not violate these

- **Never click Submit on the IEEE Author Portal.** Not for any reason. The
  author has ONE permitted resubmission and will submit personally.
- **Never create or delete AWS resources, IAM policies, or roles** unless a
  task below says so explicitly.
- **Never create a GitHub release or tag.**
- **Never put the manuscript, response letter, or any paper file into
  GitHub.** The repo is public and the paper is unsubmitted. This has already
  been enforced once; do not undo it.
- If a task cannot be completed as written, say so and stop. Do not
  substitute a different action, and do not create placeholder files.

### Reference — where things are

| Thing | Location |
|---|---|
| Drive folder (upload set) | https://drive.google.com/drive/folders/1_Xz4TJmCzDRNMHtg8oyPTiKvuAbsIDUW |
| GitHub repo (public) | https://github.com/shikher20goel/multi-agent-genai-orchestration-patterns |
| Latest release | v1.3.0 |
| AWS account | 111789566955, region us-east-1 |
| IAM user | anchor-runner |
| Salesforce org | orgfarm-04d1f5d7a4-dev-ed |

The four portal files, with expected byte counts:

```
integration-patterns-v4.pdf                  1,851,743
integration-patterns-v4-latex.zip            4,061,056
integration-patterns-v4-HIGHLIGHTED.pdf      2,583,057
Author_Response_Access-2026-28862_v4.docx       24,663
```

---

### TASK A — Verify the Drive upload set (do this first)

Open the Drive folder above. Confirm it contains **8 files**: the four listed
above plus `00_README_Portal_Upload_Map_v2.2.md`,
`Cover_Letter_Access-2026-28862`, `Conflict_of_Interest_Statement.pdf`, and
`Author_Bios_and_Photos.docx`.

Report each of the four upload files with its byte size, and whether it
matches the list above exactly. If any size differs, stop and report — a
mismatched file must not be uploaded to the portal.

---

### TASK B — Stage the portal resubmission, but DO NOT SUBMIT

Only do this if the owner explicitly asks in this session. If they have not,
skip to Task C and say you skipped it.

Go to the IEEE Author Portal, open **Access-2026-28862**, and start (or
resume) the resubmission. Note that a Submission 2 draft may already exist
carrying the older **v3** files — if so, those attachments are **stale and
must be replaced**, because every one of the four changed.

Slot mapping:

| Portal slot | File |
|---|---|
| Main Manuscript (PDF) | integration-patterns-v4.pdf |
| Main Manuscript (LaTeX source) | integration-patterns-v4-latex.zip |
| Author Response (required) | Author_Response_Access-2026-28862_v4.docx |
| Author's Tracked Changes (optional) | integration-patterns-v4-HIGHLIGHTED.pdf |
| Conflict of Interest | Conflict_of_Interest_Statement.pdf (unchanged, reuse) |
| Author Bios and Photos | Author_Bios_and_Photos.docx (unchanged, reuse) |
| Cover letter | Cover_Letter_Access-2026-28862 (export the Google Doc to PDF) |

Attach everything, then **STOP at the final review page**. Screenshot it,
report what is attached in each slot, and hand control back. **Do not click
Submit.**

---

### TASK C — AWS cost check (read-only)

The project left billable resources running deliberately, for
reproducibility. Confirm they exist and report anything unexpected.

Go to https://console.aws.amazon.com/costmanagement/home#/cost-explorer and
report month-to-date spend for the account. Expected: **under $10 total**,
with the ongoing run rate roughly **$0.20–0.50/month**.

Then confirm these exist (read-only, change nothing):

- Bedrock AgentCore → Runtimes: expect **11**, named `anchorp1`, `anchorp2`,
  `anchorp1rel` … `anchorp7rel`, `p7probe`, `p7retry`
- Bedrock AgentCore → Memory: `agentorch_all7_mem-EeJ36664JO`
- Bedrock AgentCore → Gateways: `agentorch-all7-gw-iambvbawex`
- Bedrock → Guardrails: `0rwf5fcew9ss`
- Lambda: `agentorch-all7-tool`

If month-to-date spend exceeds $10, stop and report — that would mean
something is running that should not be.

---

### TASK D — Retire two superseded runtimes (ONLY on explicit instruction)

Do not do this unless the owner says so in this session. Deletion is
irreversible.

`anchorp1` and `anchorp2` are superseded by `anchorp1rel` and `anchorp2rel`,
which run the released modules rather than hand-written copies. Only those
two may be retired.

**Do NOT delete** `p7probe` or `p7retry` — the manuscript's Section VI-H
cites records produced by them. **Do NOT delete** any `*rel` runtime, the
Memory, the Gateway, the Guardrail, or the Lambda.

---

### TASK E — Post-submission security cleanup (ONLY after submission)

Do not do any of this until the owner confirms the paper has been submitted.
It is deliberately deferred, because it revokes credentials the project still
uses.

1. IAM → Users → `anchor-runner` → Security credentials → **deactivate** the
   active access key (do not delete it yet).
2. Salesforce → Setup → App Manager → `Anchor API Client CC` → **rotate** the
   consumer secret.
3. GitHub → delete stale branches: `autonomous-build`, `phase2-calibration`,
   `phase3-fitmatrix`, `revision/*`. Keep `main`.

---

### What to report back

For each task attempted: what you did, exact values you saw, and anything
that did not match this brief. If you skipped a task because it was gated on
owner instruction, say which and why.

Do not summarise this brief back. Report only observations and actions.

## END OF BRIEF
