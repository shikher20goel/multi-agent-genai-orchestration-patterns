# anchor/p7 — Live bridge probe for Pattern 7 (Federated Cross-Platform Bridge)

Bounded live probe exhibiting the dual-retry duplicate-delivery failure
class at a CRM/hyperscaler bridge, and its elimination by P7's single
idempotent ingress point. Companion to the `anchor/` latency/cost anchor;
same epistemic scope: directional structural check, not a benchmark.

- Retry Domain A: live Salesforce replay-based redelivery (at-least-once).
- Retry Domain B: the AWS SDK's documented transient-error retry on
  `InvokeAgentRuntime`.

Each direction gets its own pair of conditions, and in each pair the only
variable is where the idempotent ingress sits.

## C1/C2 - the CRM direction

Fault injection: seeded crash (p = 0.3, seed 42) after invocation, before
durable replay-cursor persistence, so the LIVE Salesforce replay
mechanism redelivers on resume. The ingress under test is in the bridge.

| Run | Bridge ingress | Question |
|---|---|---|
| C1 | off (anti-pattern) | do duplicates propagate into agent invocations? |
| C2 | on (P7 mandate)    | does idempotent ingress stop propagation? |

```bash
python anchor/p7/bridge_probe.py --config anchor/p7/p7_config.yaml --ingress off --run-label C1
python anchor/p7/bridge_probe.py --config anchor/p7/p7_config.yaml --ingress on  --run-label C2
python anchor/p7/analyze_p7.py anchor/p7/results
```

## C3/C4 - the AWS direction

In C1/C2 the SDK retry was armed at defaults and never fired, so that
surface stayed unexercised. C3/C4 exercise it in the same live bridge.

Why the measurement had to change: when the SDK reissues a request, the
bridge process never sees a second call - it made one. Counting
invocations client-side is blind to this direction by construction. So
`agent_retry/` reports `entry_count`, `executions` and `worker_id` from
INSIDE the runtime, and logs them to CloudWatch as independent evidence.

Attribution: no crash is injected, so the CRM direction contributes
nothing. The run records `deliveries == published` and
`redeliveries == 0`, and `analyze_p7.py` REFUSES to report the pair if
either fails - a duplicate execution then has only one domain it can have
come from.

The bridge's own idempotent ingress is ON in BOTH conditions and
suppresses nothing. That is half the finding: the reissued request is
created below the bridge, so an ingress must sit at the target boundary
to see it. Only the agent-side ingress varies.

The fault is a client read timeout shorter than the agent's cold-path
work time. botocore classifies `ReadTimeoutError` as a transient
`HTTPClientError`, one of the exception classes its standard retry mode
retries, so the reissue is the SDK's own behaviour. Wire attempts are
counted with a botocore `before-send` hook, so "the retry fired" is
evidence rather than inference; if it did not fire, `analyze_p7.py` says
so instead of reporting a result.

| Run | Bridge ingress | Agent ingress | Question |
|---|---|---|---|
| C3 | on | off (anti-pattern) | does an SDK reissue become a second agent execution? |
| C4 | on | on (P7 mandate)     | does a target-boundary ingress stop it? |

```bash
python anchor/p7/deploy_retry_agent.py --region us-east-1 --copy-role-from p7probe
python anchor/p7/retry_probe.py --config anchor/p7/p7_retry_config.yaml --agent-ingress off --run-label C3
python anchor/p7/retry_probe.py --config anchor/p7/p7_retry_config.yaml --agent-ingress on  --run-label C4
python anchor/p7/analyze_p7.py anchor/p7/results
```

C3/C4 deploy to a NEW `p7retry` runtime; the `p7probe` runtime C1/C2 ran
against is left exactly as it was.

## Offline gates (no credentials)

```bash
python anchor/p7/test_bridge_probe_mock.py   # C1/C2
python anchor/p7/test_retry_probe_mock.py    # C3/C4
```

Credentials via environment only (`SF_MYDOMAIN`, `SF_CLIENT_ID`,
`SF_CLIENT_SECRET`; AWS via standard chain). Recorded results under
`results/` are redacted: IDs, sequence numbers, timestamps, status —
never event payload content.

## What this does not claim

No latency/cost claims; no statistics; no model call (delivery semantics
are independent of model behavior); no claim of production operation.
See the manuscript's Section VI-H for scope.

Setup: `SF_SETUP.md` / `AWS_SETUP.md` (kit docs). Deps:
`pip install boto3 requests pyyaml`.
