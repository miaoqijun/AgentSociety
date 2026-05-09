"""Render ``main.tex.j2`` and copy Nature class / bib style files into the
per-run compose tree.

Phase 2 plan §"compose/latex_assembly.py" (merged from the original
template_renderer + template_packer split):

1. Render ``templates/nature/main.tex.j2`` with placeholders:
   ``title``, ``authors_block``, ``affils_block``, ``abstract``,
   ``body_main``, ``body_results``, ``body_discussion``,
   ``data_availability``, ``code_availability``, ``figures_block``,
   ``bib_path``.
2. Copy ``wlscirep.cls``, ``naturemag-doi.bst``, ``jabbrv.sty``,
   ``jabbrv-ltwa-{all,en}.ldf`` into the compose directory so latexmk can
   build without depending on the project tree's location.

Authors / affils blocks are produced from a :class:`PaperMeta` instance
following the convention from ``Nature_template/main.tex``::

    \\author[1]{Alice Author}
    \\author[1,*]{Bob Builder}
    \\affil[1]{Foo Lab}
    \\affil[*]{To whom correspondence should be addressed; Email: ...}

When no corresponding author is present the ``[*]`` slot is omitted.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import List, Optional

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from agentsociety2.skills.paper.models import Author, PaperMeta
from agentsociety2.skills.paper.paths import nature_template_dir

# Files copied verbatim from templates/nature/ -> compose dir
NATURE_SUPPORT_FILES: tuple[str, ...] = (
    "wlscirep.cls",
    "naturemag-doi.bst",
    "jabbrv.sty",
    "jabbrv-ltwa-all.ldf",
    "jabbrv-ltwa-en.ldf",
)

MAIN_TEMPLATE_NAME = "main.tex.j2"


# ---------------------------------------------------------------------------
# Author / affil block builders
# ---------------------------------------------------------------------------


def _author_affil_token(author: Author, has_corresponding_slot: bool) -> str:
    """Build the bracket spec, e.g. ``[1,2,*]`` or ``[1]``."""

    parts: List[str] = [str(a) for a in author.affils]
    if author.corresponding and has_corresponding_slot:
        parts.append("*")
    return "[" + ",".join(parts) + "]" if parts else ""


def render_authors_block(meta: PaperMeta) -> str:
    """Return the ``\\author[...]{Name}`` lines as a single string."""

    has_corresponding = any(a.corresponding for a in meta.authors)
    lines: List[str] = []
    for author in meta.authors:
        token = _author_affil_token(author, has_corresponding)
        lines.append(f"\\author{token}{{{author.name}}}")
    return "\n".join(lines)


def render_affils_block(meta: PaperMeta) -> str:
    """Return the ``\\affil[...]{...}`` lines, plus the corresponding-author tail."""

    lines: List[str] = []
    for affil in meta.affils:
        lines.append(f"\\affil[{affil.id}]{{{affil.name}}}")
    corresponding = [a for a in meta.authors if a.corresponding and a.email]
    if corresponding:
        emails = ", ".join(a.email for a in corresponding if a.email)
        lines.append(
            "\\affil[*]{To whom correspondence should be addressed; Email: "
            + emails
            + "}"
        )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Template rendering
# ---------------------------------------------------------------------------


def _load_environment(template_dir: Optional[Path] = None) -> Environment:
    base = Path(template_dir) if template_dir is not None else nature_template_dir()
    # LaTeX-friendly delimiters: ``<< var >>`` for variables, ``<% block %>``
    # for control blocks.  This avoids collisions with the literal ``{{`` /
    # ``{%`` sequences that show up inside ``\newcommand{\foo}{{\bar{#1}}}``
    # and similar TeX constructs.
    env = Environment(
        loader=FileSystemLoader(str(base)),
        undefined=StrictUndefined,
        keep_trailing_newline=True,
        variable_start_string="<<",
        variable_end_string=">>",
        block_start_string="<%",
        block_end_string="%>",
        comment_start_string="<#",
        comment_end_string="#>",
    )
    return env


def render_main_tex(
    *,
    meta: PaperMeta,
    abstract: str,
    body_main: str,
    body_results: str,
    body_discussion: str,
    data_availability: str = "",
    code_availability: str = "",
    figures_block: str = "",
    bib_path: str = "references.bib",
    template_dir: Optional[Path] = None,
) -> str:
    """Render ``main.tex.j2`` with the supplied content."""

    env = _load_environment(template_dir)
    template = env.get_template(MAIN_TEMPLATE_NAME)
    return template.render(
        title=meta.title,
        authors_block=render_authors_block(meta),
        affils_block=render_affils_block(meta),
        abstract=abstract,
        body_main=body_main,
        body_results=body_results,
        body_discussion=body_discussion,
        data_availability=data_availability,
        code_availability=code_availability,
        figures_block=figures_block,
        bib_path=bib_path,
    )


# ---------------------------------------------------------------------------
# Support-file packing
# ---------------------------------------------------------------------------


def copy_support_files(
    compose_dir: Path,
    *,
    template_dir: Optional[Path] = None,
) -> List[Path]:
    """Copy ``wlscirep.cls`` etc. into ``compose_dir``.

    Returns the list of destination paths.  Raises ``FileNotFoundError`` if
    any expected file is missing from the template directory.
    """

    src_dir = Path(template_dir) if template_dir is not None else nature_template_dir()
    compose_dir.mkdir(parents=True, exist_ok=True)
    out: List[Path] = []
    for name in NATURE_SUPPORT_FILES:
        src = src_dir / name
        if not src.exists():
            raise FileNotFoundError(f"nature template missing: {src}")
        dest = compose_dir / name
        shutil.copy2(src, dest)
        out.append(dest)
    return out


def assemble_compose_tree(
    *,
    meta: PaperMeta,
    abstract: str,
    body_main: str,
    body_results: str,
    body_discussion: str,
    compose_dir: Path,
    data_availability: str = "",
    code_availability: str = "",
    figures_block: str = "",
    bib_filename: str = "references.bib",
    template_dir: Optional[Path] = None,
) -> Path:
    """End-to-end assembly: render main.tex, copy support files, return main.tex path.

    The caller is responsible for placing the bibliography file at
    ``<compose_dir>/<bib_filename>`` (typically via
    :func:`agentsociety2.skills.paper.adapter.bib_writer.write_bibtex_file`)
    and the figure panels under ``<compose_dir>/Figure/`` (via
    :func:`figure_packer.pack_figures`).
    """

    compose_dir = Path(compose_dir)
    compose_dir.mkdir(parents=True, exist_ok=True)
    rendered = render_main_tex(
        meta=meta,
        abstract=abstract,
        body_main=body_main,
        body_results=body_results,
        body_discussion=body_discussion,
        data_availability=data_availability,
        code_availability=code_availability,
        figures_block=figures_block,
        bib_path=bib_filename,
        template_dir=template_dir,
    )
    main_tex_path = compose_dir / "main.tex"
    main_tex_path.write_text(rendered, encoding="utf-8")
    copy_support_files(compose_dir, template_dir=template_dir)
    return main_tex_path


__all__ = [
    "MAIN_TEMPLATE_NAME",
    "NATURE_SUPPORT_FILES",
    "assemble_compose_tree",
    "copy_support_files",
    "render_affils_block",
    "render_authors_block",
    "render_main_tex",
]
