"""Pattern-selection decision tree — paper Fig. 2 (task 042).

Renders ``figures/decision_tree.png`` from the pattern catalog: each
leaf carries the pattern's registry id and the ``name``/``intent``
drawn from its ``meta()`` (the nine-element catalog form), so the
figure stays consistent with the implemented catalog by construction.

Decision dimensions (the paper's selection logic):

1. Does the workflow span independent platform/trust domains?  -> P7
2. Must consequential outputs pass human oversight?            -> P6
3. Is the dominant integration surface external tools/APIs?    -> P5
4. Do agents coordinate through shared evolving state?         -> P4
5. Is the control topology centralized?
     yes: fixed linear stages? -> P2 else -> P1
     no  (event-driven, loosely coupled)                       -> P3

Usage: ``python -m agentorch.study.decision_tree [--out figures/]``.
"""
from __future__ import annotations

import argparse
import textwrap
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from agentorch.patterns.registry import REGISTRY  # noqa: E402
from agentorch.types import PatternId  # noqa: E402

plt.rcParams.update({"font.size": 8, "figure.dpi": 300})

# (question, yes -> PatternId leaf); final "no" chain resolves P1/P2/P3.
DECISIONS: list[tuple[str, PatternId]] = [
    ("Workflow spans independent\nplatform / trust domains?", PatternId.BRIDGE),
    ("Consequential outputs require\nhuman oversight (EU AI Act Art. 14)?",
     PatternId.HITL),
    ("Dominant surface is external\ntools / APIs needing bulkheads?",
     PatternId.GATEWAY),
    ("Agents coordinate via shared\nevolving state (blackboard)?",
     PatternId.BLACKBOARD),
]
FINAL_QUESTION = "Centralized control topology?"
CENTRAL_QUESTION = "Fixed linear stages?"


def _leaf_label(pattern_id: PatternId) -> str:
    meta = REGISTRY[pattern_id].meta()
    intent = textwrap.shorten(str(meta["intent"]), width=58, placeholder="...")
    return f"{pattern_id.value}: {meta['name'].split(' ', 1)[1]}\n{intent}"


def draw_tree(out_path: Path) -> None:
    fig, ax = plt.subplots(figsize=(7.0, 6.2))
    ax.axis("off")
    q_style = dict(boxstyle="round,pad=0.35", facecolor="#dbe9ff",
                   edgecolor="#3b6ea5", linewidth=0.8)
    leaf_style = dict(boxstyle="round,pad=0.35", facecolor="#e6f4e6",
                      edgecolor="#2c7a2c", linewidth=0.8)

    x_q, x_leaf = 0.30, 0.76
    y = 0.95
    dy = 0.155
    prev = None
    for question, leaf in DECISIONS:
        ax.text(x_q, y, question, ha="center", va="center", bbox=q_style,
                wrap=True)
        ax.annotate("", xy=(x_leaf - 0.165, y), xytext=(x_q + 0.135, y),
                    arrowprops=dict(arrowstyle="->", linewidth=0.8))
        ax.text((x_q + x_leaf) / 2.0, y + 0.018, "yes", ha="center",
                fontsize=7)
        ax.text(x_leaf, y, _leaf_label(leaf), ha="center", va="center",
                bbox=leaf_style, fontsize=7)
        if prev is not None:
            ax.annotate("", xy=(x_q, y + 0.045), xytext=(x_q, prev - 0.045),
                        arrowprops=dict(arrowstyle="->", linewidth=0.8))
            ax.text(x_q + 0.015, (y + prev) / 2.0, "no", fontsize=7)
        prev = y
        y -= dy

    # Final branch: centralized? -> linear? -> P2/P1, else P3.
    ax.text(x_q, y, FINAL_QUESTION, ha="center", va="center", bbox=q_style)
    ax.annotate("", xy=(x_q, y + 0.045), xytext=(x_q, prev - 0.045),
                arrowprops=dict(arrowstyle="->", linewidth=0.8))
    ax.text(x_q + 0.015, (y + prev) / 2.0, "no", fontsize=7)
    ax.annotate("", xy=(x_leaf - 0.165, y), xytext=(x_q + 0.115, y),
                arrowprops=dict(arrowstyle="->", linewidth=0.8))
    ax.text((x_q + x_leaf) / 2.0, y + 0.018, "no", ha="center", fontsize=7)
    ax.text(x_leaf, y, _leaf_label(PatternId.CHOREOGRAPHY), ha="center",
            va="center", bbox=leaf_style, fontsize=7)

    y2 = y - dy
    ax.text(x_q, y2, CENTRAL_QUESTION, ha="center", va="center", bbox=q_style)
    ax.annotate("", xy=(x_q, y2 + 0.04), xytext=(x_q, y - 0.045),
                arrowprops=dict(arrowstyle="->", linewidth=0.8))
    ax.text(x_q + 0.015, (y2 + y) / 2.0, "yes", fontsize=7)
    y3 = y2 - dy * 0.85
    ax.annotate("", xy=(x_leaf - 0.165, y2), xytext=(x_q + 0.10, y2),
                arrowprops=dict(arrowstyle="->", linewidth=0.8))
    ax.text((x_q + x_leaf) / 2.0, y2 + 0.018, "yes", ha="center", fontsize=7)
    ax.text(x_leaf, y2, _leaf_label(PatternId.PIPELINE), ha="center",
            va="center", bbox=leaf_style, fontsize=7)
    ax.annotate("", xy=(x_leaf - 0.165, y3), xytext=(x_q, y2 - 0.04),
                arrowprops=dict(arrowstyle="->", linewidth=0.8,
                                connectionstyle="angle,angleA=-90,angleB=180"))
    ax.text(x_q + 0.03, (y3 + y2) / 2.0, "no", fontsize=7)
    ax.text(x_leaf, y3, _leaf_label(PatternId.SUPERVISOR), ha="center",
            va="center", bbox=leaf_style, fontsize=7)

    ax.set_xlim(0, 1)
    ax.set_ylim(min(y3 - 0.1, 0), 1.0)
    ax.set_title("Pattern selection decision tree (from catalog metadata)",
                 fontsize=10)
    fig.tight_layout()
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write decision_tree.png")
    parser.add_argument("--out", default="figures/")
    args = parser.parse_args(argv)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    draw_tree(out / "decision_tree.png")
    print(f"wrote {out / 'decision_tree.png'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
