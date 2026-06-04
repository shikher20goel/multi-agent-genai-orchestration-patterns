"""Trivial harness smoke test (task 002)."""
import agentorch


def test_package_importable() -> None:
    assert hasattr(agentorch, "__version__")
    assert agentorch.__version__
