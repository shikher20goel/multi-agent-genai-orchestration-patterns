# anchor/ - Live-endpoint anchor study (reviewer R1-1 / R2-2)

A deliberately bounded LIVE check of the emulator's structural claims:
the S1 baseline request set is issued against the live Amazon Bedrock
model runtime (Converse API) and a live Salesforce Agentforce agent
(Agent API), for patterns P1 (Supervisor: plan + parallel fan-out +
synthesis) and P2 (Pipeline: single stage), checking two directional
orderings the emulated study predicts:

1. Latency: P1 end-to-end > P2 on S1 (fan-out vs single stage).
2. Cost proxy: P1 issues more model invocations than P2.

It does NOT reproduce emulated absolute numbers, is not a benchmark, and
provides no production SLAs; live runs stay OUTSIDE the deterministic
statistics of the main study.

## Two AWS paths, and why there are two

Bedrock Agents Classic is closed to accounts without prior service usage
(new-customer cutoff July 30, 2026), so the first anchor run (1 Aug,
n=30, us-east-2) issued the pattern call sequences from the harness
process against the Converse API. That times a model call, not a managed
agent runtime.

The second run closes that gap. `agentcore/agent/` is deployed TWICE on
Bedrock AgentCore Runtime as two single-pattern agents - `anchorp1` and
`anchorp2` - whose pattern is fixed at deploy time by `ANCHOR_PATTERN`; a
payload asking for the other pattern is refused rather than served. P1's
plan / fan-out / synthesis therefore happens INSIDE the vendor's managed
runtime, and the harness only issues `InvokeAgentRuntime` and times it.
Prompts, call sequences and collaborator count are verbatim from
`live_bedrock.py`, so the only thing that differs between the two paths
is where the orchestration runs.

Because the AgentCore runtimes must live in us-east-1 (alongside the P7
probe's), the same config runs a same-region direct-Converse control
(`bedrock_direct_use1`). Without it, an AgentCore-vs-direct difference
would be confounded with the us-east-2 -> us-east-1 move.

Client-side latency and the runtime's own `in_runtime_latency_s` are both
recorded. The difference is managed-runtime overhead; it is reported,
never subtracted out.

## Offered concurrency

`concurrency: [1, 8]` runs the same request set at each level and reports
per-level medians and whether the P2 < P1 ordering is preserved at each.
Level 1 is the original sequential loop, unchanged. This is a directional
load contrast outside the deterministic study - no CIs, no tests.
Agentforce runs `[1, 4]` best-effort under org API limits; a throttle is
recorded as a result rather than worked around.

`record_prefix` names the output files and the summary key, and MUST be
set for any arm differing in region or size: reusing a name would
overwrite the 1 Aug records the manuscript's Table 9 cites.

Integrity: no result is ever hand-written; compare_anchor.py refuses to
run without real output from run_anchor.py. Raw responses are REDACTED
(latency, counts, status only - never completion text).

Run (original Converse-path anchor, us-east-2):
  pip install -r anchor/requirements.txt
  export AWS_ACCESS_KEY_ID=... AWS_SECRET_ACCESS_KEY=... AWS_DEFAULT_REGION=us-east-2
  export AGENTFORCE_CLIENT_ID=... AGENTFORCE_CLIENT_SECRET=...
  python -m anchor.run_anchor --config anchor/anchor_config.yaml
  python -m anchor.compare_anchor

Run (managed-runtime anchor + load contrast, us-east-1):
  python anchor/agentcore/deploy_agentcore.py --region us-east-1 \
      --copy-role-from p7probe          # writes agentcore/runtimes.json
  python -m anchor.run_anchor --config anchor/anchor_agentcore_config.yaml \
      --out-summary anchor/results/summary_agentcore.json
  python -m anchor.compare_anchor --summary anchor/results/summary_agentcore.json \
      --out anchor/results/anchor_findings_agentcore.json

The execution role passed to the runtimes needs `bedrock:InvokeModel` on
the anchor model and ECR pull on the `anchor-agentcore` repository. The
P7 probe's role did not (its agent makes no model call); the anchor run
added those as a SEPARATE inline policy, leaving the P7 policy untouched.
