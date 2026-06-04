"""Task 004: deterministic config and seed system."""
import numpy as np

from agentorch.config import Config, load_config


def test_load_default_config() -> None:
    cfg = load_config()
    assert isinstance(cfg.seed, int)
    assert "latency" in cfg


def test_attribute_access_nested() -> None:
    cfg = load_config()
    # Task 101 recalibration: a model step's p50 is ~1.1 s (mu ~ 0.1).
    assert -1.0 < cfg.latency.bedrock.model_invoke.mu < 1.0


def test_same_seed_identical_draws() -> None:
    cfg1 = Config({"seed": 123})
    cfg2 = Config({"seed": 123})
    a = cfg1.get_rng("stream").random(10)
    b = cfg2.get_rng("stream").random(10)
    assert np.array_equal(a, b)


def test_different_streams_independent() -> None:
    cfg = Config({"seed": 123})
    a = cfg.get_rng("alpha").random(10)
    b = cfg.get_rng("beta").random(10)
    assert not np.array_equal(a, b)


def test_different_seed_different_draws() -> None:
    a = Config({"seed": 1}).get_rng("s").random(10)
    b = Config({"seed": 2}).get_rng("s").random(10)
    assert not np.array_equal(a, b)
