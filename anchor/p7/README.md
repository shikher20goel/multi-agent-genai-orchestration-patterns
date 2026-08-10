# anchor/p7 — Live bridge probe for Pattern 7 (Federated Cross-Platform Bridge)

Bounded live probe exhibiting the dual-retry duplicate-delivery failure
class at a CRM/hyperscaler bridge, and its elimination by P7's single
idempotent ingress point. Companion to the `anchor/` latency/cost anchor;
same epistemic scope: directional structural check, not a benchmark.

- Retry Domain A: live Salesforce replay-based redelivery (at-least-once).
- Retry Domain B: documented AWS SDK auto-retry on transient
  `InvokeAgentRuntime` errors.
- Fault injection: seeded crash (p = 0.3, seed 42) after invocation,
  before durable replay-cursor persistence.

## Runs

| Run | Ingress | Question |
|---|---|---|
| C1 | off (anti-pattern) | do duplicates propagate into agent invocations? |
| C2 | on (P7 mandate)    | does idempotent ingress stop propagation? |

```bash
python anchor/p7/bridge_probe.py --config anchor/p7/p7_config.yaml --ingress off --run-label C1
python anchor/p7/bridge_probe.py --config anchor/p7/p7_config.yaml --ingress on  --run-label C2
python anchor/p7/analyze_p7.py anchor/p7/results
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
