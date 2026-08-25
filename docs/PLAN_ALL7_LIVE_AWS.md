# Plan — live-deploy all seven patterns on AWS

Scope decided 25-Aug-2026: **AWS-only, all seven patterns, Agentforce
deferred.** Paper integration decided after this lands.

## What is already true

P1, P2 and P7 already execute live on Bedrock AgentCore Runtime, and for
P1/P2 it is the *released* `agentorch` modules that run, not rebuilt
copies. The mechanism is the documented call-context seam: constructing
the pattern and reassigning one attribute.

    pattern.bedrock = LiveBedrockAgentRuntime(...)

Nothing in `agentorch` is edited. Extending to seven patterns is
therefore not a rewrite; it is implementing four more live client methods
behind the same seam, provisioning three AWS resources, and deploying.

## The seam surface, complete

Every pattern's Bedrock branch touches only these. `invoke_agent` is done;
the other four are the work.

| Method | Patterns | Live target | Status |
|---|---|---|---|
| `bedrock.invoke_agent` | all 7 | Converse API | DONE |
| `agentcore.observability_emit` | P3 | CloudWatch Logs / EMF | to build |
| `agentcore.memory_get` / `memory_put` | P4, P6 | AgentCore Memory | to build |
| `agentcore.gateway_call` | P5 | AgentCore Gateway + Target | to build |
| `guardrails.apply` | P6 | `ApplyGuardrail` | to build |

Verified against the account on 25-Aug: one Memory exists
(`p7probe_mem-…`), **zero** Gateways, **zero** Guardrails. `CreateMemory`,
`CreateGateway`, `CreateGatewayTarget` and the Guardrails APIs are all
reachable with current credentials.

## Design rule for every live client

The mocks call `ctx.boundary_call(...)` to drive virtual latency and fault
injection. **Live clients must not.** That machinery belongs to the
deterministic study; a live client that invoked it would contaminate the
emulated timing model with wall-clock behaviour and vice versa. Live
clients instead count their own real calls, exactly as
`LiveBedrockAgentRuntime` counts `invocations`. This is why
`virtual_service_time_s` comes back as 0.0 from a live run — visible in
the record rather than left to inference.

## Phases

### Phase 0 — Contract harness (no spend)
- `anchor/agentcore/live_clients.py`: live implementations of the four
  methods, same names, same argument names, same return shapes.
- Contract test asserting each live class exposes a signature-compatible
  method for every mock method the patterns call. This is the guard that
  keeps the seam claim true as either side changes; without it, drift is
  silent.
- Offline stub test running all seven released patterns against stub live
  clients, asserting each pattern's structural signature (invocation and
  service-call counts per pattern).

**Gate:** seven patterns run offline through the live-client interface;
contract test passes; existing 242 tests unaffected.

### Phase 1 — Provision (small spend)
- AgentCore Memory for P4/P6 (create `agentorch_mem`; do not reuse the P7
  probe's, whose records are cited).
- AgentCore Gateway + one Target for P5.
- Bedrock Guardrail in shadow mode for P6 — shadow, because the released
  P6 calls `apply(draft, mode="shadow")` and the pattern's claim is about
  the human step, not about blocking.
- Extend the execution role: memory read/write, gateway invoke,
  `bedrock:ApplyGuardrail`. Additive inline policy, as before.

**Gate:** every resource returns READY/ACTIVE and is reachable from a
one-shot probe before anything is deployed.

### Phase 2 — Live client implementations
One method at a time, each smoke-tested against the real service in
isolation before being wired into a pattern. The C3/C4 counter bug was
caught exactly this way; the same discipline applies here.

**Gate:** each method demonstrated live, standalone, with its record.

### Phase 3 — Deploy
One image, seven runtimes, `ANCHOR_PATTERN` fixed per deployment and a
mismatched payload refused — the existing convention. The image already
ships the repo's own `src/` on `PYTHONPATH`, so what executes stays
demonstrably the committed source.

**Gate:** seven runtimes READY; one smoke request each, naming the module
and class that ran.

### Phase 4 — Record
n = 30 per pattern on S1, plus each pattern's natural scenario where S1
does not exercise it (P3 burst, P6 human step). Structural assertions per
pattern, not just success counts.

**Gate:** `structure_as_expected` true for all seven; records committed.

### Phase 5 — Verify and document
Extend `verify_manuscript_numbers.py`-style tracing to the new records,
update `anchor/README.md`, and write the honest bounds list.

## Bounds that will remain true, and must be stated

- **P6's human step is modelled, not staffed.** On the Bedrock path the
  wait is a latency sample. "P6 live" means live model call, live
  guardrail, live memory — with a simulated human.
- **Agentforce is untouched.** These are the Bedrock instantiations only.
  The Agentforce instantiations of all seven remain undeployed.
- **Live runs stay outside the deterministic study.** No CIs, no tests, no
  commingling — the same rule the anchor already follows.
- **P5's gateway target is a stand-in**, not a production tool mesh; it
  demonstrates the extra hop the pattern predicts, nothing more.

## Cost

Model calls dominate and remain trivial (Nova Micro, ~1.5k requests).
Gateway and Memory are consumption-priced at negligible volume. Expect
well under $5. Resources persist and bill until the deferred cleanup.

## What this would do for the paper

R2.2's residual is "two of seven patterns, one platform". This closes the
pattern half and leaves the platform half. That is a materially stronger
answer — but it is a second round of §V-A/§VI-G/letter rewriting on a
manuscript currently at 11/11 ≥95%, and the single permitted resubmission
should not be spent casually. Decide after Phase 4, on evidence.
