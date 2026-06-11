#!/usr/bin/env bash
# run.sh -- master reproduction script (task 051).
#
# From a clean checkout: installs the package, runs the full
# measurement study into results/, and regenerates ALL tables and
# figures into figures/. Idempotent: safe to rerun; outputs are
# overwritten deterministically (seed and config pinned in
# configs/default.yaml; provenance in results/manifest.json).
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"

PYTHON="${PYTHON:-python3}"

echo "== [1/4] Install package (editable, no deps re-resolution if already present) =="
if ! "$PYTHON" -c "import agentorch" >/dev/null 2>&1; then
    "$PYTHON" -m pip install --user -e . 2>/dev/null || "$PYTHON" -m pip install -e .
else
    echo "agentorch already importable; skipping install"
fi
"$PYTHON" -c "import agentorch; print('agentorch import OK')"

echo "== [2/4] Run the full measurement study -> results/ =="
mkdir -p results figures
"$PYTHON" -m agentorch.study.run_study --out results/

echo "== [3/4] Regenerate tables -> figures/ =="
"$PYTHON" -m agentorch.study.make_table3 --results results/ --out figures/table3.csv
"$PYTHON" -m agentorch.study.make_table4 --results results/ --out figures/table4_supplementary.csv
# fit_matrix.csv = the paper's Table 4 (pre-registered rule, docs/FIT_RULE.md).
# NOTE: the agreed-cell fixture (tests/fixtures/fit_agreed_cells.json) is
# COMMITTED, generated once by task 203 via --emit-agreed; run.sh does not
# regenerate it, so the agreement gate stays stable and explicit.
"$PYTHON" -m agentorch.study.make_fit_matrix --results results/ --out figures/fit_matrix.csv

echo "== [4/4] Regenerate figures -> figures/ =="
"$PYTHON" -m agentorch.study.figures_latency --results results/ --out figures/
"$PYTHON" -m agentorch.study.figures_cost   --results results/ --out figures/
"$PYTHON" -m agentorch.study.figures_fault  --results results/ --out figures/
"$PYTHON" -m agentorch.study.decision_tree  --out figures/

echo "== Outputs =="
ls -1 results/ figures/

for f in figures/table3.csv figures/fit_matrix.csv figures/table4_supplementary.csv figures/ccdf.png figures/p99_ci.png \
         figures/cost_per_1k.png figures/cost_ledger.csv figures/fault_matrix.png \
         figures/decision_tree.png results/manifest.json; do
    [ -f "$f" ] || { echo "MISSING expected output: $f" >&2; exit 1; }
done
echo "run.sh: all expected outputs present"
