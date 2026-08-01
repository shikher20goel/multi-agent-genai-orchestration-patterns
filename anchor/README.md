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
statistics of the main study. Bedrock note: Bedrock Agents Classic is
closed to new accounts (July 30, 2026), so the anchor targets the
Converse API; an AgentCore-based anchor is follow-up work.

Integrity: no result is ever hand-written; compare_anchor.py refuses to
run without real output from run_anchor.py. Raw responses are REDACTED
(latency, counts, status only - never completion text).

Run:
  pip install -r anchor/requirements.txt
  export AWS_ACCESS_KEY_ID=... AWS_SECRET_ACCESS_KEY=... AWS_DEFAULT_REGION=us-east-2
  export AGENTFORCE_CLIENT_ID=... AGENTFORCE_CLIENT_SECRET=...
  python -m anchor.run_anchor --config anchor/anchor_config.yaml
  python -m anchor.compare_anchor
