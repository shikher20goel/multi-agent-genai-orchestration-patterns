# Results-to-paper mapping (task 043, HUMAN-gated)

Every `results/` and `figures/` output, the paper element it backs, the
exact command that generates it, and the source data it is computed
from. NOTHING in the manuscript may cite a number that does not trace
through this table. All commands run from the repository root after
the study run; the study itself is regenerated with:

```
python3 -m agentorch.study.run_study --out results/      # full study
python3 -m agentorch.study.run_study --smoke --out results/  # reduced smoke
```

Study provenance (seed, config hash, n per condition, git revision,
timestamp, wall time) is recorded in `results/manifest.json` by the run
itself.

## Raw results (results/, regenerated; gitignored)

| Output | Paper element it backs | Generating command | Source |
|---|---|---|---|
| `results/latency.csv` | All latency/error/throughput numbers (Tables 5–6 of the revised manuscript, latency figures); one row per request, `submit_ts`/`complete_ts` recorded separately (open-loop) | `python3 -m agentorch.study.run_study --out results/` | Executed rig: `agentorch.rig.loadgen` over all 42 baseline conditions + fault-mode windows |
| `results/cost.csv` | All cost numbers (Table 3 cost/request, supplementary cost grades, cost figure/ledger); one CostRecord per baseline request, scenario-tagged (task 105) | same run | `agentorch.rig.costcapture.capture_request_cost` with prices from `configs/costs.yaml` (HUMAN-gated dated assumptions; USD per request) |
| `results/faults.csv` | Fault-containment claims (supplementary reliability grades, Fig. fault matrix, Section on isolation) | same run | `agentorch.rig.faultcampaign.run_campaign` (Algorithm 2), 336 cells = 7 patterns x 2 platforms x 6 components x 4 fault types |
| `results/manifest.json` | Reproducibility statement (seed, config hash, n, git rev, timestamp) | same run | `agentorch.study.run_study` |

## Tables (figures/, regenerated; gitignored)

| Output | Paper element | Generating command | Source CSV |
|---|---|---|---|
| `figures/table3.csv` | **Table 5 (revised manuscript)** — executed-study results: per (pattern, platform, scenario) n, p50/p95/p99 (ms) with 95% BCa CIs, error rate, throughput (rps), cost/request | `python3 -m agentorch.study.make_table3 --results results/ --out figures/table3.csv` | `results/latency.csv`, `results/cost.csv` |
| `figures/fit_matrix.csv` | **Table 6 (revised manuscript)** — fit-for-purpose matrix: ONE platform-independent Weak/Moderate/Strong grade per (pattern, scenario), 21 cells, computed under the pre-registered rule of `docs/FIT_RULE.md` (Holm/MWU standings on the scenario's stressed property, both-platform pooling, capability gate); discrepancies vs the published cells recorded in `docs/FIT_DISCREPANCIES.md` | `python3 -m agentorch.study.make_fit_matrix --results results/ --out figures/fit_matrix.csv` | `results/latency.csv`, `results/cost.csv` + pattern capability metadata |
| `figures/table4_supplementary.csv` | **Supplementary** (referenced from the Table 6 discussion; NOT the fit-for-purpose matrix) — richer per-platform quality view: A/B/C Holm-equivalence-group grades on tail latency (p99 region), failure-under-fault, and cost/request, plus a metadata-derived oversight column, per `make_table4.py` and `docs/GRADES.md` | `python3 -m agentorch.study.make_table4 --results results/ --out figures/table4_supplementary.csv` | `results/latency.csv`, `results/cost.csv` (fault-mode rows of latency.csv drive reliability) |

## Figures (figures/, regenerated; gitignored)

| Output | Paper element | Generating command | Source CSV |
|---|---|---|---|
| `figures/ccdf.png` | **Fig. CCDF** — per-pattern latency CCDF (log-log), one panel per platform, scenario S1 | `python3 -m agentorch.study.figures_latency --results results/ --out figures/` | `results/latency.csv` (baseline rows) |
| `figures/p99_ci.png` | **Fig. p99** — p99 latency with 95% BCa error bars, panels per scenario, grouped by platform | same command (writes both PNGs) | `results/latency.csv` (baseline rows) |
| `figures/cost_per_1k.png` | **Fig. cost** — cost units per 1k requests per (pattern, platform), log scale, under `configs/costs.yaml` assumptions | `python3 -m agentorch.study.figures_cost --results results/ --out figures/` | `results/cost.csv` |
| `figures/cost_ledger.csv` | Cost appendix / scenario-resolved ledger (42 rows: pattern x platform x scenario, USD per request under `configs/costs.yaml` dated assumptions) backing Fig. cost, Table 5's cost column, and the S2>S1 / P1>P2 relative-cost claims (task 105) | same command (writes both outputs) | `results/cost.csv` via `agentorch.rig.costcapture.aggregate_ledger(by_scenario=True)` |
| `figures/fault_matrix.png` | **Fig. fault matrix** — pattern x (component, fault) grid: absorbed / isolated / propagated / not exercised, one panel per platform | `python3 -m agentorch.study.figures_fault --results results/ --out figures/` | `results/faults.csv` |
| `figures/decision_tree.png` | **Fig. 2** — pattern-selection decision tree over the paper's decision dimensions; leaf labels come from `REGISTRY[...].meta()` (catalog-consistent by construction) | `python3 -m agentorch.study.decision_tree --out figures/` | Pattern catalog metadata (`agentorch.patterns.registry`), no measurement data |

## Statistical methods backing the numbers

| Method | Implementation | Used by |
|---|---|---|
| Percentiles | `agentorch.stats.percentiles.percentiles` | Table 5, latency figures |
| 95% BCa bootstrap CIs | `agentorch.stats.bootstrap.bca_ci` (scipy `method='BCa'`) | Table 5, `p99_ci.png` |
| Mann-Whitney U + rank-biserial + Hodges-Lehmann | `agentorch.stats.compare.compare` | supplementary-table latency grades + fit-matrix standings |
| Holm correction over the 21-pair family per condition | `agentorch.stats.correction.holm` / `enumerate_family` | supplementary-table latency grades + fit-matrix standings |
| Pre-committed analysis plan | `docs/STATISTICAL_ANALYSIS_PLAN.md` | All of the above |

[HUMAN: verify each row against the manuscript draft before any figure
or table number is inserted; confirm no manuscript value bypasses this
mapping.]
