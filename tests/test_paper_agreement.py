"""Paper-agreement gate (PHASE2_SPEC §PRIMARY DELIVERABLE).

Encodes the directional claims of the paper's Table 3 (synoptic
comparison / structural consequences) and Table 4 (fit-for-purpose
matrix) and asserts that EXECUTED results satisfy them. A module-scoped
fixture regenerates a reduced-but-adequate study (n=300 per baseline
condition, fixed master seed from configs/default.yaml) through the
exact production path (`agentorch.study.run_study.run_study`), so every
asserted number traces to the same rig that produces `results/`.

The six claims asserted (verbatim from PHASE2_SPEC.md):

1. P2 Sequential Pipeline p99 in S2 (multi-step) > P2 p99 in S1
   (additive over stages).
2. P6 HITL end-to-end latency is the HIGHEST of all patterns /
   human-step-dominated, not the lowest.
3. P3 Event-Driven Choreography degrades LEAST under S3 bursty load
   relative to P1/P2 (burst absorption: p99 inflation S3 vs S1).
4. Fault campaign shows PROPAGATION for P2 (stage fault blocks
   downstream) and SPOF behaviour for P1 (supervisor outage) and P4
   (blackboard/memory-store outage); CONTAINMENT (isolated/absorbed)
   for P3, P5 (bulkhead/timeout), P7 (platform outage contained to one
   cluster).
5. Fault campaign exercises human_queue faults for P6 and shows
   correctness isolation.
6. Per-condition results DIFFER across S1/S2/S3 (no identical values
   across scenarios for the same pattern/platform).

Plus the task-102 guard: every baseline condition runs below
saturation (offered utilization < 1) with bounded queue growth.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from agentorch.config import load_config
from agentorch.study.run_study import run_study

N_PER_CONDITION = 300  # reduced-but-adequate study size for the gate
PATTERNS = [f"P{i}" for i in range(1, 8)]
PLATFORMS = ["agentforce", "bedrock"]
SCENARIOS = ["S1", "S2", "S3"]


@pytest.fixture(scope="module")
def study(tmp_path_factory):
    """Regenerate results at n=300/condition with the committed seed."""
    out = tmp_path_factory.mktemp("paper_agreement_results")
    cfg = load_config()
    cfg.to_dict()["study"]["n_items"] = N_PER_CONDITION
    manifest = run_study(cfg, out, smoke=False)
    lat = pd.read_csv(out / "latency.csv")
    faults = pd.read_csv(out / "faults.csv")
    base = lat[lat["mode"] == "baseline"]
    return {"base": base, "faults": faults, "manifest": manifest, "cfg": cfg,
            "out_dir": out}


def _p(base: pd.DataFrame, pattern: str, platform: str, scenario: str,
       q: float) -> float:
    sel = base[(base["pattern"] == pattern) & (base["platform"] == platform)
               & (base["scenario"] == scenario)]["latency_ms"]
    assert len(sel) == N_PER_CONDITION, (pattern, platform, scenario, len(sel))
    return float(np.percentile(sel.to_numpy(dtype=float), q))


# ---------------------------------------------------------------- claim 1
def test_claim1_pipeline_p99_additive_over_stages(study) -> None:
    """P2 p99 in S2 (4-8 stages) exceeds P2 p99 in S1 (single stage)."""
    base = study["base"]
    for platform in PLATFORMS:
        p99_s1 = _p(base, "P2", platform, "S1", 99)
        p99_s2 = _p(base, "P2", platform, "S2", 99)
        assert p99_s2 > p99_s1, (
            f"P2/{platform}: S2 p99 {p99_s2:.0f} ms must exceed "
            f"S1 p99 {p99_s1:.0f} ms (additive over stages)")
        # Additive structure: the multi-step gap is substantial, not noise.
        assert p99_s2 > 1.5 * p99_s1, (platform, p99_s1, p99_s2)


# ---------------------------------------------------------------- claim 2
def test_claim2_hitl_latency_highest_and_human_dominated(study) -> None:
    """P6's end-to-end p99 is the highest of all patterns in every
    (platform, scenario) condition, and its magnitude is set by the
    configured human decision delay (tens of seconds), not machine time."""
    base = study["base"]
    cfg = study["cfg"]
    hd = cfg.latency.shared.human_decision_delay
    human_p50_ms = float(np.exp(hd["mu"])) * 1000.0
    for platform in PLATFORMS:
        for scenario in SCENARIOS:
            p99_p6 = _p(base, "P6", platform, scenario, 99)
            for pattern in PATTERNS:
                if pattern == "P6":
                    continue
                p99_other = _p(base, pattern, platform, scenario, 99)
                assert p99_p6 > p99_other, (
                    f"P6 p99 {p99_p6:.0f} ms must exceed {pattern} "
                    f"p99 {p99_other:.0f} ms in {platform}/{scenario}")
            # Human-step-dominated: the tail is at least the human
            # decision median (tens of seconds per config).
            assert p99_p6 >= human_p50_ms, (platform, scenario, p99_p6)


# ---------------------------------------------------------------- claim 3
def test_claim3_choreography_absorbs_bursts_best(study) -> None:
    """P3's p99 inflation under bursty S3 (vs its own S1 baseline) is
    the smallest among {P1, P2, P3}: the bus absorbs bursts that a
    supervisor or a fixed chain must queue."""
    base = study["base"]
    for platform in PLATFORMS:
        inflation = {}
        for pattern in ("P1", "P2", "P3"):
            p99_s1 = _p(base, pattern, platform, "S1", 99)
            p99_s3 = _p(base, pattern, platform, "S3", 99)
            inflation[pattern] = p99_s3 / p99_s1
        assert inflation["P3"] < inflation["P1"], (platform, inflation)
        assert inflation["P3"] < inflation["P2"], (platform, inflation)


# ---------------------------------------------------------------- claim 4
def _cls(faults: pd.DataFrame, pattern: str, platform: str, component: str,
         fault: str) -> str:
    row = faults[(faults["pattern"] == pattern)
                 & (faults["platform"] == platform)
                 & (faults["component"] == component)
                 & (faults["fault"] == fault)]
    assert len(row) == 1, (pattern, platform, component, fault, len(row))
    return str(row.iloc[0]["classification"])


def test_claim4_fault_matrix_matches_table3_consequences(study) -> None:
    """Propagation for P1 (supervisor outage = SPOF), P2 (stage fault
    blocks downstream), P4 (store outage = SPOF); containment
    (isolated/absorbed) for P3 (buffered redelivery), P5 (bulkhead),
    P7 (remote-cluster outage contained to bridged work)."""
    faults = study["faults"]
    contained = {"isolated", "absorbed"}
    for platform in PLATFORMS:
        # SPOF / propagation rows.
        assert _cls(faults, "P1", platform, "model_backend",
                    "outage") == "propagated", f"P1 supervisor SPOF {platform}"
        assert _cls(faults, "P2", platform, "model_backend",
                    "outage") == "propagated", f"P2 stage fault {platform}"
        assert _cls(faults, "P4", platform, "memory_store",
                    "outage") == "propagated", f"P4 store SPOF {platform}"
        # Containment rows.
        assert _cls(faults, "P3", platform, "event_bus",
                    "outage") == "absorbed", f"P3 bus redelivery {platform}"
        assert _cls(faults, "P5", platform, "tool",
                    "outage") in contained, f"P5 bulkhead {platform}"
        assert _cls(faults, "P5", platform, "tool",
                    "timeout") in contained, f"P5 tool timeout {platform}"
        # P7: the remote-cluster outage cell (model_backend with the
        # campaign's unit="remote") degrades only the bridged work.
        assert _cls(faults, "P7", platform, "model_backend",
                    "outage") == "isolated", f"P7 cluster containment {platform}"

    # The matrix is a MIX, as Table 3's consequences require.
    classes = set(faults["classification"].unique())
    assert {"propagated", "isolated", "absorbed"} <= classes


def test_claim4_faults_degrade_affected_conditions(study) -> None:
    """Every exercised fault cell visibly degrades its condition:
    error rate up (traversing success < 1), latency up vs baseline, or
    output degraded (a bulkhead-isolated unit's work lost)."""
    faults = study["faults"]
    exercised = faults[(faults["classification"] != "not_exercised")
                       & (faults["n_traversing"] > 0)]
    assert len(exercised) > 0
    for _, row in exercised.iterrows():
        degraded = (row["traversing_success_rate"] < 1.0
                    or row["fault_mean_latency_s"]
                    > row["baseline_mean_latency_s"]
                    or row["traversing_degraded_rate"] > 0.0)
        assert degraded, (row["pattern"], row["platform"],
                          row["component"], row["fault"])


# ---------------------------------------------------------------- claim 5
def test_claim5_hitl_human_queue_correctness_isolation(study) -> None:
    """human_queue faults are exercised for P6 and show correctness
    isolation: decisions are deferred/queued (latency up), never
    wrongly auto-approved (success and integrity preserved)."""
    faults = study["faults"]
    for platform in PLATFORMS:
        cells = faults[(faults["pattern"] == "P6")
                       & (faults["platform"] == platform)
                       & (faults["component"] == "human_queue")]
        exercised = cells[cells["n_traversing"] > 0]
        assert len(exercised) > 0, f"P6 human_queue not exercised on {platform}"
        for _, row in exercised.iterrows():
            # Integrity preserved: deferred decisions still succeed...
            assert row["traversing_success_rate"] >= 0.95, row["fault"]
            assert row["classification"] in ("absorbed", "isolated"), row["fault"]
            # ...at the price of latency (deferral), not correctness.
            assert (row["fault_mean_latency_s"]
                    > row["baseline_mean_latency_s"]), row["fault"]


# ---------------------------------------------------------------- claim 6
def test_claim6_conditions_differ_across_scenarios(study) -> None:
    """Independent per-condition streams (task 103): no pattern/platform
    repeats identical latency values across scenarios."""
    base = study["base"]
    for platform in PLATFORMS:
        for pattern in PATTERNS:
            p50s = [_p(base, pattern, platform, s, 50) for s in SCENARIOS]
            p99s = [_p(base, pattern, platform, s, 99) for s in SCENARIOS]
            assert len(set(p50s)) == 3, (pattern, platform, p50s)
            assert len(set(p99s)) == 3, (pattern, platform, p99s)


# ------------------------------------------------------- task 102 guard
def test_load_below_saturation_and_bounded_queues(study) -> None:
    """Task 102: every baseline condition is driven below its measured
    single-replica saturation (utilization < 1) and queue growth stays
    bounded — p99 is not an unbounded-queue artifact."""
    manifest = study["manifest"]
    conds = manifest["conditions"]
    assert len(conds) == 42
    for key, c in conds.items():
        assert c["offered_utilization"] < 1.0, (key, c)
        assert c["offered_rate_rps"] < c["saturation_rate_rps"], key
        # Bounded queue: max depth stays far below the condition size.
        assert c["max_queue_depth"] < N_PER_CONDITION / 4, (key, c)


def test_manifest_records_saturation_check(study, tmp_path) -> None:
    """The per-condition saturation rate and chosen arrival rate are
    recorded in results/manifest.json (task 102)."""
    m = study["manifest"]
    assert "utilization_target" in m
    sample = m["conditions"]["P1:bedrock:S1"]
    for field in ("mean_service_s", "saturation_rate_rps",
                  "offered_rate_rps", "offered_utilization"):
        assert field in sample
    # Round-trips through JSON.
    assert json.loads(json.dumps(m))["conditions"]


# ----------------------------------------------- calibration sanity rails
def test_latency_magnitudes_are_realistic(study) -> None:
    """Task 101 rails: machine-path baselines never reach the old
    60-190 s artifact range; HITL is tens of seconds via the human
    delay, bounded well under 190 s."""
    base = study["base"]
    for platform in PLATFORMS:
        for scenario in SCENARIOS:
            for pattern in PATTERNS:
                p99 = _p(base, pattern, platform, scenario, 99)
                if pattern == "P6":
                    assert p99 < 190_000, (pattern, platform, scenario, p99)
                else:
                    assert p99 < 60_000, (pattern, platform, scenario, p99)


# ----------------------------------------------- Table 4 (task 106)
@pytest.fixture(scope="module")
def table4(study):
    """Table 4 computed from the same regenerated study results."""
    from agentorch.study.make_table4 import build_table4
    return build_table4(study["out_dir"], cfg=study["cfg"])


def _grade(t4, pattern: str, platform: str, scenario: str, col: str) -> str:
    row = t4[(t4["pattern"] == pattern) & (t4["platform"] == platform)
             & (t4["scenario"] == scenario)]
    assert len(row) == 1
    return str(row.iloc[0][col])


def test_table4_s3_choreography_beats_pipeline(table4) -> None:
    """Paper Table 4: under bursty S3, P3 (event-driven choreography) is
    graded strictly better than P2 (fixed chain) on the latency
    endpoint, on both platforms."""
    from agentorch.study.make_table4 import GRADE_ORDER
    for platform in PLATFORMS:
        g3 = _grade(table4, "P3", platform, "S3", "latency_grade")
        g2 = _grade(table4, "P2", platform, "S3", "latency_grade")
        assert GRADE_ORDER[g3] < GRADE_ORDER[g2], (platform, g3, g2)


def test_table4_s2_orchestrators_strong_on_completion(study) -> None:
    """Paper Table 4: P1 and P2 are strong for the long-horizon S2
    scenario on the completion endpoint — their baseline S2 success rate
    equals the condition's best, and they natively process EVERY
    scenario step (the paper's S2 fitness is a completion/structural
    claim, not a raw-speed claim)."""
    base = study["base"]
    for platform in PLATFORMS:
        cond = base[(base["platform"] == platform) & (base["scenario"] == "S2")]
        rates = cond.groupby("pattern")["success"].mean()
        best = rates.max()
        assert rates["P1"] == best, (platform, rates.to_dict())
        assert rates["P2"] == best, (platform, rates.to_dict())


def test_table4_hitl_latency_weak_oversight_strong(table4) -> None:
    """Paper Table 4: P6 is in the WORST latency group (grade C,
    human-decision-dominated tail) in every condition, yet is the only
    pattern graded A on the metadata-derived oversight axis."""
    for platform in PLATFORMS:
        for scenario in SCENARIOS:
            assert _grade(table4, "P6", platform, scenario,
                          "latency_grade") == "C", (platform, scenario)
            assert _grade(table4, "P6", platform, scenario,
                          "oversight_grade") == "A", (platform, scenario)
    others = table4[table4["pattern"] != "P6"]
    assert (others["oversight_grade"] != "A").all()


# ------------------------------- Table 4 fit cells (Phase 3 task 203)
FIXTURE = (Path(__file__).parent / "fixtures" / "fit_agreed_cells.json")
AGREED_CELLS = json.loads(FIXTURE.read_text())


@pytest.fixture(scope="module")
def fit_matrix(study):
    """Fit matrix computed by the pre-registered rule (docs/FIT_RULE.md)
    from the same regenerated study results."""
    from agentorch.study.make_fit_matrix import build_fit_matrix
    return build_fit_matrix(study["out_dir"], cfg=study["cfg"])


def _fit_grade(fit, pattern: str, scenario: str) -> str:
    row = fit[(fit["pattern"] == pattern) & (fit["scenario"] == scenario)]
    assert len(row) == 1, (pattern, scenario)
    return str(row.iloc[0]["fit_grade"])


def test_fit_fixture_cells_match_published_table4() -> None:
    """The pinned agreed-cell fixture carries EXACTLY the paper's
    published grade for each cell it pins (guards fixture drift). The
    paper cells are published ground truth (PAPER_TABLE4); the
    fixture's membership came from the task-202 comparison."""
    from agentorch.study.make_fit_matrix import PAPER_TABLE4
    assert len(AGREED_CELLS) > 0
    for cell in AGREED_CELLS:
        key = (cell["pattern"], cell["scenario"])
        assert cell["grade"] == PAPER_TABLE4[key], cell


@pytest.mark.parametrize(
    "cell", AGREED_CELLS,
    ids=[f"{c['pattern']}-{c['scenario']}" for c in AGREED_CELLS])
def test_fit_matrix_reproduces_agreed_paper_cell(fit_matrix, cell) -> None:
    """Paper Table 4 agreement gate: for every cell where the
    pre-registered fit rule reproduced the paper (task 202), the
    regenerated fit matrix must keep reproducing it."""
    got = _fit_grade(fit_matrix, cell["pattern"], cell["scenario"])
    assert got == cell["grade"], (
        f"fit_matrix contradicts agreed paper cell "
        f"{cell['pattern']}/{cell['scenario']}: computed {got!r}, "
        f"paper {cell['grade']!r}")


def test_committed_fit_matrix_consistent_with_agreed_cells() -> None:
    """The committed figures/fit_matrix.csv (full n=500 run) must not
    contradict any pinned agreed cell either."""
    committed = Path(__file__).parent.parent / "figures" / "fit_matrix.csv"
    if not committed.is_file():  # fresh clone before run.sh
        pytest.skip("figures/fit_matrix.csv not generated yet")
    fit = pd.read_csv(committed)
    for cell in AGREED_CELLS:
        got = _fit_grade(fit, cell["pattern"], cell["scenario"])
        assert got == cell["grade"], cell
