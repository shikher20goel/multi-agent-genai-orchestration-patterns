"""Tests for scripts/sensitivity_sweep.py (reviewer response, R2-4).

Quick-mode only: the full sweep is a release artifact, not a CI gate.
These tests assert the sweep machinery is sound -- overlays load and
change exactly one parameter, the comparison outputs are well-formed,
and reuse is hash-guarded -- without asserting any particular grade,
which is the sweep's *finding*, never its fixture.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from scripts.sensitivity_sweep import (
    VARIANTS, run_sweep, variant_config, variant_override)

BASE = variant_config("baseline").to_dict()


def test_variants_have_committed_overlays() -> None:
    for name in VARIANTS:
        override = variant_override(name)
        assert len(override) == 1, f"{name} must change exactly one parameter"


@pytest.mark.parametrize("name", VARIANTS)
def test_variant_config_changes_only_its_parameter(name: str) -> None:
    cfg = variant_config(name).to_dict()
    (dotted, value), = variant_override(name).items()
    keys = dotted.split(".")
    node = cfg
    for k in keys[:-1]:
        node = node[k]
    assert node[keys[-1]] == value
    def scrub(d: dict, path: list[str]) -> dict:
        d = json.loads(json.dumps(d))
        node = d
        for k in path[:-1]:
            node = node[k]
        node.pop(path[-1], None)
        return d
    assert scrub(cfg, keys) == scrub(BASE, keys)
    assert cfg["seed"] == BASE["seed"]


def test_quick_sweep_single_variant(tmp_path: Path) -> None:
    out_root = tmp_path / "results_sweep"
    figures = tmp_path / "figures"
    summary = run_sweep(out_root, figures, only="n250", quick=True)

    assert summary["quick"] is True
    assert list(summary["variants"]) == ["n250"]
    v = summary["variants"]["n250"]
    fit = v["fit_vs_baseline"]
    assert fit["cells_total"] == 21
    assert 0 <= fit["cells_agree"] <= 21
    assert fit["cells_agree"] + len(fit["moving_cells"]) == 21
    taus = v["kendall_tau_median_latency"]
    assert set(taus) == {"agentforce:S1", "agentforce:S2", "agentforce:S3",
                         "bedrock:S1", "bedrock:S2", "bedrock:S3", "mean"}
    assert all(-1.0 <= t <= 1.0 for t in taus.values())
    assert set(v["headline_contrasts"]) == {
        "pipeline_additive", "hitl_tail_dominant",
        "choreography_burst_absorption", "supervisor_costliest"}

    sweep_csv = pd.read_csv(figures / "sensitivity_sweep.csv")
    assert len(sweep_csv) == 42
    assert (figures / "sensitivity_summary.json").exists()
    assert (out_root / "baseline" / "fit_matrix.csv").exists()
    assert (out_root / "n250" / "fit_matrix.csv").exists()


def test_reuse_is_config_hash_guarded(tmp_path: Path) -> None:
    out_root = tmp_path / "results_sweep"
    figures = tmp_path / "figures"
    run_sweep(out_root, figures, only="baseline", quick=True)
    manifest = json.loads((out_root / "baseline" / "manifest.json").read_text())
    first_hash = manifest["config_hash"]
    run_sweep(out_root, figures, only="baseline", quick=True)
    manifest2 = json.loads((out_root / "baseline" / "manifest.json").read_text())
    assert manifest2["config_hash"] == first_hash
    assert manifest2["timestamp_utc"] == manifest["timestamp_utc"]
