"""Copy figure panels into the compose tree and render LaTeX figure blocks.

Plan rule (verbatim):

    \\begin{figure}[t]
    \\centering
    \\includegraphics[width=\\textwidth]{Figure/<id>.<ext>}
    \\caption{\\textbf{<title>.} \\textbf{a,} ... \\textbf{b,} ...}
    \\label{fig:<id>}
    \\end{figure}

The :func:`pack_figures` entry point operates on
:class:`agentsociety2.skills.paper.models.FigureSpec` instances (typically
loaded from ``figure_argument_map.json``).  It copies each spec's
``file_path`` into ``compose_dir/Figure/<figure_id_slug>.<ext>`` and
returns the rendered LaTeX block ready to inject into ``main.tex.j2``'s
``{{ figures_block }}`` placeholder.

Figures with ``file_path is None`` are skipped (they are still in
"planned" status and shouldn't appear in the compiled draft).
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Iterable, List, Tuple

from agentsociety2.skills.paper.models import FigureSpec


_RE_NON_SLUG = re.compile(r"[^A-Za-z0-9]+")


def _slugify_figure_id(figure_id: str) -> str:
    """Normalize a figure_id (e.g. ``fig:welfare_curve``) into a filename stem."""

    raw = figure_id.replace("fig:", "")
    slug = _RE_NON_SLUG.sub("_", raw).strip("_")
    return slug or "figure"


def _copy_panel(src: Path, dest_dir: Path, slug: str) -> Path:
    if not src.exists():
        raise FileNotFoundError(f"figure panel not found: {src}")
    dest_dir.mkdir(parents=True, exist_ok=True)
    ext = src.suffix.lower() or ".png"
    dest = dest_dir / f"{slug}{ext}"
    shutil.copy2(src, dest)
    return dest


def _format_panel_caption(panels: List[str]) -> str:
    """Render panel descriptions as ``\\textbf{a,} desc \\textbf{b,} desc ...``."""

    if not panels:
        return ""
    parts: List[str] = []
    for idx, panel in enumerate(panels):
        label = chr(ord("a") + idx) if idx < 26 else f"p{idx}"
        # Avoid trailing dot duplication
        body = panel.strip().rstrip(".")
        parts.append(f"\\textbf{{{label},}} {body}.")
    return " ".join(parts)


def render_figure_block(spec: FigureSpec, *, copied_filename: str) -> str:
    """Render the ``\\begin{figure}...\\end{figure}`` block for one spec."""

    title = (spec.title or spec.figure_id).strip().rstrip(".")
    panels_caption = _format_panel_caption(spec.panels)
    label = spec.figure_id if spec.figure_id.startswith("fig:") else f"fig:{spec.figure_id}"
    caption_body = f"\\textbf{{{title}.}}"
    if panels_caption:
        caption_body = f"{caption_body} {panels_caption}"
    lines = [
        "\\begin{figure}[t]",
        "\\centering",
        f"\\includegraphics[width=\\textwidth]{{Figure/{copied_filename}}}",
        f"\\caption{{{caption_body}}}",
        f"\\label{{{label}}}",
        "\\end{figure}",
    ]
    return "\n".join(lines)


def pack_figures(
    specs: Iterable[FigureSpec],
    compose_dir: Path,
    *,
    skip_missing: bool = False,
) -> Tuple[List[Path], str]:
    """Copy panels and render the combined figures block.

    Returns ``(copied_files, figures_block_str)``.  The block is suitable
    for the ``{{ figures_block }}`` placeholder in ``main.tex.j2``.

    ``skip_missing=True`` silently skips figures whose ``file_path`` does
    not resolve (useful for partial drafts); the default raises
    :class:`FileNotFoundError`.
    """

    figure_dir = Path(compose_dir) / "Figure"
    blocks: List[str] = []
    copied: List[Path] = []

    for spec in specs:
        if spec.file_path is None:
            continue
        src = Path(spec.file_path)
        if not src.exists():
            if skip_missing:
                continue
            raise FileNotFoundError(f"figure panel not found: {src}")
        slug = _slugify_figure_id(spec.figure_id)
        dest = _copy_panel(src, figure_dir, slug)
        copied.append(dest)
        blocks.append(render_figure_block(spec, copied_filename=dest.name))

    return copied, "\n\n".join(blocks)


__all__ = [
    "pack_figures",
    "render_figure_block",
]
