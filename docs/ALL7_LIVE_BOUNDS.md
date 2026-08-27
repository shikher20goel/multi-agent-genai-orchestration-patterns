# What the seven-pattern live run does and does not establish

All seven released `agentorch` pattern modules executed on Amazon Bedrock
AgentCore Runtime, 30 requests each, 210/210 successful, every structural
signature matching the fixture frozen from the offline run. This document
records the bounds of that result, so they are available independently of
whatever text later cites it.

## What it establishes

- The released modules — not reconstructions of them — run on a live
  hyperscaler agent runtime. Each response names the module and class that
  executed, and the image carries the repository's own `src/` on `PYTHONPATH`
  rather than a separately resolved distribution.
- The mock-to-live substitution is the single call-context seam Section V-A
  describes. Nothing in `agentorch` is edited, subclassed or monkey-patched.
- Each pattern's own control flow produces its predicted structure live:
  the supervisor's five invocations, the pipeline's one, the choreography's
  event-per-emit, the blackboard's read-modify-write, the gateway's hop
  accounting, the HITL confidence gate, the bridge target.

## What it does NOT establish

1. **One platform.** These are the Bedrock instantiations. Nothing was
   deployed to Agentforce; its live evidence remains API-level invocation of
   an activated agent, which is not a deployment of an instantiation.
2. **P6's human step is modelled, not staffed.** On the Bedrock path the
   adjudication delay is a latency sample from the study's own model. "P6
   live" means live model call, live guardrail, live memory, simulated human.
   7 of 30 items paused; that is the confidence gate working, not a human
   deciding anything.
3. **P5's gateway hop is not live.** The AgentCore Gateway exists and is
   READY but has no target, because a target needs a Lambda or OpenAPI
   backend and no Lambda execution role could be created. P5's model calls
   are live; its gateway hop ran on the in-memory stub. Every P5 record
   carries `backends_live.gateway=false` and the analyzer prints the bound on
   every run.
4. **Not a timing arm.** The released `Pattern._parallel` runs fan-out
   branches sequentially and accounts only `max` of their durations, which is
   correct under the study's virtual clock and makes wall-clock here
   incomparable to the anchor's. No latency claim may be drawn from these
   records.
5. **One scenario.** S1 only. S2 and S3 were not run live.
6. **Outside the deterministic study.** No confidence intervals, no
   hypothesis tests, no commingling with the seeded emulation — the same rule
   the anchor already follows.
7. **P3's observability was not smoke-tested standalone.** The IAM user
   lacks `logs:PutLogEvents`; the execution role holds it, so emission was
   verified in the deployed run and corroborated from CloudWatch instead.

## How a reader can check

- `anchor/results/all7_summary.json` — per-pattern counts and `backends_live`
- `anchor/results/all7_P*.jsonl` — redacted per-request records
- `anchor/results/all7_p3_corroboration.json` — CloudWatch cross-check
- `anchor/agentcore/known_bounds.json` — declared bounds, machine-readable
- `python anchor/agentcore/analyze_all7.py` — refuses a partial run, a
  signature mismatch, an undeclared stub, or mixed image digests
- `python scripts/check_redaction.py anchor/results/` — redaction gate
