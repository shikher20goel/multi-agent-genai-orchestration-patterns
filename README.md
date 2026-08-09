# AgentOrchPatterns — Reproducibility Package

Executable reproducibility package for the IEEE Access submission
*"A Pattern Catalog for Multi-Agent Generative AI Orchestration Across
Enterprise CRM and Hyperscaler Cloud Platforms"* (S. Goel). It turns
the paper's prospective evaluation rig into an **executed, open,
deterministic measurement study**: seven orchestration patterns
(P1 Supervisor … P7 Federated Bridge) run against locally **mocked**
Salesforce Agentforce 360 and Amazon Bedrock/AgentCore platform
clients, under three synthetic scenarios (S1 RAG QA, S2 long-horizon
document generation, S3 bursty incident triage), with an open-loop
load generator, a 336-cell fault-injection campaign, a cost model, and
a pre-committed statistics pipeline (BCa bootstrap CIs, Mann–Whitney U
with effect sizes, Holm correction).

No network access and no cloud credentials are needed or used: all
platform behavior is mocked locally and every run is seeded and
deterministic (same seed → identical output).

Repository: https://github.com/shikher20goel/multi-agent-genai-orchestration-patterns ·
Archived artifact DOI: minted at the tagged release (see the Releases page
and the badge below once the Zenodo deposit is live).

## Requirements

- Python ≥ 3.10 (developed on 3.10/3.11; no 3.11-only syntax).
- OS: Linux/macOS (any platform with a POSIX shell for `run.sh` /
  `demo.sh`; the Python package itself is cross-platform).
- Python packages (installed automatically in the Installation step):
  `numpy`, `scipy`, `statsmodels`, `pandas`, `matplotlib`, `simpy`,
  `pyyaml`; for development/testing: `pytest`, `pytest-cov`, `ruff`.
- Pinned versions: `environment/requirements.lock` (exact versions the
  results were produced with); a pinned `Dockerfile` is provided for a
  containerized environment (Docker optional).
- Hardware: any commodity machine. The full study completes in a few
  seconds of wall time (all timing is virtual-clock based; nothing
  sleeps). ~200 MB free disk.
- No GPU, no network, no cloud accounts.

## Installation

From the repository root:

```bash
python3 -m pip install -e ".[dev]"
```

or, to reproduce with the exact pinned environment:

```bash
python3 -m pip install -r environment/requirements.lock
python3 -m pip install -e . --no-deps
```

Optional containerized install (Docker):

```bash
docker build -t agentorch .
```

Verify the installation:

```bash
python3 -m pytest -q          # full test suite
```

## Usage

Single-command full reproduction (study → tables → figures):

```bash
bash run.sh
```

Quick end-to-end demo (< 40 s; smoke study + one figure + printed
summary table):

```bash
bash demo.sh
```

Individual steps:

```bash
python3 -m agentorch.study.run_study --out results/          # full study
python3 -m agentorch.study.run_study --smoke --out results/  # reduced smoke study
python3 -m agentorch.study.make_table3 --results results/ --out figures/table3.csv
python3 -m agentorch.study.make_table4 --results results/ --out figures/table4_supplementary.csv
python3 -m agentorch.study.make_fit_matrix --results results/ --out figures/fit_matrix.csv
python3 -m agentorch.study.figures_latency --results results/ --out figures/
python3 -m agentorch.study.figures_cost   --results results/ --out figures/
python3 -m agentorch.study.figures_fault  --results results/ --out figures/
python3 -m agentorch.study.decision_tree  --out figures/
python3 governance/hitl_example.py        # runnable HITL governance demo
```

All tunables (seed, latency parameters, fault campaign grid, scenario
shapes) live in `configs/default.yaml`; cost-model unit prices live in
`configs/costs.yaml`. Master seed: 42.

## Expected Output

After `bash run.sh` completes (exit code 0):

- `results/latency.csv` — one row per request across all 42 baseline
  conditions (7 patterns × 2 platforms × 3 scenarios, n = 500 each)
  plus fault-mode windows; `submit_ts` and `complete_ts` recorded
  separately (open-loop, coordinated-omission correct).
- `results/cost.csv` — per-request cost records (model invocations,
  tokens, service calls, cost units).
- `results/faults.csv` — one row per fault-campaign cell
  (336 = 7 patterns × 2 platforms × 6 components × 4 fault types) with
  contained/propagated classification.
- `results/manifest.json` — provenance: seed, config hash, n per
  condition, git revision, timestamp, wall time.
- `figures/table3.csv` — synoptic comparison (paper Table 5): p50/p95/
  p99 latency with 95% BCa CIs, error rate, throughput, cost/request.
- `figures/fit_matrix.csv` — fit-for-purpose matrix (paper Table 6): platform-independent Weak/Moderate/Strong per (pattern, scenario), pre-registered rule in `docs/FIT_RULE.md`.
- `figures/table4_supplementary.csv` — supplementary per-platform A/B/C quality grades (latency/reliability/cost/oversight); NOT the fit-for-purpose matrix.
- `figures/ccdf.png`, `figures/p99_ci.png` — latency figures.
- `figures/cost_per_1k.png`, `figures/cost_ledger.csv` — cost outputs.
- `figures/fault_matrix.png` — fault-isolation matrix.
- `figures/decision_tree.png` — pattern-selection decision tree.

Determinism check: rerunning `bash run.sh` with the same
`configs/default.yaml` reproduces identical CSV values (the manifest's
`config_hash` and `seed` pin the run). `scripts/verify_repro.py`
checks that the full output manifest is present.

Expected demo output (`bash demo.sh`): a smoke study in
`results_demo/`, one figure (`figures_demo/p99_ci.png`), and a printed
per-pattern summary table on stdout.

## License

Apache License 2.0 — see the `LICENSE` file. Copyright 2026 Shikher
Goel. (License choice pending final human confirmation; see
`progress.txt`.)

If you use this artifact, please cite the paper via `CITATION.cff`
(preferred-citation; the archived-artifact DOI is minted at the tagged
release and recorded there).

## Paper-table mapping (revised manuscript, Access-2026-28862)

| Revised-paper table | Artifact in this repository |
|---|---|
| Table 5 (executed-study results) | `figures/table3.csv` (regenerated by `run.sh`) |
| Table 6 (fit-for-purpose matrix, per-cell provenance) | `figures/fit_matrix.csv` + `docs/FIT_RULE.md`; the paper's provenance label "Reproduced" means the pre-registered rule's computed grade reproduces the published grade |
| Table 7 (supplementary quality view) | `figures/table4_supplementary.csv` + `docs/GRADES.md` |
| Table 8 (sensitivity sweep) | `figures/sensitivity_sweep.csv`, `figures/sensitivity_summary.json` via `scripts/sensitivity_sweep.py` + `configs/sweep/` |
| Table 9 (live-endpoint anchor) | `anchor/results/` via `anchor/run_anchor.py` |

Internal artifact filenames (`table3.csv`, `table4_supplementary.csv`) are historical and unchanged; the mapping above is authoritative.
