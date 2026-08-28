#!/usr/bin/env bash
# Managed-runtime anchor + load contrast (R1-1 / R2-2).
#
# Assumes anchor/agentcore/runtimes.json exists (deploy_agentcore.py) and
# that AWS credentials are on the standard boto3 chain. Prompts for any
# Agentforce credential not already in the environment; values are never
# written to disk.
#
# Writes to summary_agentcore.json / anchor_findings_agentcore.json, NOT
# to the 1 Aug summary.json the manuscript's Table 9 cites.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"

[ -f anchor/agentcore/runtimes.json ] || {
    echo "anchor/agentcore/runtimes.json missing - run deploy_agentcore.py first" >&2
    exit 1
}

[ -n "${AGENTFORCE_CLIENT_ID:-}" ] || read -p "AGENTFORCE_CLIENT_ID: " AGENTFORCE_CLIENT_ID
[ -n "${AGENTFORCE_CLIENT_SECRET:-}" ] || {
    read -sp "AGENTFORCE_CLIENT_SECRET (hidden): " AGENTFORCE_CLIENT_SECRET; echo
}
export AGENTFORCE_CLIENT_ID AGENTFORCE_CLIENT_SECRET

python3 -u -m anchor.run_anchor \
    --config anchor/anchor_agentcore_config.yaml \
    --out-summary anchor/results/summary_agentcore.json

python3 -m anchor.compare_anchor \
    --summary anchor/results/summary_agentcore.json \
    --out anchor/results/anchor_findings_agentcore.json

echo "AGENTCORE_ANCHOR_DONE"
