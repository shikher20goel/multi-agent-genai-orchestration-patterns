"""Task 008: latency model determinism and tail shape."""
import numpy as np

from agentorch.config import load_config
from agentorch.latency import LatencyModel
from agentorch.types import Platform


def test_same_seed_identical_samples() -> None:
    cfg = load_config()
    m1 = LatencyModel(cfg, cfg.get_rng("latency"))
    m2 = LatencyModel(cfg, cfg.get_rng("latency"))
    a = [m1.sample(Platform.BEDROCK, "model_invoke") for _ in range(50)]
    b = [m2.sample(Platform.BEDROCK, "model_invoke") for _ in range(50)]
    assert a == b


def test_p99_greater_than_p50() -> None:
    cfg = load_config()
    m = LatencyModel(cfg, cfg.get_rng("latency"))
    xs = np.array([m.sample(Platform.AGENTFORCE, "model_invoke") for _ in range(5000)])
    assert np.percentile(xs, 99) > np.percentile(xs, 50)
    assert np.all(xs > 0)


def test_unknown_service_raises() -> None:
    cfg = load_config()
    m = LatencyModel(cfg, cfg.get_rng("latency"))
    try:
        m.sample(Platform.BEDROCK, "nonexistent")
        raise AssertionError("expected KeyError")
    except KeyError:
        pass


def test_string_platform_accepted() -> None:
    cfg = load_config()
    m = LatencyModel(cfg, cfg.get_rng("latency"))
    assert m.sample("bedrock", "tool") > 0
