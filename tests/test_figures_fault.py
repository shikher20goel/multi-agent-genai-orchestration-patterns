"""Task 041 (HUMAN-gated): fault matrix figure from results/faults.csv."""
import pandas as pd

from agentorch.study.figures_fault import make_fault_matrix


def test_fault_matrix_written(smoke_results, tmp_path) -> None:
    faults = pd.read_csv(smoke_results / "faults.csv")
    png = tmp_path / "fault_matrix.png"
    make_fault_matrix(faults, png)
    assert png.exists() and png.stat().st_size > 10_000
    assert png.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
    # The figure must carry information: the campaign distinguishes
    # absorbed (hit requests succeed) from isolated (hit requests fail)
    # cells among the exercised ones.
    hit = faults[faults["n_traversing"] > 0]
    absorbed = (hit["traversing_success_rate"] >= 0.95).sum()
    isolated = (hit["traversing_success_rate"] < 0.95).sum()
    assert absorbed > 0 and isolated > 0
