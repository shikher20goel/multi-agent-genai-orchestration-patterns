"""Shared fixtures (task 061): one session-scoped smoke study.

Five test modules previously each ran their own smoke study; the study
is deterministic (seeded), so a single shared, read-only results
directory is equivalent and cuts suite wall time substantially.
"""
from __future__ import annotations

import pytest

from agentorch.config import load_config
from agentorch.study.run_study import run_study


@pytest.fixture(scope="session")
def smoke_results(tmp_path_factory):
    out = tmp_path_factory.mktemp("smoke_results_shared")
    run_study(load_config(), out, smoke=True)
    return out
