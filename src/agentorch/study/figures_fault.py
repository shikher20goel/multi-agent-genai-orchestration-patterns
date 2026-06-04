"""Fault-isolation figure from results/ — containment matrix (task 041,
HUMAN-gated).

Writes ``figures/fault_matrix.png``: per platform, a pattern x
(component, fault-type) grid colored by the campaign outcome:

- green  = absorbed   (contained AND directly-hit requests still succeed
                       at >= the containment threshold — bulkheads/fallbacks),
- orange = isolated   (contained per the contract, but directly-hit
                       requests fail),
- red    = propagated (failures spread to requests the fault never hit),
- grey   = not exercised (the pattern never traversed the component).

Reads ONLY results/faults.csv.

Usage: ``python -m agentorch.study.figures_fault [--results results/]
[--out figures/]``.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.colors import ListedColormap  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402

PATTERN_ORDER = [f"P{i}" for i in range(1, 8)]

plt.rcParams.update({
    "font.size": 8,
    "axes.titlesize": 10,
    "axes.labelsize": 9,
    "figure.dpi": 300,
})

# Cell codes: 0 = not exercised, 1 = propagated, 2 = isolated, 3 = absorbed.
_CMAP = ListedColormap(["#d9d9d9", "#d62728", "#ff9f1c", "#2ca02c"])
ABSORB_THRESHOLD = 0.95  # mirrors faults.containment_threshold


def make_fault_matrix(faults: pd.DataFrame, out_path: Path) -> None:
    platforms = sorted(faults["platform"].unique())
    cells = sorted(set(zip(faults["component"], faults["fault"])))
    labels = [f"{c}\n{f}" for c, f in cells]
    fig, axes = plt.subplots(len(platforms), 1,
                             figsize=(7.0, 2.2 * len(platforms)),
                             sharex=True)
    if len(platforms) == 1:
        axes = [axes]
    for ax, platform in zip(axes, platforms):
        sub = faults[faults["platform"] == platform]
        grid = np.zeros((len(PATTERN_ORDER), len(cells)))
        for i, pattern in enumerate(PATTERN_ORDER):
            for j, (component, fault) in enumerate(cells):
                row = sub[(sub["pattern"] == pattern)
                          & (sub["component"] == component)
                          & (sub["fault"] == fault)]
                if row.empty:
                    grid[i, j] = 0
                elif "classification" in row.columns:
                    # Task 104: the campaign emits an explicit
                    # PROPAGATED/ISOLATED/ABSORBED/NOT_EXERCISED class.
                    grid[i, j] = {"not_exercised": 0, "propagated": 1,
                                  "isolated": 2, "absorbed": 3}[
                        str(row.iloc[0]["classification"])]
                elif int(row.iloc[0]["n_traversing"]) == 0:
                    grid[i, j] = 0
                elif not bool(row.iloc[0]["contained"]):
                    grid[i, j] = 1
                elif float(row.iloc[0]["traversing_success_rate"]) >= ABSORB_THRESHOLD:
                    grid[i, j] = 3
                else:
                    grid[i, j] = 2
        ax.imshow(grid, cmap=_CMAP, vmin=0, vmax=3, aspect="auto")
        ax.set_yticks(range(len(PATTERN_ORDER)))
        ax.set_yticklabels(PATTERN_ORDER)
        ax.set_title(f"fault containment — {platform}")
        ax.set_xticks(range(len(cells)))
        ax.set_xticklabels(labels, rotation=90)
        for edge in np.arange(-0.5, len(cells), 1.0):
            ax.axvline(edge, color="white", linewidth=0.5)
        for edge in np.arange(-0.5, len(PATTERN_ORDER), 1.0):
            ax.axhline(edge, color="white", linewidth=0.5)
    axes[-1].set_xlabel("(component, injected fault)")
    legend = [Patch(facecolor="#2ca02c", label="absorbed"),
              Patch(facecolor="#ff9f1c", label="isolated"),
              Patch(facecolor="#d62728", label="propagated"),
              Patch(facecolor="#d9d9d9", label="not exercised")]
    fig.legend(handles=legend, loc="upper right", frameon=False, fontsize=8)
    fig.tight_layout()
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write fault matrix figure")
    parser.add_argument("--results", default="results/")
    parser.add_argument("--out", default="figures/")
    args = parser.parse_args(argv)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    faults = pd.read_csv(Path(args.results) / "faults.csv")
    make_fault_matrix(faults, out / "fault_matrix.png")
    print(f"wrote {out / 'fault_matrix.png'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
