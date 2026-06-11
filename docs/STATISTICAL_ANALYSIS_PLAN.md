# Statistical Analysis Plan (SAP) — pre-committed

**Study:** Executed measurement study for *"A Pattern Catalog for Multi-Agent
Generative AI Orchestration Across Enterprise CRM and Hyperscaler Cloud
Platforms"* (IEEE Access submission).
**Status:** Pre-committed before inspection of full-study results. Any
deviation must be documented in `progress.txt` and in the manuscript.
**Gate:** HUMAN review required (task 035).

## 1. Design

Full-factorial baseline grid: 7 orchestration patterns (P1–P7, see
`agentorch.types.PatternId`) x 2 platforms (`bedrock`, `agentforce`) x 3
workload scenarios (S1 RAG QA, S2 long-horizon doc-gen, S3 bursty incident
triage) = **42 baseline conditions**, plus a fault-injection campaign
(Algorithm 2) and per-request cost capture. All execution is against local
deterministic platform mocks on a virtual clock; the rig is open-loop
(coordinated-omission correct): `submit_ts` comes from the pre-drawn Poisson
arrival schedule, never from completions
(`agentorch.rig.loadgen.run_open_loop`).

Per-condition sample size `n` is set in `configs/default.yaml`
(`study.n_items` for the full study, `study.smoke_n_items` for smoke runs)
and recorded in `results/manifest.json`.

## 2. Endpoints

**Primary endpoints** (per condition, computed from `results/latency.csv`):

1. End-to-end latency percentiles **p50, p95, p99** (ms), computed with
   `agentorch.stats.percentiles.percentiles` (linear-interpolation
   quantile estimator).

**Secondary endpoints:**

2. **Error rate** = 1 − (successful requests / all requests) per condition
   (from the `success` column of `results/latency.csv`).
3. **Cost per request** (cost units, USD under the HUMAN-gated assumptions
   in `configs/costs.yaml`), from `results/cost.csv` via
   `agentorch.rig.costcapture.aggregate_ledger`.
4. **Throughput** (completed requests / measurement window, rps) and
   Little's-law utilization (`agentorch.rig.saturation.headroom`).
5. **Fault containment** per (component, fault type) cell, classified by
   `agentorch.rig.faultcampaign.classify_cell` (contained iff zero failures
   among non-traversing requests and their success rate ≥
   `faults.containment_threshold` = 0.95 from `configs/default.yaml`).

## 3. Confidence intervals

All reported percentile and mean-cost point estimates carry **95% BCa
bootstrap confidence intervals** (bias-corrected and accelerated; Efron
1987), computed by `agentorch.stats.bootstrap.bca_ci`, a seeded wrapper over
`scipy.stats.bootstrap(method='BCa')`. Resample count: `stats.n_resamples`
= 2000 from `configs/default.yaml`. Confidence level: 1 − alpha with
**alpha = `stats.alpha` = 0.05** from `configs/default.yaml`.

## 4. Hypothesis tests

Pairwise pattern contrasts use the **two-sided Mann–Whitney U test**
(`agentorch.stats.compare.compare`, backed by `scipy.stats.mannwhitneyu`),
chosen because latency distributions are right-skewed and rank-based tests
do not assume normality. Each comparison reports:

- the U statistic and two-sided p-value;
- the **rank-biserial correlation** r = 2U/(n1·n2) − 1 as the effect size;
- the **Hodges–Lehmann estimator** (median of pairwise differences) as the
  robust shift estimate (`agentorch.stats.compare.hodges_lehmann_shift`).

A contrast is reported as *practically meaningful* only when it is
statistically significant after correction (Section 5) **and**
|rank-biserial| ≥ 0.30 (pre-committed effect-size floor).

## 5. Multiplicity

**Family definition (pre-committed):** within one (platform, scenario)
condition and one endpoint, the family is the **C(7,2) = 21 pairwise
comparisons among the seven patterns**, enumerated by
`agentorch.stats.correction.enumerate_family`. Each family is corrected
independently with the **Holm step-down procedure**
(`agentorch.stats.correction.holm`, backed by
`statsmodels.stats.multitest.multipletests(method='holm')`), controlling
the familywise error rate at alpha = `stats.alpha` = 0.05. Cross-platform
contrasts of the same pattern (7 per scenario) form a separate family,
also Holm-corrected.

## 6. Exclusion rules

Pre-committed; applied identically to all conditions:

1. **No warm-up exclusion**: the virtual-clock rig has no JIT/cache warm-up
   transient; all `n` requests per condition are analyzed.
2. Latency endpoints include **failed requests** (timeouts carry their full
   `faults.timeout_s` = 30 s service time) — excluding failures would bias
   latency downward exactly where patterns differ. Error rate is reported
   alongside so failure-masking is visible.
3. Fault-mode records (`mode = "fault"`) are **excluded from baseline
   latency/cost endpoints**; they feed only the containment analysis.
4. No outlier removal of any kind.
5. A condition is reported only if all `n` scheduled requests produced a
   record (the rig emits exactly one `LatencyRecord` per scheduled item by
   construction; a shortfall would indicate a rig bug and void the run).

## 7. Seed policy

A single master seed (`seed: 42` in `configs/default.yaml`) drives every
random stream. Child streams are derived deterministically as
SHA-256(master seed, stream name) via `agentorch.config.Config.get_rng`,
so arrival schedules, service-time draws, fault firings, scenario
generation, and bootstrap resampling are independent, reproducible
streams.

**Independence across conditions (Option A; Phase 2 task 103).** Each
(pattern, platform, scenario, mode) condition derives its OWN child
streams: the stream names embed the full condition string (e.g.
`loadgen:P2:bedrock:S2:baseline:latency`), so latency draws, fault
firings, arrivals, and scenario items are statistically independent
across conditions. No common-random-numbers coupling is used; the
between-condition independence assumption of the Mann–Whitney U tests
(Section 4) therefore holds by construction. The master seed, config hash, n, git revision, and timestamp are
recorded in `results/manifest.json` by `agentorch.study.run_study`.
Re-running with the same seed must reproduce every CSV bit-for-bit
(timestamp and git fields aside).

## 8. Reporting

- Table 3 (`figures/table3.csv`): per condition — n, p50/p95/p99 with BCa
  CIs, error rate, throughput, cost per request.
- Supplementary per-platform grades (`figures/table4_supplementary.csv`; the
  platform-independent fit matrix is `figures/fit_matrix.csv`,
  docs/FIT_RULE.md): grades derived from the
  endpoints by the explicit rules documented in
  `src/agentorch/study/make_table4.py`.
- Figures: CCDF and p99-with-CI latency plots, cost per 1k requests,
  fault-containment matrix — all generated exclusively from `results/`.
- Every manuscript number must trace to `results/`; no value may be typed
  in by hand.
