"""Cost figures from results/ — cost per 1k requests + ledger (task 040,
HUMAN-gated).

Writes ``figures/cost_per_1k.png`` (mean cost-units per 1000 requests,
grouped bars per pattern x platform) and ``figures/cost_ledger.csv``
(task 105: per-(pattern, platform, scenario) aggregation via
``agentorch.rig.costcapture.aggregate_ledger(by_scenario=True)`` so
per-scenario relative-cost claims trace to the ledger). Reads ONLY
results/. Cost units are USD per request under the HUMAN-gated dated
assumptions in ``configs/costs.yaml``; the axis label states that.

Usage: ``python -m agentorch.study.figures_cost [--results results/]
[--out figures/]``.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

from agentorch.rig.costcapture import aggregate_ledger  # noqa: E402

PATTERN_ORDER = [f"P{i}" for i in range(1, 8)]

plt.rcParams.update({
    "font.size": 9,
    "axes.titlesize": 10,
    "axes.labelsize": 9,
    "legend.fontsize": 8,
    "figure.dpi": 300,
})


def make_cost_per_1k(ledger: pd.DataFrame, out_path: Path) -> None:
    platforms = sorted(ledger["platform"].unique())
    fig, ax = plt.subplots(figsize=(3.5, 2.6))
    width = 0.38
    cmap = plt.get_cmap("tab10")
    for j, platform in enumerate(platforms):
        sub = ledger[ledger["platform"] == platform].set_index("pattern")
        xs, ys = [], []
        for i, pattern in enumerate(PATTERN_ORDER):
            if pattern not in sub.index:
                continue
            xs.append(i + (j - 0.5) * width)
            ys.append(float(sub.loc[pattern, "mean_cost_units"]) * 1000.0)
        ax.bar(xs, ys, width=width, color=cmap(j), alpha=0.85, label=platform)
    ax.set_xticks(range(len(PATTERN_ORDER)))
    ax.set_xticklabels(PATTERN_ORDER)
    ax.set_xlabel("pattern")
    ax.set_ylabel("cost units / 1k requests\n(USD, configs/costs.yaml assumptions)")
    ax.set_yscale("log")
    ax.grid(True, axis="y", which="both", alpha=0.25, linewidth=0.4)
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write cost figure + ledger")
    parser.add_argument("--results", default="results/")
    parser.add_argument("--out", default="figures/")
    args = parser.parse_args(argv)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    cost = pd.read_csv(Path(args.results) / "cost.csv")
    # Task 105: the persisted ledger is scenario-resolved (42 rows);
    # the figure shows the per-(pattern, platform) aggregate.
    ledger_scenario = aggregate_ledger(cost, by_scenario=True)
    ledger_scenario.to_csv(out / "cost_ledger.csv", index=False)
    ledger = aggregate_ledger(cost)
    make_cost_per_1k(ledger, out / "cost_per_1k.png")
    print(f"wrote {out / 'cost_per_1k.png'} and {out / 'cost_ledger.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
