"""Latency figures from results/ — CCDF + p99 with BCa CIs (task 039, HUMAN-gated).

Writes ``figures/ccdf.png`` (per-pattern latency CCDF, one panel per
platform, scenario S1) and ``figures/p99_ci.png`` (p99 point estimates
with 95% BCa error bars across all conditions). Reads ONLY results/.
Matplotlib Agg; sized/styled to stay legible at IEEE column width.

Usage: ``python -m agentorch.study.figures_latency [--results results/]
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

from agentorch.config import load_config  # noqa: E402
from agentorch.stats.bootstrap import bca_ci  # noqa: E402

PATTERN_ORDER = [f"P{i}" for i in range(1, 8)]
CCDF_SCENARIO = "S1"

plt.rcParams.update({
    "font.size": 9,
    "axes.titlesize": 10,
    "axes.labelsize": 9,
    "legend.fontsize": 7.5,
    "figure.dpi": 300,
})


def make_ccdf(base: pd.DataFrame, out_path: Path) -> None:
    """Per-pattern latency CCDF, one panel per platform (scenario S1)."""
    sub = base[base["scenario"] == CCDF_SCENARIO]
    platforms = sorted(sub["platform"].unique())
    fig, axes = plt.subplots(1, len(platforms), figsize=(7.0, 2.8),
                             sharey=True, sharex=True)
    if len(platforms) == 1:
        axes = [axes]
    cmap = plt.get_cmap("tab10")
    for ax, platform in zip(axes, platforms):
        grp = sub[sub["platform"] == platform]
        for i, pattern in enumerate(PATTERN_ORDER):
            x = np.sort(grp[grp["pattern"] == pattern]["latency_ms"]
                        .to_numpy(dtype=float))
            if x.size == 0:
                continue
            ccdf = 1.0 - np.arange(1, x.size + 1) / x.size
            # Keep the last point plottable on the log axis.
            ccdf[-1] = 1.0 / x.size
            ax.loglog(x, ccdf, label=pattern, color=cmap(i), linewidth=1.2)
        ax.set_title(f"{platform} ({CCDF_SCENARIO})")
        ax.set_xlabel("end-to-end latency (ms)")
        ax.grid(True, which="both", alpha=0.25, linewidth=0.4)
    axes[0].set_ylabel("P(X > x)  (CCDF)")
    axes[0].legend(ncol=2, frameon=False)
    fig.tight_layout()
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)


def make_p99_ci(base: pd.DataFrame, out_path: Path, cfg) -> None:
    """p99 with 95% BCa error bars: panels per scenario, hue per platform."""
    alpha = float(cfg.stats.alpha)
    n_resamples = int(cfg.stats.n_resamples)
    scenarios = sorted(base["scenario"].unique())
    platforms = sorted(base["platform"].unique())
    fig, axes = plt.subplots(1, len(scenarios), figsize=(7.0, 2.8),
                             sharey=True)
    if len(scenarios) == 1:
        axes = [axes]
    width = 0.38
    cmap = plt.get_cmap("tab10")
    for ax, scenario in zip(axes, scenarios):
        for j, platform in enumerate(platforms):
            xs, ys, lo_err, hi_err = [], [], [], []
            for i, pattern in enumerate(PATTERN_ORDER):
                grp = base[(base["scenario"] == scenario)
                           & (base["platform"] == platform)
                           & (base["pattern"] == pattern)]
                x = grp["latency_ms"].to_numpy(dtype=float)
                if x.size == 0:
                    continue
                p99 = float(np.percentile(x, 99))
                rng = cfg.get_rng(f"fig-p99:{pattern}:{platform}:{scenario}")
                lo, hi = bca_ci(x, lambda a: float(np.percentile(a, 99)),
                                alpha=alpha, n_resamples=n_resamples, rng=rng)
                xs.append(i + (j - 0.5) * width)
                ys.append(p99)
                lo_err.append(max(p99 - lo, 0.0))
                hi_err.append(max(hi - p99, 0.0))
            ax.bar(xs, ys, width=width, color=cmap(j), alpha=0.85,
                   label=platform if scenario == scenarios[0] else None)
            ax.errorbar(xs, ys, yerr=[lo_err, hi_err], fmt="none",
                        ecolor="black", elinewidth=0.8, capsize=2)
        ax.set_title(scenario)
        ax.set_xticks(range(len(PATTERN_ORDER)))
        ax.set_xticklabels(PATTERN_ORDER)
        ax.set_xlabel("pattern")
        ax.grid(True, axis="y", alpha=0.25, linewidth=0.4)
    axes[0].set_ylabel("p99 latency (ms), 95% BCa CI")
    fig.legend(loc="upper center", ncol=2, frameon=False,
               bbox_to_anchor=(0.5, 1.08))
    fig.tight_layout()
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write latency figures")
    parser.add_argument("--results", default="results/")
    parser.add_argument("--out", default="figures/")
    args = parser.parse_args(argv)
    cfg = load_config()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    lat = pd.read_csv(Path(args.results) / "latency.csv")
    base = lat[lat["mode"] == "baseline"]
    make_ccdf(base, out / "ccdf.png")
    make_p99_ci(base, out / "p99_ci.png", cfg)
    print(f"wrote {out / 'ccdf.png'} and {out / 'p99_ci.png'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
