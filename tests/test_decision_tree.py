"""Task 042: decision tree rendered from pattern catalog metadata."""
from agentorch.study.decision_tree import DECISIONS, draw_tree
from agentorch.types import PatternId


def test_decision_tree_written(tmp_path) -> None:
    png = tmp_path / "decision_tree.png"
    draw_tree(png)
    assert png.exists() and png.stat().st_size > 10_000
    assert png.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


def test_all_seven_patterns_reachable() -> None:
    leaves = {leaf for _, leaf in DECISIONS}
    leaves |= {PatternId.CHOREOGRAPHY, PatternId.PIPELINE, PatternId.SUPERVISOR}
    assert leaves == set(PatternId)
