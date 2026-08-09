# Fit-matrix discrepancies vs the paper's Table 4 (Phase 3 task 202) [HUMAN]

`figures/fit_matrix.csv` was computed from the pre-registered rule of
`docs/FIT_RULE.md` against the full study results (n = 500/condition,
seed 42, results/). 10 of the 21 published cells reproduce; the 11
below do not. Per the integrity rule, the computed grades stand
unmodified in fit_matrix.csv; nothing here was reverse-engineered or
forced. Every cell is flagged **[HUMAN]** for author review. Measured
numbers below trace to results/latency.csv (baseline rows) and
results/cost.csv; standings per endpoint are auditable in
figures/fit_matrix.csv.

Reading guide: standings are TOP / MID / BOTTOM Holm-equivalence-group
positions (docs/FIT_RULE.md); "inflation" = p99(S3)/p99(S1) per
pattern/platform; "growth" = median S2 latency / median S1 latency and
mean S2 cost / mean S1 cost.

## Agreed cells (10)

P1-S3, P2-S3, P3-S2, P3-S3, P4-S1, P4-S2, P4-S3, P5-S2, P6-S2, P6-S3
(pinned in tests/fixtures/fit_agreed_cells.json by task 203).

## Discrepant cells (11) [HUMAN]

| # | Cell | Paper | Computed | Measured rationale | Honest read |
|---|------|-------|----------|--------------------|-------------|
| 1 | P1-S1 | Moderate | **Weak** | P1's S1 per-request latency (median 5,880 ms AF / 4,545 ms BR) and cost ($2.80 AF / $0.0281 BR — 5 model invocations per request) are BOTTOM on both platforms on both endpoints: plan + 3-collaborator fan-out + synthesis is the most expensive single-step topology in the rig. | **Evidence-based refinement candidate.** The paper says "Moderate — planning overhead per request"; the executed rig quantifies that overhead as worst-group on BOTH throughput proxy and cost. The direction matches the paper's own rationale; only the severity differs. Calibration sensitivity: the 5-invocation fan-out width (configs) drives the cost standing. |
| 2 | P1-S2 | Strong | **Moderate** | Measured S2 growth standing is BOTTOM-lat/MID-cost on both platforms (latency growth 1.59x AF / 1.47x BR, dominated because the supervisor re-pays the fan-out each step); the adaptive_decomposition capability upgrade lifts Weak -> Moderate, not to Strong. | **Calibration issue (partly) + rule-composition choice.** The paper's Strong is a structural claim ("adaptive decomposition fits"); the rig's S2 makes every pattern execute the same fixed step list, so adaptivity has no measurable payoff — the mock cannot express the benefit being graded. The upgrade-only gate (pre-registered) then cannot reach Strong from a BOTTOM measured standing. |
| 3 | P2-S1 | Weak | **Strong** | P2 is TOP on both endpoints on both platforms: single-stage S1 median 1,607 ms AF / 1,260 ms BR (fastest) and cheapest cost group ($0.60 AF / $0.0056 BR). | **Calibration issue.** The paper's "additive latency hurts throughput" presumes a multi-stage chain even in S1; the rig's S1 collapses P2 to ONE stage, making it trivially the leanest topology. Whether S1 should drive P2 through >1 stage is an author-level scenario-spec decision. |
| 4 | P2-S2 | Strong | **Weak** | P2's S2 growth is the worst of all patterns by far: median latency growth 6.7x AF / 6.6x BR and cost growth 6.1x both platforms (BOTTOM everywhere) — additive stages dominate growth. | **Rule-vs-paper construct mismatch (calibration issue).** The paper grades S2 fit on ORDER-MATCH ("fixed order matches the task") and completion, not on latency/cost growth; the rig's pre-registered S2 property is growth over stages, on which an additive chain is necessarily worst. The Phase-2 agreement suite separately corroborates the paper's completion claim (P1/P2 best S2 success). Both constructs are defensible; they measure different things. |
| 5 | P3-S1 | Moderate | **Weak** | P3 is BOTTOM on both endpoints both platforms: S1 median 4,243 ms AF / 3,519 ms BR (bus hop per event + handler chain) and cost $1.60 AF / $0.0167 BR (one model call per event hop). | **Evidence-based refinement candidate.** The paper's Moderate rests on "weak per-request trace" (an observability argument, unmeasured here); the rig measures the per-hop latency/cost price of choreography in a single-step workload as worst-group. The grade dimension differs from the paper's rationale dimension. |
| 6 | P5-S1 | Strong | **Moderate** | P5 is MID on both endpoints both platforms: median 2,069 ms AF / 1,818 ms BR and cost $0.80 AF / $0.0056 BR — fast and cheap, but significantly dominated by P2's single-step path, so not in the TOP equivalence group. | **Calibration issue.** The paper's Strong rests on "attributable cost, parallel dispatch"; the rig's S1 dispatches tools sequentially per request and cost attribution is not a graded endpoint, so the gateway's two advantages are invisible to the pre-registered property. |
| 7 | P5-S3 | Strong | **Weak** | P5's p99 inflation under burst is 3.35x AF / 4.25x BR — BOTTOM group on both platforms (only P2 is comparable); the mocked gateway has no arrival buffer, so bursts queue at the gateway hop. | **Calibration issue.** The paper's Strong is a FAULT-containment claim ("bulkheads contain faults") — corroborated separately by the fault campaign (P5 tool outage ISOLATED) — not a latency-inflation claim. The pre-registered S3 property (p99 inflation) penalizes the extra hop under burst; the bulkhead benefit lives on a different axis than the one S3 stresses in the rig. |
| 8 | P6-S1 | Weak | **Moderate** | P6 is MID on both endpoints both platforms: median 1,998 ms AF / 1,628 ms BR (the human delay hits only the adjudicated fraction; the rest is a short machine path) and near-cheapest cost. | **Calibration issue.** The paper's Weak says "human step throttles throughput"; the rig's load generator is OPEN-LOOP and the human decision is modeled non-blocking, so the human step inflates the tail (p99 ~62 s, graded C in the supplementary table) without throttling sustained throughput. A closed-loop or capacity-limited human queue would likely reproduce Weak. |
| 9 | P7-S1 | Strong | **Moderate** | P7 is MID-lat / TOP-cost on both platforms (median 3,073 ms AF / 3,196 ms BR — the cross-platform RTT keeps it out of the fastest group; cost $0.60 AF / $0.0056 BR is top group); the pessimistic composite takes the latency MID. | **Calibration issue.** The paper's Strong is conditional — "when data and model split platforms"; the rig's S1 charges every P7 request the bridge RTT but models no penalty for the OTHER patterns' lack of cross-platform reach, so the conditional benefit cannot appear. |
| 10 | P7-S2 | Moderate | **Weak** | P7's S2 cost growth is BOTTOM on both platforms (5.94x BR / 1.83x-but-dominated AF; token volume scales with steps AND each step pays the bridge) and AF latency growth MID / BR TOP -> pessimistic composite BOTTOM on both. | **Mixed.** The paper itself says "cross-platform hop per step" — the measured per-step cost amplification is that exact mechanism, measured as worst-group. Whether that severity merits Weak rather than Moderate is a threshold question (BOTTOM = dominated by >= 4 of 6). |
| 11 | P7-S3 | Strong | **Weak** | P7's p99 inflation under burst is 2.44x AF / 2.18x BR — BOTTOM group on both platforms; the bridge hop queues under burst, and P7 holds neither S3 gate capability. | **Calibration issue.** The paper's Strong is "platform-outage containment" — a fault-isolation claim confirmed separately by the campaign (P7 remote-cluster outage ISOLATED) — not a burst-latency claim. As with P5-S3, the rig's pre-registered S3 property stresses an axis orthogonal to the paper's rationale. |

## Summary for the author [HUMAN]

- **3 cells** (P1-S1, P3-S1, P7-S2) read as plausible *evidence-based
  refinements*: the measured direction matches the paper's own
  stated rationale, only more severely.
- **8 cells** read primarily as *calibration/construct issues*: the
  rig's pre-registered stressed property (latency/cost growth, p99
  inflation) does not capture the axis the paper's cell rationale
  actually names (order-match/completion for P2-S2, fault containment
  for P5-S3/P7-S3, conditional cross-platform reach for P7-S1,
  parallel dispatch + cost attributability for P5-S1, closed-loop
  human throttling for P6-S1, adaptive-decomposition payoff for
  P1-S2, multi-stage S1 chain for P2-S1).
- No rule, threshold, pooling, or endpoint was modified after the
  first computation (docs/FIT_RULE.md Changelog has no
  post-computation entries). All 11 computed grades stand as computed
  in figures/fit_matrix.csv pending author review.
