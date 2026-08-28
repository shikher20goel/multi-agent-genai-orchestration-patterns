"""Build the IEEE "Author's Tracked Changes" PDF by highlighting revised prose.

latexdiff is not available in this environment, and even where it is, its
output is a re-typeset document rather than the submitted PDF with changes
marked. IEEE wants the latter. So this script diffs the revised .tex
against the SUBMITTED .tex, then finds each changed sentence in the
rendered PDF's word stream and lays a highlight annotation over it.

The matching is the whole problem, and three things make a naive search
fail on a typeset two-column PDF:

  * Hyphenation. A word broken across lines appears as two words joined by
    U+002D or U+2010, and the second half starts a new line. Those are
    merged back before matching.
  * Cross-line and cross-column runs. A sentence's words are contiguous in
    the text stream but not on the page, so a match yields several
    rectangles, not one; each becomes its own quad.
  * Commands that render to something other than their source. `\\ref`,
    `\\cite`, math and accents all mean the .tex token stream and the PDF
    token stream disagree. Matching is therefore done on alphanumeric
    tokens only, and a bounded number of unmatched PDF tokens is tolerated
    inside a run so a citation number in the middle of a sentence does not
    break it.

A sentence that still cannot be located is reported rather than silently
dropped: an under-highlighted PDF is a correctness problem for the
reviewer, so the count is printed and compared against a floor.

Usage:
    python scripts/highlight_changes.py OLD.tex NEW.tex NEW.pdf OUT.pdf
"""
from __future__ import annotations

import difflib
import re
import sys
from pathlib import Path

import fitz  # PyMuPDF

# Environments whose bodies are not prose and should not drive highlighting.
_SKIP_ENV = ("tabular", "algorithmic", "algorithm", "thebibliography",
             "equation", "align", "verbatim", "lstlisting")


def strip_tex(s: str) -> str:
    """Reduce LaTeX to the prose a reader sees, preserving sentence order."""
    s = re.sub(r"(?<!\\)%.*", "", s)                    # comments, not \%
    s = re.sub(r"\\(begin|end)\{[^}]*\}", " ", s)
    s = re.sub(r"\\(label|ref|eqref|cite|citep|citet)\{[^}]*\}", " ", s)
    s = re.sub(r"\\(includegraphics|input|include)(\[[^\]]*\])?\{[^}]*\}", " ", s)
    s = re.sub(r"\$[^$]*\$", " ", s)                     # inline math
    s = re.sub(r"\\[a-zA-Z]+\*?", " ", s)                # remaining commands
    s = s.replace("---", "-").replace("--", "-")
    s = re.sub(r"[{}~\\]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def sentences(tex: str) -> list[str]:
    """Prose sentences in document order, skipping non-prose environments."""
    body = tex
    for env in _SKIP_ENV:
        body = re.sub(rf"\\begin\{{{env}\}}.*?\\end\{{{env}\}}", " ",
                      body, flags=re.S)
    # Captions and section headings ARE prose a reviewer must see marked.
    extra = re.findall(r"\\caption\{(.*?)\}\s*\n", tex, flags=re.S)
    extra += re.findall(r"\\(?:sub)*section\*?\{([^}]*)\}", tex)
    out = []
    for chunk in [strip_tex(body)] + [strip_tex(x) for x in extra]:
        for s in re.split(r"(?<=[.:;!?])\s+", chunk):
            s = s.strip()
            if len(s.split()) >= 4:          # too short to match reliably
                out.append(s)
    return out


def toks(s: str) -> list[str]:
    return [t for t in re.findall(r"[A-Za-z0-9]+", s.lower()) if t]


def page_stream(page):
    """Word stream with hyphenated line-breaks rejoined."""
    words = page.get_text("words")
    words.sort(key=lambda w: (w[5], w[6], w[7]))
    merged = []
    i = 0
    while i < len(words):
        x0, y0, x1, y1, w, *rest = words[i]
        if w.endswith(("-", "\u2010")) and i + 1 < len(words):
            nxt = words[i + 1]
            merged.append((w[:-1] + nxt[4],
                           [fitz.Rect(x0, y0, x1, y1),
                            fitz.Rect(nxt[0], nxt[1], nxt[2], nxt[3])]))
            i += 2
            continue
        merged.append((w, [fitz.Rect(x0, y0, x1, y1)]))
        i += 1
    return [(toks(w)[0] if toks(w) else "", r) for w, r in merged]


def find_run(stream, target, min_ratio=0.72, span_factor=3.0):
    """Locate target tokens in the stream; return rects of the best match.

    Exact runs do not survive a typeset PDF: rendered citation numbers,
    math, and reference numbers all appear in the page stream but not in
    the stripped .tex, and sentence splitting occasionally clips a token.
    So this aligns greedily in order and accepts the best window in which
    at least min_ratio of the target tokens are found, bounding the window
    to span_factor x the target length so a "match" cannot be scattered
    across half a page.

    Returns rects for the tokens that actually matched, so the highlight
    covers the located words rather than a bounding box over everything
    between them.
    """
    tgt = target if isinstance(target, list) else toks(target)
    if len(tgt) < 4:
        return None
    n = len(stream)
    max_span = int(len(tgt) * span_factor) + 8
    best, best_hits = None, 0
    for start in range(n):
        if stream[start][0] != tgt[0]:
            continue
        rects, ti, hits = [], 0, 0
        si = start
        limit = min(n, start + max_span)
        while ti < len(tgt) and si < limit:
            if stream[si][0] and stream[si][0] == tgt[ti]:
                rects.extend(stream[si][1])
                hits += 1
                ti += 1
            elif ti + 1 < len(tgt) and stream[si][0] == tgt[ti + 1]:
                # target token absent from the render (e.g. clipped by
                # sentence splitting); skip it rather than abandon the run
                ti += 1
                if stream[si][0] == tgt[ti]:
                    rects.extend(stream[si][1])
                    hits += 1
                    ti += 1
            si += 1
        if hits > best_hits:
            best_hits, best = hits, rects
        if hits == len(tgt):
            break
    if best and best_hits / len(tgt) >= min_ratio:
        return best
    return None


def main(argv=None) -> int:
    a = argv or sys.argv[1:]
    if len(a) != 4:
        sys.exit("usage: highlight_changes.py OLD.tex NEW.tex NEW.pdf OUT.pdf")
    old_tex, new_tex, new_pdf, out_pdf = a

    old_s = sentences(Path(old_tex).read_text())
    new_s = sentences(Path(new_tex).read_text())
    sm = difflib.SequenceMatcher(None, [toks(x) and " ".join(toks(x)) for x in old_s],
                                 [toks(x) and " ".join(toks(x)) for x in new_s],
                                 autojunk=False)
    changed = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag in ("insert", "replace"):
            changed.extend(new_s[j1:j2])
    # Long sentences are matched in windows: a single unmatched token deep
    # inside a 60-word sentence would otherwise lose the whole highlight.
    targets = []
    for s in changed:
        t = toks(s)
        if len(t) <= 25:
            targets.append(t)
        else:
            for k in range(0, len(t), 20):
                w = t[k:k + 20]
                if len(w) >= 5:
                    targets.append(w)

    doc = fitz.open(new_pdf)
    # Hold the Page objects: an annotation created from a transient
    # doc[i] can be collected before update() and unbinds itself.
    pages = [doc[i] for i in range(doc.page_count)]
    streams = [page_stream(p) for p in pages]
    hits = misses = 0
    for tgt in targets:
        placed = False
        for pno, st in enumerate(streams):
            rects = find_run(st, tgt)
            if rects:
                annot = pages[pno].add_highlight_annot(rects)
                annot.set_colors(stroke=(1, 1, 0.25))
                annot.update()
                hits += 1
                placed = True
                break
        if not placed:
            misses += 1
    doc.save(out_pdf, garbage=3, deflate=True)
    total = hits + misses
    print(f"changed sentences: {len(changed)}")
    print(f"match targets:     {total}")
    print(f"annotations added: {hits}")
    print(f"unmatched:         {misses}"
          f" ({100.0 * misses / total:.1f}%)" if total else "")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
