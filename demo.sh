#!/usr/bin/env bash
# demo.sh -- tiny end-to-end demo (task 055): smoke study + one figure
# + printed per-pattern summary table. Completes in well under 40 s.
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"
PYTHON="${PYTHON:-python3}"

OUT_RESULTS="${DEMO_RESULTS:-results_demo}"
OUT_FIGURES="${DEMO_FIGURES:-figures_demo}"
mkdir -p "$OUT_RESULTS" "$OUT_FIGURES"

echo "== demo [1/3]: smoke measurement study -> $OUT_RESULTS/ =="
"$PYTHON" -m agentorch.study.run_study --smoke --out "$OUT_RESULTS/" >/dev/null
echo "wrote $OUT_RESULTS/{latency,cost,faults}.csv + manifest.json"

echo "== demo [2/3]: one figure (p99 with CIs) -> $OUT_FIGURES/ =="
"$PYTHON" -m agentorch.study.figures_latency --results "$OUT_RESULTS/" --out "$OUT_FIGURES/"
[ -f "$OUT_FIGURES/p99_ci.png" ] || { echo "demo figure missing" >&2; exit 1; }

echo "== demo [3/3]: per-pattern summary table (scenario S1, smoke n) =="
"$PYTHON" - "$OUT_RESULTS" <<'PYEOF'
import sys
import pandas as pd

res = sys.argv[1]
lat = pd.read_csv(f"{res}/latency.csv")
cost = pd.read_csv(f"{res}/cost.csv")
base = lat[(lat["mode"] == "baseline") & (lat["scenario"] == "S1")]
rows = []
for (pat, plat), g in base.groupby(["pattern", "platform"]):
    c = cost[(cost["pattern"] == pat) & (cost["platform"] == plat)]
    rows.append({
        "pattern": pat, "platform": plat, "n": len(g),
        "p50_ms": g["latency_ms"].quantile(0.50),
        "p99_ms": g["latency_ms"].quantile(0.99),
        "err_rate": 1.0 - g["success"].mean(),
        "cost_units_per_req": c["cost_units"].mean(),
    })
df = pd.DataFrame(rows).sort_values(["pattern", "platform"])
with pd.option_context("display.float_format", lambda v: f"{v:,.3f}"):
    print(df.to_string(index=False))
print("\ndemo complete: smoke study + p99 figure + summary table (deterministic, seed from configs/default.yaml)")
PYEOF
