# Atomic Task Backlog — All Seven Patterns Live on AWS

> Completion promise: PROJECT_COMPLETE
> Dependency-ordered. No task depends on a higher-numbered task.
> `prd.json` is the machine-readable source of truth.

Repo conventions every task inherits: Python 3.12; `agentorch` imported from
`src/` on `PYTHONPATH`; pytest in `tests/`; live clients live under
`anchor/agentcore/`; recorded results under `anchor/results/` are **append-only
evidence** — never overwrite a committed record.

---

## M0 — Repo audit + contract harness

### TASK 000 — Create the live-client contract test harness
- Milestone: M0
- Depends on: none
- Context: `tests/` holds 242 passing tests but nothing that checks a live client against the mock interface it replaces. `src/agentorch/clients/bedrock.py` defines `MockBedrockAgentRuntime`, `MockAgentCore`, `MockGuardrails`.
- Do: Create `tests/test_live_contract.py` with one trivial passing test asserting `MockAgentCore` exposes `gateway_call`, `memory_get`, `memory_put`, `observability_emit`. This is the harness the rest of M0/M1 builds on.
- Constraints / Do NOT: Do not import boto3. Do not make network calls. Do not modify any mock.
- Done-check: `python -m pytest tests/test_live_contract.py -q` → 1 passed.
- Review gate: AUTO

### TASK 001 — Add a signature-comparison helper to the contract harness
- Milestone: M0
- Depends on: 000
- Context: Contract drift is silent unless argument names are compared, not just method presence. `LiveBedrockAgentRuntime` in `anchor/agentcore/agent_released/agent_app.py` already mirrors `invoke_agent(agentId, agentAliasId, sessionId, inputText)`.
- Do: Add `assert_signature_compatible(mock_cls, live_cls, method)` to `tests/test_live_contract.py` using `inspect.signature`, comparing parameter names in order (ignoring `self`). Apply it to `invoke_agent` for the existing live client.
- Constraints / Do NOT: Do not relax the check to name-only. Argument *names* matter here because the patterns call with keywords.
- Done-check: `python -m pytest tests/test_live_contract.py -q` → all pass.
- Review gate: AUTO

### TASK 002 — Record the per-pattern seam surface as a test fixture
- Milestone: M0
- Depends on: 001
- Context: Each pattern's Bedrock branch touches a known set of seam methods (P1: invoke_agent; P3: +observability_emit; P4: +memory_get/put; P5: +gateway_call; P6: +guardrails.apply, memory_put).
- Do: Create `tests/fixtures/seam_surface.json` mapping each pattern id to the seam methods its Bedrock branch calls. Add a test asserting the file parses and covers P1–P7.
- Constraints / Do NOT: Do not derive this by regex at test time — commit it as a reviewed fixture so a change to a pattern shows up as a diff.
- Done-check: `python -m pytest tests/test_live_contract.py -q` → all pass.
- Review gate: AUTO

### TASK 003 — Assert the seam fixture matches the patterns' actual source
- Milestone: M0
- Depends on: 002
- Context: The fixture in TASK 002 will rot if a pattern changes.
- Do: Add a test that parses each `src/agentorch/patterns/p*.py` with `ast`, collects `self.<client>.<method>` attribute calls inside the Bedrock branch, and asserts it equals the fixture. Fail with a message naming the drifting pattern.
- Constraints / Do NOT: Do not modify the patterns to make this easier. If the AST walk is awkward, that is a property of the code, not a reason to edit it.
- Done-check: `python -m pytest tests/test_live_contract.py -q` → all pass.
- Review gate: AUTO

### TASK 004 — Confirm the full suite is unaffected
- Milestone: M0
- Depends on: 003
- Context: M0 added tests only; nothing in `src/` should have changed.
- Do: Run the full suite and confirm 242 pre-existing tests still pass alongside the new ones. Record the count in `orchestration/all7/progress.txt`.
- Constraints / Do NOT: Do not fix unrelated failures here; log them and stop.
- Done-check: `python -m pytest -q` → 0 failures.
- Review gate: AUTO

---

## M1 — Live client interfaces and stubs (no spend)

### TASK 010 — Create the live-clients module skeleton
- Milestone: M1
- Depends on: 004
- Context: `anchor/agentcore/agent_released/agent_app.py` holds `LiveBedrockAgentRuntime` inline. The four new methods need a shared home.
- Do: Create `anchor/agentcore/live_clients.py`. Move `LiveBedrockAgentRuntime` into it unchanged and import it back into `agent_app.py`. Add empty `LiveAgentCore` and `LiveGuardrails` classes with docstrings stating they must not call `ctx.boundary_call`.
- Constraints / Do NOT: Do not change `LiveBedrockAgentRuntime`'s behaviour — this is a move, not a rewrite. The existing P1/P2 live results must remain reproducible by the same code path.
- Done-check: `python -m pytest -q` → 0 failures; `python -c "from anchor.agentcore.live_clients import LiveBedrockAgentRuntime"` exits 0.
- Review gate: AUTO

### TASK 011 — Document the no-boundary_call rule in the module
- Milestone: M1
- Depends on: 010
- Context: The mocks call `ctx.boundary_call(...)` to drive virtual latency and fault injection. A live client that did so would contaminate the deterministic study's timing model.
- Do: Add a module-level docstring to `live_clients.py` explaining the rule and why `virtual_service_time_s` therefore comes back as 0.0 from live runs. Add a test asserting no live client class references `boundary_call` (source scan).
- Constraints / Do NOT: Do not add a mechanism that "supports both" — the separation is the point.
- Done-check: `python -m pytest tests/test_live_contract.py -q` → all pass.
- Review gate: AUTO

### TASK 012 — Stub `observability_emit` with an in-memory sink
- Milestone: M1
- Depends on: 011
- Context: P3 calls `self.agentcore.observability_emit({...})` once per event. The mock appends to `observability_events`.
- Do: Add `observability_emit(self, event: dict) -> None` to `LiveAgentCore`, initially appending to `self.emitted` and incrementing `self.service_calls`. Same signature as the mock.
- Constraints / Do NOT: No boto3 yet — this task is interface only.
- Done-check: `python -m pytest tests/test_live_contract.py -q` → signature-compatible with `MockAgentCore.observability_emit`.
- Review gate: AUTO

### TASK 013 — Stub `memory_get` / `memory_put` with an in-memory dict
- Milestone: M1
- Depends on: 012
- Context: P4 does put(key, []) → get → append → put → get. P6 calls put once. The mock stores in `self._memory`.
- Do: Add `memory_get(self, key)` and `memory_put(self, key, value)` to `LiveAgentCore` backed by a dict, incrementing `service_calls`. Match mock signatures exactly.
- Constraints / Do NOT: Do not change the return contract — `memory_get` returns the stored value or `None`, exactly as the mock does. P4 depends on that.
- Done-check: `python -m pytest tests/test_live_contract.py -q` → all pass.
- Review gate: AUTO

### TASK 014 — Stub `gateway_call`
- Milestone: M1
- Depends on: 013
- Context: P5 calls `self.agentcore.gateway_call(tool, {...})` and reads the returned dict. The mock returns `{"tool":…, "result":…, "args":…}` and counts **two** service calls (gateway hop + tool).
- Do: Add `gateway_call(self, tool, args)` to `LiveAgentCore` returning the same shape and incrementing `service_calls` by 2, mirroring the mock's hop-plus-tool accounting.
- Constraints / Do NOT: Do not collapse the two counted calls into one — the extra hop is the pattern's structural consequence and must stay visible.
- Done-check: `python -m pytest tests/test_live_contract.py -q` → all pass.
- Review gate: AUTO

### TASK 015 — Stub `guardrails.apply`
- Milestone: M1
- Depends on: 014
- Context: P6's Bedrock branch calls `self.guardrails.apply(draft, mode="shadow")`. The mock returns a dict and never blocks in shadow mode.
- Do: Add `apply(self, text, mode="shadow")` to `LiveGuardrails` returning the mock's shape, raising `ValueError` for a mode outside `{"shadow","block"}` exactly as the mock does.
- Constraints / Do NOT: Do not implement blocking behaviour. P6's claim is about the human step, not about guardrail enforcement.
- Done-check: `python -m pytest tests/test_live_contract.py -q` → all pass.
- Review gate: AUTO

### TASK 016 — Contract-test all four stubs against their mocks
- Milestone: M1
- Depends on: 015
- Context: TASK 001 gave the helper; TASKs 012–015 gave the methods.
- Do: Extend `tests/test_live_contract.py` to assert signature compatibility for every method in `tests/fixtures/seam_surface.json` across `LiveAgentCore` / `LiveGuardrails` / `LiveBedrockAgentRuntime`.
- Constraints / Do NOT: Do not skip a method because it is "obviously fine".
- Done-check: `python -m pytest tests/test_live_contract.py -q` → all pass.
- Review gate: AUTO

### TASK 017 — Add a seam-swap helper
- Milestone: M1
- Depends on: 016
- Context: `agent_app.py` currently swaps one attribute. Seven patterns need up to three swapped.
- Do: Add `attach_live_clients(pattern)` to `live_clients.py` that assigns `pattern.bedrock`, and assigns `pattern.agentcore` / `pattern.guardrails` when those attributes already exist on the pattern. Return the client bundle for counter access.
- Constraints / Do NOT: Do not create attributes the pattern does not already define — that would change `agentorch`'s object shape rather than swapping its collaborators.
- Done-check: `python -m pytest tests/test_live_contract.py -q` → all pass.
- Review gate: AUTO

### TASK 018 — Confirm suite still green after M1
- Milestone: M1
- Depends on: 017
- Context: M1 touched `anchor/` and `tests/` only.
- Do: Run the full suite; append the result to `orchestration/all7/progress.txt`.
- Constraints / Do NOT: Do not proceed to M2 on a red suite.
- Done-check: `python -m pytest -q` → 0 failures.
- Review gate: AUTO

---

## M2 — All seven patterns offline through stub live clients

### TASK 020 — Create the offline all-seven test module
- Milestone: M2
- Depends on: 018
- Context: A local run proved P1/P2 accept the seam swap. The other five are unproven offline.
- Do: Create `tests/test_all7_stub.py` that builds a `CallContext` via `CallContext.build(cfg, sink=TelemetrySink(), stream_prefix=…)`, constructs each pattern for `Platform.BEDROCK`, calls `attach_live_clients`, runs one `WorkItem` on S1, and asserts `result.status == "ok"`.
- Constraints / Do NOT: Do not modify any pattern to make it pass. A failure here is a finding about the seam, and must be reported, not patched around.
- Done-check: `python -m pytest tests/test_all7_stub.py -q` → all pass.
- Review gate: AUTO

### TASK 021 — Assert P1's structural signature offline
- Milestone: M2
- Depends on: 020
- Context: P1 = plan + n_collaborators fan-out + synthesis. With `n_collaborators=3` that is 5 model invocations.
- Do: Assert `bedrock.invocations == 5` and `result.payload["n_collaborators"] == 3`.
- Constraints / Do NOT: Do not hard-code 5 if config changes it — derive from `cfg.patterns.p1.n_collaborators`.
- Done-check: `python -m pytest tests/test_all7_stub.py -q` → all pass.
- Review gate: AUTO

### TASK 022 — Assert P2's structural signature offline
- Milestone: M2
- Depends on: 021
- Context: P2 on S1 is a single stage → 1 invocation.
- Do: Assert `bedrock.invocations == 1` and `result.payload["n_steps"] == 1`.
- Constraints / Do NOT: Do not assume S1 always means one stage — read it from the pattern's own `_stages(item)`.
- Done-check: `python -m pytest tests/test_all7_stub.py -q` → all pass.
- Review gate: AUTO

### TASK 023 — Assert P3's structural signature offline
- Milestone: M2
- Depends on: 022
- Context: P3 emits one observability event per handled event alongside its model calls.
- Do: Assert `agentcore.emitted` is non-empty and its length equals the number of events the pattern processed.
- Constraints / Do NOT: Do not assert an absolute count without deriving it from the scenario.
- Done-check: `python -m pytest tests/test_all7_stub.py -q` → all pass.
- Review gate: AUTO

### TASK 024 — Assert P4's structural signature offline
- Milestone: M2
- Depends on: 023
- Context: P4 does an initial `memory_put`, then per-specialist get/append/put, then a final `memory_get`.
- Do: Assert the stub's memory recorded at least one put before any get, and that the final get returns a list whose length equals the specialist count.
- Constraints / Do NOT: Do not weaken to "memory was touched" — ordering is the pattern's contention claim.
- Done-check: `python -m pytest tests/test_all7_stub.py -q` → all pass.
- Review gate: AUTO

### TASK 025 — Assert P5's structural signature offline
- Milestone: M2
- Depends on: 024
- Context: P5 routes through the gateway; each tool call costs a gateway hop plus the tool itself.
- Do: Assert `service_calls` increased by exactly 2 per `gateway_call`, and that the tools called match the pattern's tool list.
- Constraints / Do NOT: Do not relax the ×2 accounting.
- Done-check: `python -m pytest tests/test_all7_stub.py -q` → all pass.
- Review gate: AUTO

### TASK 026 — Assert P6's structural signature offline
- Milestone: M2
- Depends on: 025
- Context: P6's Bedrock branch drafts via a model call, applies a shadow guardrail, writes memory, and waits on a **modelled** human delay sampled from `ctx.latency_model`.
- Do: Assert the guardrail was applied exactly once in shadow mode, memory was written, and the human wait came from the latency model rather than a client call.
- Constraints / Do NOT: Do not attempt to make the human step live. Record in the test docstring that it is modelled — this bound must not get lost.
- Done-check: `python -m pytest tests/test_all7_stub.py -q` → all pass.
- Review gate: AUTO

### TASK 027 — Assert P7's structural signature offline
- Milestone: M2
- Depends on: 026
- Context: P7's Bedrock branch is the bridge target; the CRM side is not exercised offline.
- Do: Assert the pattern completes with `status == "ok"` and made at least one model invocation. Document in the docstring that the CRM half is covered by the separate live probe, not here.
- Constraints / Do NOT: Do not simulate Salesforce in this test.
- Done-check: `python -m pytest tests/test_all7_stub.py -q` → all pass.
- Review gate: AUTO

### TASK 028 — Freeze the seven structural signatures as a fixture
- Milestone: M2
- Depends on: 027
- Context: These counts become the live runs' expectations in M6.
- Do: Write `tests/fixtures/pattern_signatures.json` capturing per-pattern expected invocation and service-call counts on S1, generated from the passing tests. Add a test asserting the offline run reproduces it.
- Constraints / Do NOT: Do not regenerate this fixture automatically in CI — it is a reviewed baseline, like `fit_agreed_cells.json`.
- Done-check: `python -m pytest -q` → 0 failures.
- Review gate: AUTO

---

## M3 — Provision AWS resources (ALL HUMAN-GATED)

### TASK 030 — Write the provisioning script (no execution)
- Milestone: M3
- Depends on: 028
- Context: `anchor/agentcore/deploy_agentcore.py` shows the house style for idempotent AWS setup.
- Do: Write `anchor/agentcore/provision_all7.py` that can create an AgentCore Memory, a Gateway plus one Target, and a Bedrock Guardrail in shadow mode — each idempotent, each printing what it would create under `--dry-run`.
- Constraints / Do NOT: **Do not execute it against AWS in this task.** `--dry-run` only. Do not reuse `p7probe_mem-…`; the P7 probe's records cite it.
- Done-check: `python anchor/agentcore/provision_all7.py --dry-run` → prints the three planned resources, creates nothing.
- Review gate: AUTO

### TASK 031 — Human review of the provisioning plan
- Milestone: M3
- Depends on: 030
- Context: The next task spends money and creates persistent billable resources.
- Do: Present the `--dry-run` output, the expected monthly cost, and the cleanup procedure to the human.
- Constraints / Do NOT: Do not create anything. Do not proceed without an explicit approval recorded in `progress.txt`.
- Done-check: FLAG FOR HUMAN REVIEW.
- Review gate: HUMAN-REVIEW-REQUIRED

### TASK 032 — Create the AgentCore Memory resource
- Milestone: M3
- Depends on: 031
- Context: Needed by P4 and P6.
- Do: Run the provisioning script's memory step; record the resource id in `anchor/agentcore/resources_all7.json`.
- Constraints / Do NOT: Do not touch the P7 probe's memory.
- Done-check: FLAG FOR HUMAN REVIEW — show the created id and a successful read-back.
- Review gate: HUMAN-REVIEW-REQUIRED

### TASK 033 — Create the AgentCore Gateway and one Target
- Milestone: M3
- Depends on: 032
- Context: Needed by P5. The target is a stand-in demonstrating the extra hop, not a production tool mesh.
- Do: Create the gateway and a single minimal target; record identifiers in `resources_all7.json`.
- Constraints / Do NOT: Do not expose anything publicly writable. Do not attach real data sources.
- Done-check: FLAG FOR HUMAN REVIEW — show gateway status and one successful tool invocation.
- Review gate: HUMAN-REVIEW-REQUIRED

### TASK 034 — Create the Bedrock Guardrail in shadow mode
- Milestone: M3
- Depends on: 033
- Context: Needed by P6, which calls `apply(..., mode="shadow")`.
- Do: Create a minimal guardrail configured not to block; record its id and version.
- Constraints / Do NOT: Do not enable blocking. Do not add content policies beyond what the shadow demonstration needs.
- Done-check: FLAG FOR HUMAN REVIEW — show `ApplyGuardrail` returning a non-blocking assessment.
- Review gate: HUMAN-REVIEW-REQUIRED

### TASK 035 — Extend the execution role for the new services
- Milestone: M3
- Depends on: 034
- Context: The role `AmazonBedrockAgentCoreSDKRuntime-us-east-1-…` carries an additive inline policy `AnchorAgentCoreExtras`. Memory, gateway and guardrail permissions are missing.
- Do: Extend that inline policy with the minimum actions needed, scoped to the resources created in 032–034.
- Constraints / Do NOT: **Do not modify the p7probe inline policy.** Do not use wildcard resources where an ARN is known. This is an IAM change — the skill's forbidden list names it.
- Done-check: FLAG FOR HUMAN REVIEW — show the policy diff before and after.
- Review gate: HUMAN-REVIEW-REQUIRED

### TASK 036 — Verify every provisioned resource is reachable
- Milestone: M3
- Depends on: 035
- Context: IAM propagation is not immediate; the released-module deploy hit exactly this.
- Do: Write `anchor/agentcore/check_resources.py` probing each resource read-only, retrying on AccessDenied for up to 5 minutes.
- Constraints / Do NOT: Do not treat a first AccessDenied as fatal; do not treat a persistent one as transient.
- Done-check: `python anchor/agentcore/check_resources.py` → all three reachable, exit 0.
- Review gate: AUTO

### TASK 037 — Record the provisioned inventory
- Milestone: M3
- Depends on: 036
- Context: The cleanup task in M7 needs an exact list.
- Do: Commit `anchor/agentcore/resources_all7.json` with ids, ARNs, region and creation date, and note in `progress.txt` that these bill until retired.
- Constraints / Do NOT: Do not commit any credential or token.
- Done-check: `python -c "import json;d=json.load(open('anchor/agentcore/resources_all7.json'));assert {'memory','gateway','guardrail'} <= d.keys()"` exits 0.
- Review gate: AUTO

---

## M4 — Live client implementations, each smoke-tested standalone

### TASK 040 — Implement `observability_emit` against CloudWatch
- Milestone: M4
- Depends on: 037
- Context: The stub appends in memory. P3 needs real emission.
- Do: Replace the stub body with a CloudWatch Logs `PutLogEvents` (or EMF) emit to a dedicated log group, keeping the signature and the in-memory `emitted` list for assertions.
- Constraints / Do NOT: Do not emit event payload content beyond ids and counters — the redaction rule applies to every recorded surface.
- Done-check: `python -m pytest tests/test_live_contract.py -q` → all pass (signature unchanged).
- Review gate: AUTO

### TASK 041 — Smoke-test `observability_emit` live, standalone
- Milestone: M4
- Depends on: 040
- Context: Every live method is proven alone before being wired into a pattern.
- Do: Emit 3 events; read them back from CloudWatch; write `anchor/results/smoke_observability.json`.
- Constraints / Do NOT: Do not proceed to P3 deployment if read-back fails.
- Done-check: `python anchor/agentcore/smoke_observability.py` → 3 events emitted and read back, exit 0.
- Review gate: AUTO

### TASK 042 — Implement `memory_put` against AgentCore Memory
- Milestone: M4
- Depends on: 041
- Context: P4 writes a list and reads it back; the value round-trip must be lossless.
- Do: Implement `memory_put` writing a JSON-serialised value keyed by `key` into the provisioned memory resource.
- Constraints / Do NOT: Do not silently truncate. If the service imposes a size limit, fail loudly rather than storing a partial value.
- Done-check: `python -m pytest tests/test_live_contract.py -q` → all pass.
- Review gate: AUTO

### TASK 043 — Implement `memory_get` against AgentCore Memory
- Milestone: M4
- Depends on: 042
- Context: The mock returns the stored value or `None` for a missing key. P4 relies on that.
- Do: Implement `memory_get` returning the deserialised value, or `None` when absent.
- Constraints / Do NOT: Do not raise on a missing key — that would change the contract P4 depends on.
- Done-check: `python -m pytest tests/test_live_contract.py -q` → all pass.
- Review gate: AUTO

### TASK 044 — Smoke-test memory round-trip live, standalone
- Milestone: M4
- Depends on: 043
- Context: Round-trip fidelity is the whole risk for P4.
- Do: put/get a list of 3 dicts, a missing key, and an overwrite; assert exact equality and `None` for absent. Write `anchor/results/smoke_memory.json`.
- Constraints / Do NOT: Do not assert only on the happy path.
- Done-check: `python anchor/agentcore/smoke_memory.py` → all three cases pass, exit 0.
- Review gate: AUTO

### TASK 045 — Implement `gateway_call` against the AgentCore Gateway
- Milestone: M4
- Depends on: 044
- Context: The mock counts a gateway hop plus a tool call. Live, both are real.
- Do: Implement `gateway_call(tool, args)` invoking the provisioned gateway target, returning the mock's dict shape and counting two service calls.
- Constraints / Do NOT: Do not bypass the gateway and call the tool directly — the hop is the pattern's structural claim.
- Done-check: `python -m pytest tests/test_live_contract.py -q` → all pass.
- Review gate: AUTO

### TASK 046 — Smoke-test `gateway_call` live, standalone
- Milestone: M4
- Depends on: 045
- Context: First spend on the gateway path.
- Do: Invoke two distinct tools; record latency and the two-call accounting to `anchor/results/smoke_gateway.json`.
- Constraints / Do NOT: Do not report the hop latency as a pattern-level latency claim.
- Done-check: `python anchor/agentcore/smoke_gateway.py` → both tools return, exit 0.
- Review gate: AUTO

### TASK 047 — Implement `guardrails.apply` against ApplyGuardrail
- Milestone: M4
- Depends on: 046
- Context: P6 calls it in shadow mode only.
- Do: Implement `apply(text, mode)` calling `bedrock-runtime:ApplyGuardrail` against the provisioned guardrail, returning the mock's dict shape, preserving the `ValueError` on an invalid mode.
- Constraints / Do NOT: Do not implement blocking. Do not send the draft text to any destination other than the guardrail API.
- Done-check: `python -m pytest tests/test_live_contract.py -q` → all pass.
- Review gate: AUTO

### TASK 048 — Smoke-test `guardrails.apply` live, standalone
- Milestone: M4
- Depends on: 047
- Context: Shadow mode must never block.
- Do: Apply the guardrail to a benign string and to a string designed to trip a policy; assert neither blocks in shadow mode. Write `anchor/results/smoke_guardrails.json`.
- Constraints / Do NOT: Do not record the assessed text — counters and verdicts only.
- Done-check: `python anchor/agentcore/smoke_guardrails.py` → both non-blocking, exit 0.
- Review gate: AUTO

### TASK 049 — Re-run the contract suite against live implementations
- Milestone: M4
- Depends on: 048
- Context: Signatures must have survived four rewrites.
- Do: Run the contract and stub suites; confirm no signature drifted.
- Constraints / Do NOT: Do not edit a test to accommodate a drifted signature — fix the client.
- Done-check: `python -m pytest tests/test_live_contract.py tests/test_all7_stub.py -q` → all pass.
- Review gate: AUTO

### TASK 050 — Human review of first live spend across four services
- Milestone: M4
- Depends on: 049
- Context: Four new billable code paths are now exercised.
- Do: Present the four smoke records and the observed cost to the human.
- Constraints / Do NOT: Do not begin M5 deployment before approval is recorded.
- Done-check: FLAG FOR HUMAN REVIEW.
- Review gate: HUMAN-REVIEW-REQUIRED

### TASK 051 — Confirm suite green after M4
- Milestone: M4
- Depends on: 050
- Context: Live clients now reach real services; offline tests must not have started requiring credentials.
- Do: Run the full suite with AWS credentials **unset** to prove offline tests remain credential-free.
- Constraints / Do NOT: Do not mark done if any test needs credentials — that would break the repo's no-credentials gate.
- Done-check: `env -u AWS_ACCESS_KEY_ID -u AWS_SECRET_ACCESS_KEY python -m pytest -q` → 0 failures.
- Review gate: AUTO

---

## M5 — Container and deployment

### TASK 055 — Generalise the agent app to all seven patterns
- Milestone: M5
- Depends on: 051
- Context: `agent_released/agent_app.py` handles P1/P2 via `ANCHOR_PATTERN`.
- Do: Extend it to construct any of P1–P7 from the registry, call `attach_live_clients`, and return per-pattern structural counters. Keep the pattern-mismatch refusal.
- Constraints / Do NOT: Do not import pattern classes individually — use `agentorch.patterns.registry` so a new pattern is picked up without editing this file.
- Done-check: `python -m pytest tests/test_all7_stub.py -q` → all pass.
- Review gate: AUTO

### TASK 056 — Extend the container to carry the new dependencies
- Milestone: M5
- Depends on: 055
- Context: The image installs `bedrock-agentcore`, `boto3`, `numpy`, `pandas`, `pyyaml` and puts `src/` on `PYTHONPATH`.
- Do: Confirm no new dependency is needed; if one is, add it and justify in the commit message.
- Constraints / Do NOT: Do not pip-install `agentorch` as a distribution — the claim depends on running the repo's own source tree.
- Done-check: `docker buildx build --platform linux/arm64 -f anchor/agentcore/agent_released/Dockerfile .` → succeeds.
- Review gate: AUTO

### TASK 057 — Human review before deploying seven runtimes
- Milestone: M5
- Depends on: 056
- Context: Seven persistent runtimes bill until retired.
- Do: Present the deployment plan and expected cost.
- Constraints / Do NOT: Do not deploy before approval.
- Done-check: FLAG FOR HUMAN REVIEW.
- Review gate: HUMAN-REVIEW-REQUIRED

### TASK 058 — Deploy runtimes for P3 and P4
- Milestone: M5
- Depends on: 057
- Context: `deploy_released.py` deploys one image as several runtimes with `ANCHOR_PATTERN` fixed.
- Do: Deploy `anchorp3rel` and `anchorp4rel` with a fresh image tag; record ARNs.
- Constraints / Do NOT: Do not reuse an existing image tag for rebuilt code — a cached image would silently run the old agent.
- Done-check: `python anchor/agentcore/deploy_released.py --patterns P3,P4` → both READY.
- Review gate: AUTO

### TASK 059 — Deploy runtimes for P5, P6 and P7
- Milestone: M5
- Depends on: 058
- Context: Same mechanism.
- Do: Deploy `anchorp5rel`, `anchorp6rel`, `anchorp7rel`; record ARNs.
- Constraints / Do NOT: Do not disturb `anchorp1rel` / `anchorp2rel`, whose records are already cited.
- Done-check: `python anchor/agentcore/deploy_released.py --patterns P5,P6,P7` → all READY.
- Review gate: AUTO

### TASK 060 — Smoke one request per newly deployed runtime
- Milestone: M5
- Depends on: 059
- Context: Every deployment so far has been smoke-tested before its recorded run.
- Do: Send one S1 request to each of the five new runtimes; assert `status == "ok"` and that the response names the released module and class.
- Constraints / Do NOT: Do not proceed to M6 if any pattern returns a `pattern:` error status.
- Done-check: `python anchor/agentcore/smoke_all7.py` → 5/5 ok, exit 0.
- Review gate: AUTO

### TASK 061 — Record the deployed inventory
- Milestone: M5
- Depends on: 060
- Context: Seven runtimes now exist plus the two probe runtimes.
- Do: Update `anchor/agentcore/runtimes_released.json` with all seven ARNs and the image digest each runs.
- Constraints / Do NOT: Do not omit the image digest — it is how a reader ties a record to the code that produced it.
- Done-check: `python -c "import json;d=json.load(open('anchor/agentcore/runtimes_released.json'));assert len(d['runtimes'])==7"` exits 0.
- Review gate: AUTO

### TASK 062 — Confirm suite green after M5
- Milestone: M5
- Depends on: 061
- Context: Deployment changed `agent_app.py` and the Dockerfile.
- Do: Run the full offline suite credential-free.
- Constraints / Do NOT: Do not skip the credential-free assertion.
- Done-check: `env -u AWS_ACCESS_KEY_ID -u AWS_SECRET_ACCESS_KEY python -m pytest -q` → 0 failures.
- Review gate: AUTO

---

## M6 — Live runs and recorded evidence

### TASK 065 — Human approval for the full recorded run
- Milestone: M6
- Depends on: 062
- Context: n=30 across seven patterns is the bulk of the spend.
- Do: Present the request count, estimated cost, and expected wall-clock.
- Constraints / Do NOT: Do not start before approval is recorded in `progress.txt`.
- Done-check: FLAG FOR HUMAN REVIEW.
- Review gate: HUMAN-REVIEW-REQUIRED

### TASK 066 — Write the all-seven run harness
- Milestone: M6
- Depends on: 065
- Context: `run_released_check.py` drives two patterns and asserts their structure.
- Do: Generalise it to all seven, reading expectations from `tests/fixtures/pattern_signatures.json`, writing per-pattern `.jsonl` plus a summary.
- Constraints / Do NOT: Do not merge these records into the anchor's timing summaries — this is a deployability and structure record, not a timing arm.
- Done-check: `python anchor/agentcore/run_all7.py --n 1` → 7 records written, exit 0.
- Review gate: AUTO

### TASK 067 — Run P3 and P4 live at n=30
- Milestone: M6
- Depends on: 066
- Context: P3 exercises observability, P4 memory.
- Do: Run both; assert structural signatures match the frozen fixture.
- Constraints / Do NOT: Do not retry a failed request silently — record failures with their status.
- Done-check: `python anchor/agentcore/run_all7.py --patterns P3,P4 --n 30` → `structure_as_expected` true.
- Review gate: AUTO

### TASK 068 — Run P5 and P6 live at n=30
- Milestone: M6
- Depends on: 067
- Context: P5 exercises the gateway, P6 the guardrail plus memory plus the modelled human step.
- Do: Run both; assert signatures; record explicitly that P6's human wait is modelled.
- Constraints / Do NOT: Do not describe P6's result as a live human-in-the-loop measurement.
- Done-check: `python anchor/agentcore/run_all7.py --patterns P5,P6 --n 30` → `structure_as_expected` true.
- Review gate: AUTO

### TASK 069 — Run P7 live at n=30 and re-run P1/P2 for parity
- Milestone: M6
- Depends on: 068
- Context: P1/P2 already have records, but a same-image parity run makes all seven comparable.
- Do: Run P7 at n=30; re-run P1/P2 into **new** files with a distinct record prefix.
- Constraints / Do NOT: **Do not overwrite `released_P1.jsonl` / `released_P2.jsonl`** — those are committed evidence.
- Done-check: `python anchor/agentcore/run_all7.py --patterns P7,P1,P2 --n 30` → `structure_as_expected` true; original files unmodified per `git status`.
- Review gate: AUTO

### TASK 070 — Aggregate the seven-pattern summary
- Milestone: M6
- Depends on: 069
- Context: Each run wrote its own summary.
- Do: Produce `anchor/results/all7_live_summary.json` with per-pattern counts, module/class names, image digest, and a top-level `all_seven_ok` boolean.
- Constraints / Do NOT: Do not compute the boolean as "no exceptions" — require every pattern's structural signature to match.
- Done-check: `python anchor/agentcore/analyze_all7.py` → prints the table, exit 0.
- Review gate: AUTO

### TASK 071 — Add the no-fabrication guard to the analyzer
- Milestone: M6
- Depends on: 070
- Context: `analyze_p7.py` refuses to report incomplete or unattributable runs; the same discipline applies here.
- Do: Make `analyze_all7.py` exit non-zero and refuse to emit a summary if any pattern has `n_ok < n_total`, if a signature mismatches, or if the image digest differs across patterns.
- Constraints / Do NOT: Do not let a partial run produce a publishable-looking summary.
- Done-check: `python anchor/agentcore/analyze_all7.py --self-test` → refuses a synthetic incomplete input, exit non-zero.
- Review gate: AUTO

### TASK 072 — Pull independent CloudWatch corroboration for P3
- Milestone: M6
- Depends on: 071
- Context: C3/C4 corroborated agent-reported counters from platform logs; P3's observability claim deserves the same.
- Do: Filter the log group for the recorded task ids and assert the emitted-event count matches the harness record.
- Constraints / Do NOT: Do not treat agreement as proof of anything beyond emission counts.
- Done-check: `python anchor/agentcore/corroborate_p3.py` → counts match, exit 0.
- Review gate: AUTO

### TASK 073 — Commit all seven records
- Milestone: M6
- Depends on: 072
- Context: `anchor/results/` is gitignored; existing records were added with `git add -f`.
- Do: Commit the seven `.jsonl` files, the summary, and the corroboration extract with `-f`.
- Constraints / Do NOT: Do not commit any credential. Do not commit completion text.
- Done-check: `git status --porcelain anchor/results/` → clean after commit.
- Review gate: AUTO

### TASK 074 — Verify redaction across every new record
- Milestone: M6
- Depends on: 073
- Context: Every recorded surface in this repo is redacted to ids, counters, timestamps and status.
- Do: Scan all new records for anything resembling model completion text (long free-text fields) and fail if found.
- Constraints / Do NOT: Do not whitelist a field to make the check pass.
- Done-check: `python scripts/check_redaction.py anchor/results/` → exit 0.
- Review gate: AUTO

---

## M7 — Verification and documentation

### TASK 075 — Extend the number-tracing verifier
- Milestone: M7
- Depends on: 074
- Context: `scripts/verify_manuscript_numbers.py` traces live values to committed artifacts and fails on drift.
- Do: Add the seven-pattern structural counts to it, so any future document claiming them is checked against the records.
- Constraints / Do NOT: Do not couple it to the manuscript — it must pass whether or not the paper cites these yet.
- Done-check: `python scripts/verify_manuscript_numbers.py paper/v3/main.tex` → exit 0.
- Review gate: AUTO

### TASK 076 — Update `anchor/README.md`
- Milestone: M7
- Depends on: 075
- Context: The README documents the anchor arms and the P7 probe.
- Do: Add a section describing the all-seven live deployment: what it shows, what it does not, and the exact bounds (P6's human step modelled; Agentforce untouched; not a timing arm).
- Constraints / Do NOT: Do not describe this as a benchmark or as production evidence.
- Done-check: `grep -c "modelled" anchor/README.md` → at least 1; suite green.
- Review gate: AUTO

### TASK 077 — Write the bounds document
- Milestone: M7
- Depends on: 076
- Context: These bounds will be quoted in any future paper text and must exist independently of it.
- Do: Write `docs/ALL7_LIVE_BOUNDS.md` listing every limitation: two of two platforms? no — one platform; modelled human; stand-in gateway target; S1 only; no timing claims; live runs outside the deterministic study.
- Constraints / Do NOT: Do not soften a bound to make the result sound stronger.
- Done-check: File exists and lists at least six distinct bounds; suite green.
- Review gate: AUTO

### TASK 078 — Full clean-clone reproduction
- Milestone: M7
- Depends on: 077
- Context: The repo's reproduction claim is bit-for-bit under `environment/requirements.lock`.
- Do: Clean-clone the branch, build the pinned venv, run `run.sh`, and assert `git status figures/` is empty.
- Constraints / Do NOT: Do not use the ambient interpreter — drift shows up as ULP differences in `table3.csv`.
- Done-check: `git status --short figures/` → empty after a locked `run.sh`.
- Review gate: AUTO

### TASK 079 — Human decision on resource retention
- Milestone: M7
- Depends on: 078
- Context: Memory, gateway, guardrail and seven runtimes bill until retired, and deletion is irreversible.
- Do: Present the inventory and cost; ask whether to retain for reproducibility or retire now.
- Constraints / Do NOT: **Do not delete anything autonomously.**
- Done-check: FLAG FOR HUMAN REVIEW.
- Review gate: HUMAN-REVIEW-REQUIRED

---

## M8 — Paper integration (ALL HUMAN-GATED, deferred by decision)

### TASK 080 — Draft the §V-A coverage update
- Milestone: M8
- Depends on: 079
- Context: §V-A currently states live execution covers two of seven patterns. If M6 succeeded, that number changes.
- Do: Draft replacement text stating exactly what the seven-pattern run establishes and what it does not.
- Constraints / Do NOT: Do not edit `paper/v3/main.tex`. Draft only. Do not claim Agentforce coverage.
- Done-check: FLAG FOR HUMAN REVIEW.
- Review gate: HUMAN-REVIEW-REQUIRED

### TASK 081 — Draft the R2.2 letter update
- Milestone: M8
- Depends on: 080
- Context: R2.2's residual is "two of seven patterns, one platform". The pattern half may now close.
- Do: Draft the replacement response paragraph.
- Constraints / Do NOT: Do not overstate; the platform half remains open.
- Done-check: FLAG FOR HUMAN REVIEW.
- Review gate: HUMAN-REVIEW-REQUIRED

### TASK 082 — Re-audit the affected comments
- Milestone: M8
- Depends on: 081
- Context: R2.2, R1.Q1 and R2.6 all cite the coverage figure.
- Do: Re-score those comments against the drafted text and the committed records.
- Constraints / Do NOT: Do not raise a score without an evidence quote.
- Done-check: FLAG FOR HUMAN REVIEW.
- Review gate: HUMAN-REVIEW-REQUIRED

### TASK 083 — Human decision: fold into the resubmission or defer
- Milestone: M8
- Depends on: 082
- Context: One resubmission is permitted. The manuscript is currently at 11/11 ≥95% and submittable as-is.
- Do: Present the strengthened evidence, the rebuild cost, and the delay, and ask for a decision.
- Constraints / Do NOT: Do not modify the manuscript, rebuild the upload set, or submit anything.
- Done-check: FLAG FOR HUMAN REVIEW.
- Review gate: HUMAN-REVIEW-REQUIRED
