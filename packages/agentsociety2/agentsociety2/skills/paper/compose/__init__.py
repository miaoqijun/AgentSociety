"""Compose package - markdown -> LaTeX -> PDF (Phase 2 of M1).

Submodules:

- :mod:`md_to_tex` - producer Markdown -> LaTeX body fragment
- :mod:`figure_packer` - copy panel files into ``compose/Figure/`` + render
  the ``\\begin{figure}...\\end{figure}`` blocks consumed by the template
- :mod:`latex_assembly` - render ``main.tex.j2`` and copy the Nature class
  / bib style files into the per-run compose tree
- :mod:`compiler` - run ``latexmk`` and surface a structured
  :class:`CompileResult` (or :class:`CompileError` when latexmk is absent)
"""

from __future__ import annotations

from agentsociety2.skills.paper.compose import (
    compiler,
    figure_packer,
    latex_assembly,
    md_to_tex,
)

__all__ = ["compiler", "figure_packer", "latex_assembly", "md_to_tex"]
