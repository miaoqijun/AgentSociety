"""BibTeX writer (verbatim move from old generator.py).

Reads ``literature_index.json`` produced by the literature-search skill and
emits a ``references.bib`` file that the LaTeX template can consume via
``\\addbibresource{references.bib}``.

The :func:`build_reference_strings` helper is the verbatim replacement for
``_build_reference_strings`` in the old generator and is unit-tested for
semantic preservation in :mod:`tests.skills.paper.test_adapter_bib_writer`.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from agentsociety2.skills.paper.adapter.summary import (
    sanitize_bibtex_key,
    trim_text,
)


def build_reference_strings(
    entries: List[Dict[str, Any]],
    *,
    limit: int | None = 30,
) -> List[str]:
    """Convert literature entries to BibTeX ``@article`` strings.

    Verbatim move of the old ``_build_reference_strings`` (with ``limit``
    exposed instead of hardcoded 30).
    """

    refs: List[str] = []
    for idx, entry in enumerate(entries):
        title = (entry.get("title") or "").strip()
        if not title:
            continue

        journal = (entry.get("journal") or "").strip()
        doi = (entry.get("doi") or "").strip()
        abstract = (entry.get("abstract") or "").strip()
        extra = entry.get("extra_fields") or {}
        authors = extra.get("authors") or entry.get("authors") or ""
        year = extra.get("year") or entry.get("year") or ""
        if isinstance(year, (int, float)):
            year = str(int(year))
        url = extra.get("url") or entry.get("url") or ""

        key = sanitize_bibtex_key(title, idx, year=year)

        fields: List[str] = [f"  title = {{{title}}}"]
        if authors:
            if isinstance(authors, list):
                author_str = " and ".join(str(a) for a in authors)
            else:
                author_str = str(authors)
            fields.append(f"  author = {{{author_str}}}")
        if journal:
            fields.append(f"  journal = {{{journal}}}")
        if year:
            fields.append(f"  year = {{{year}}}")
        if doi:
            fields.append(f"  doi = {{{doi}}}")
        if url:
            fields.append(f"  url = {{{url}}}")
        if abstract:
            fields.append(f"  abstract = {{{trim_text(abstract, 500)}}}")

        fields_str = ",\n".join(fields)
        refs.append(f"@article{{{key},\n{fields_str}\n}}")

    if limit is None:
        return refs
    return refs[:limit]


def load_literature_entries(
    literature_index_path: Path,
) -> List[Dict[str, Any]]:
    """Read and return the ``entries`` array from ``literature_index.json``."""

    if not literature_index_path.exists():
        return []
    try:
        data = json.loads(literature_index_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    entries = data.get("entries") if isinstance(data, dict) else None
    if not isinstance(entries, list):
        return []
    return entries


def write_bibtex_file(
    literature_index_path: Path,
    out_path: Path,
    *,
    limit: int | None = 30,
) -> int:
    """Write a BibTeX file from ``literature_index.json``.

    Returns the number of entries actually written.  Out-path parents are
    created automatically; if the literature index is missing or unreadable
    the function writes an empty ``.bib`` and returns 0.
    """

    entries = load_literature_entries(literature_index_path)
    refs = build_reference_strings(entries, limit=limit)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n\n".join(refs) + ("\n" if refs else ""), encoding="utf-8")
    return len(refs)


# Legacy alias for source-level back-compat with the old generator.
_build_reference_strings = build_reference_strings


__all__ = [
    "build_reference_strings",
    "load_literature_entries",
    "write_bibtex_file",
    "_build_reference_strings",
]
