"""Convert producer-emitted Markdown into LaTeX body suitable for the
Nature template.

Conversion rules (per Phase 2 of the M1 plan):

- ``**bold**`` -> ``\\textbf{bold}``
- ``*italic*`` / ``_italic_`` -> ``\\textit{italic}``
- ```` `code` ```` -> ``\\texttt{code}``
- Inline ``$math$`` passes through verbatim
- Display ``$$math$$`` -> ``\\[ math \\]``
- ``- item`` / ``1. item`` -> ``\\begin{itemize}|\\begin{enumerate}`` blocks
- ``[CITE:key]`` -> ``\\supercite{key}`` (comma-separated keys allowed)
- ``[FIG:id]`` -> ``Fig.~\\ref{fig:id}``
- ``[TABLE:id]`` -> ``Table~\\ref{tab:id}``
- ``%``, ``&``, ``#``, ``_``, ``$`` escaped in plain-text contexts

The :func:`md_to_tex` entry point is order-aware: inline math, display
math, code spans and the citation / reference sentinels are extracted to
placeholders *before* text-escaping runs, then restored after inline
formatting.  This avoids double-escaping LaTeX inside math or citations.

Headings (``##`` and below) are converted to ``\\subsection*{...}`` /
``\\subsubsection*{...}``; ``#`` is *not* converted (the Nature template
owns top-level sections via ``\\section*{Main}`` etc.).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Tuple

# ---------------------------------------------------------------------------
# Regex patterns (compiled once)
# ---------------------------------------------------------------------------

# Protected regions: extracted before any text-level escape.
_RE_DISPLAY_MATH = re.compile(r"\$\$(.+?)\$\$", re.DOTALL)
_RE_INLINE_MATH = re.compile(r"(?<!\\)\$([^$\n]+?)\$")
_RE_CODE_SPAN = re.compile(r"`([^`]+)`")
_RE_CITE = re.compile(r"\[CITE:([^\]]+)\]")
_RE_FIG = re.compile(r"\[FIG:([^\]]+)\]")
_RE_TABLE = re.compile(r"\[TABLE:([^\]]+)\]")

# Inline formatting (run AFTER protected regions are extracted).
_RE_BOLD = re.compile(r"\*\*(.+?)\*\*")
_RE_ITALIC_STAR = re.compile(r"(?<!\*)\*(?!\*)([^\n*]+?)(?<!\*)\*(?!\*)")
_RE_ITALIC_UNDER = re.compile(r"(?<!_)_(?!_)([^\n_]+?)(?<!_)_(?!_)")

# Block-level
_RE_HEADING_3 = re.compile(r"^### +(.+)$")
_RE_HEADING_2 = re.compile(r"^## +(.+)$")
_RE_LIST_BULLET = re.compile(r"^- +(.+)$")
_RE_LIST_ORDERED = re.compile(r"^(\d+)\. +(.+)$")
_RE_DISPLAY_MATH_BLOCK_START = re.compile(r"^\$\$(.*)$")

# Characters that need TeX escaping in plain text
# Order matters: backslash must be handled first (we don't escape it because
# the producer should not emit raw backslashes; instead, any LaTeX command we
# emit is added AFTER escaping via placeholders).
_TEX_ESCAPES: Tuple[Tuple[str, str], ...] = (
    ("%", r"\%"),
    ("&", r"\&"),
    ("#", r"\#"),
    ("_", r"\_"),
    ("$", r"\$"),
)


@dataclass
class _Placeholders:
    """Holds extracted protected regions keyed by stable tokens."""

    next_id: int = 0
    table: dict = field(default_factory=dict)

    def stash(self, latex: str) -> str:
        # Token contains only uppercase letters + digits so it survives the
        # text-escape pass (no %, &, #, _, $) AND the inline-formatting pass
        # (no *).  Restoration keys on the same token verbatim.
        token = f"\x01PROTBLK{self.next_id:06d}ENDPRO\x02"
        self.table[token] = latex
        self.next_id += 1
        return token

    def restore(self, text: str) -> str:
        for token, latex in self.table.items():
            text = text.replace(token, latex)
        return text


# ---------------------------------------------------------------------------
# Inline conversion
# ---------------------------------------------------------------------------


def _convert_inline(text: str, placeholders: _Placeholders) -> str:
    """Convert one paragraph or list-item line to LaTeX inline form."""

    # 1. Protect display math (rare in inline, but the producer may inline it).
    def _stash_display(m: "re.Match[str]") -> str:
        body = m.group(1).strip()
        return placeholders.stash(f"\\[ {body} \\]")

    text = _RE_DISPLAY_MATH.sub(_stash_display, text)

    # 2. Protect inline math (verbatim passthrough).
    def _stash_inline_math(m: "re.Match[str]") -> str:
        return placeholders.stash(f"${m.group(1)}$")

    text = _RE_INLINE_MATH.sub(_stash_inline_math, text)

    # 3. Protect code spans.
    def _stash_code(m: "re.Match[str]") -> str:
        body = m.group(1)
        # Inside \texttt{} we still need to escape % & # _ $
        body_escaped = body
        for ch, esc in _TEX_ESCAPES:
            body_escaped = body_escaped.replace(ch, esc)
        return placeholders.stash(f"\\texttt{{{body_escaped}}}")

    text = _RE_CODE_SPAN.sub(_stash_code, text)

    # 4. Protect citation / figure / table refs.
    text = _RE_CITE.sub(
        lambda m: placeholders.stash(f"\\supercite{{{m.group(1).strip()}}}"),
        text,
    )
    text = _RE_FIG.sub(
        lambda m: placeholders.stash(f"Fig.~\\ref{{fig:{m.group(1).strip()}}}"),
        text,
    )
    text = _RE_TABLE.sub(
        lambda m: placeholders.stash(f"Table~\\ref{{tab:{m.group(1).strip()}}}"),
        text,
    )

    # 5. Inline formatting BEFORE text escape, so ``_under_`` is consumed by
    #    italic-under conversion rather than being mistaken for an escaped
    #    underscore.  Bold first (greedier marker) so ``**x**`` is not
    #    partially matched as italic.
    text = _RE_BOLD.sub(lambda m: f"\\textbf{{{m.group(1)}}}", text)
    text = _RE_ITALIC_STAR.sub(lambda m: f"\\textit{{{m.group(1)}}}", text)
    text = _RE_ITALIC_UNDER.sub(lambda m: f"\\textit{{{m.group(1)}}}", text)

    # 6. Escape orphan TeX special chars left in the text (% & # _ $).
    #    Anything inside protected placeholders is preserved verbatim;
    #    anything inside \textbf{} / \textit{} bodies is still text and
    #    therefore correctly escaped.
    for ch, esc in _TEX_ESCAPES:
        text = text.replace(ch, esc)

    # 7. Restore protected tokens with their LaTeX equivalents.
    return placeholders.restore(text)


# ---------------------------------------------------------------------------
# Block-level conversion
# ---------------------------------------------------------------------------


def md_to_tex(markdown_text: str) -> str:
    """Convert ``markdown_text`` to a LaTeX body fragment.

    The output is meant to be inserted into a ``\\section*{...}`` body in
    ``main.tex``.  The function does NOT emit ``\\section*`` itself; the
    Nature template owns top-level section structure.
    """

    placeholders = _Placeholders()
    lines = (markdown_text or "").splitlines()
    out: List[str] = []
    i = 0

    def _flush_paragraph(buf: List[str]) -> None:
        if not buf:
            return
        joined = " ".join(line.strip() for line in buf if line.strip())
        if joined:
            out.append(_convert_inline(joined, placeholders))
            out.append("")  # blank line between paragraphs

    para_buf: List[str] = []

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # Blank line - flushes paragraph
        if not stripped:
            _flush_paragraph(para_buf)
            para_buf = []
            i += 1
            continue

        # Display math block on its own line(s): $$ ... $$
        m_disp = _RE_DISPLAY_MATH_BLOCK_START.match(stripped)
        if m_disp and stripped.endswith("$$") and len(stripped) > 4:
            _flush_paragraph(para_buf)
            para_buf = []
            inner = stripped[2:-2].strip()
            out.append(f"\\[ {inner} \\]")
            out.append("")
            i += 1
            continue
        if stripped.startswith("$$"):
            _flush_paragraph(para_buf)
            para_buf = []
            buf: List[str] = [stripped[2:]]
            i += 1
            while i < len(lines) and "$$" not in lines[i]:
                buf.append(lines[i])
                i += 1
            if i < len(lines):
                tail = lines[i]
                idx = tail.find("$$")
                buf.append(tail[:idx])
                i += 1
            inner = "\n".join(b for b in buf).strip()
            out.append("\\[")
            out.append(inner)
            out.append("\\]")
            out.append("")
            continue

        # Headings
        m3 = _RE_HEADING_3.match(stripped)
        if m3:
            _flush_paragraph(para_buf)
            para_buf = []
            heading = _convert_inline(m3.group(1).strip(), placeholders)
            out.append(f"\\subsubsection*{{{heading}}}")
            out.append("")
            i += 1
            continue
        m2 = _RE_HEADING_2.match(stripped)
        if m2:
            _flush_paragraph(para_buf)
            para_buf = []
            heading = _convert_inline(m2.group(1).strip(), placeholders)
            out.append(f"\\subsection*{{{heading}}}")
            out.append("")
            i += 1
            continue

        # Unordered list block
        if _RE_LIST_BULLET.match(stripped):
            _flush_paragraph(para_buf)
            para_buf = []
            items: List[str] = []
            while i < len(lines):
                m = _RE_LIST_BULLET.match(lines[i].strip())
                if not m:
                    break
                items.append(_convert_inline(m.group(1).strip(), placeholders))
                i += 1
            out.append("\\begin{itemize}")
            for item in items:
                out.append(f"  \\item {item}")
            out.append("\\end{itemize}")
            out.append("")
            continue

        # Ordered list block
        if _RE_LIST_ORDERED.match(stripped):
            _flush_paragraph(para_buf)
            para_buf = []
            items = []
            while i < len(lines):
                m = _RE_LIST_ORDERED.match(lines[i].strip())
                if not m:
                    break
                items.append(_convert_inline(m.group(2).strip(), placeholders))
                i += 1
            out.append("\\begin{enumerate}")
            for item in items:
                out.append(f"  \\item {item}")
            out.append("\\end{enumerate}")
            out.append("")
            continue

        # Default: accumulate paragraph text
        para_buf.append(line)
        i += 1

    _flush_paragraph(para_buf)
    # Drop trailing blank lines for cleaner output
    while out and out[-1] == "":
        out.pop()
    return "\n".join(out) + ("\n" if out else "")


__all__ = ["md_to_tex"]
