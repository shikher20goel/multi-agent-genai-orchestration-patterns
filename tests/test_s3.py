"""Task 026: S3 bursty incident triage; burst factor configurable."""
import pytest

from agentorch.config import load_config
from agentorch.scenarios import generate
from agentorch.scenarios.s3_triage import generate_s3
from agentorch.types import ScenarioId


def test_s3_generates_with_default_burst_factor() -> None:
    cfg = load_config()
    items = generate(ScenarioId.S3, 100, cfg.get_rng("s3"), cfg)
    assert len(items) == 100
    burst = [i for i in items if i.payload["in_burst"]]
    calm = [i for i in items if not i.payload["in_burst"]]
    assert burst and calm
    assert all(i.payload["arrival_weight"] == cfg.scenarios.s3.burst_factor
               for i in burst)
    assert all(i.payload["arrival_weight"] == 1.0 for i in calm)


def test_s3_burst_factor_configurable() -> None:
    cfg = load_config()
    items = generate_s3(100, cfg.get_rng("s3"), cfg, burst_factor=12.0)
    burst_weights = {i.payload["arrival_weight"] for i in items
                     if i.payload["in_burst"]}
    assert burst_weights == {12.0}
    assert all(i.payload["burst_factor"] == 12.0 for i in items)
    with pytest.raises(ValueError):
        generate_s3(5, cfg.get_rng("s3"), cfg, burst_factor=0.5)


def test_s3_some_items_require_human_routing() -> None:
    cfg = load_config()
    items = generate(ScenarioId.S3, 200, cfg.get_rng("s3"), cfg)
    threshold = cfg.patterns.p6.confidence_threshold
    human = [i for i in items if i.payload["needs_human"]]
    auto = [i for i in items if not i.payload["needs_human"]]
    assert human and auto
    assert all(i.payload["confidence"] < threshold for i in human)
    assert all(i.payload["confidence"] >= threshold for i in auto)


def test_s3_deterministic() -> None:
    cfg = load_config()
    a = generate(ScenarioId.S3, 30, cfg.get_rng("s3"), cfg)
    b = generate(ScenarioId.S3, 30, cfg.get_rng("s3"), cfg)
    assert [i.payload for i in a] == [i.payload for i in b]
