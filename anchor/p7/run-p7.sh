#!/usr/bin/env bash
# P7 probe runner — prompts for the 3 SF secrets (hidden, session-only),
# then runs C1 (ingress off), C2 (ingress on), and the comparison.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"

read -p  "SF_MYDOMAIN (https://...my.salesforce.com): " SF_MYDOMAIN
read -p  "SF_CLIENT_ID: " SF_CLIENT_ID
read -sp "SF_CLIENT_SECRET (hidden): " SF_CLIENT_SECRET; echo
export SF_MYDOMAIN SF_CLIENT_ID SF_CLIENT_SECRET

python anchor/p7/bridge_probe.py --config anchor/p7/p7_config.yaml --ingress off --run-label C1
python anchor/p7/bridge_probe.py --config anchor/p7/p7_config.yaml --ingress on  --run-label C2
python anchor/p7/analyze_p7.py anchor/p7/results
echo "P7_PROBE_DONE"
