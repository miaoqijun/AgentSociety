"""Reusable text + JSON-summary helpers (verbatim move from old generator.py).

These functions previously lived in
``agentsociety2/skills/paper/generator.py``.  They are pure utilities used
by :mod:`research_pack_builder` and :mod:`bib_writer`; nothing here calls
LLMs or writes files.

Extracted helpers:

- :data:`SUPPORTED_IMAGE_FORMATS`
- :func:`collect_figure_paths_under`
- :func:`read_text_safe`
- :func:`extract_heading`           (was ``_extract_heading``)
- :func:`trim_text`                 (was ``_trim_text``)
- :func:`format_title_from_filename` (was ``_format_title_from_filename``)
- :func:`sanitize_bibtex_key`       (was ``_sanitize_bibtex_key``)
- :func:`summarize_analysis_result_json` (was ``_summarize_analysis_result_json``)

Underscore-prefixed aliases are re-exported for source-level back-compat
with the legacy generator module.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import List

SUPPORTED_IMAGE_FORMATS = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp"}


def collect_figure_paths_under(base_dir: Path) -> List[str]:
    """Recursively collect image file paths under ``base_dir``."""

    out: List[str] = []
    if not base_dir.is_dir():
        return out
    for path in sorted(base_dir.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix.lower() not in SUPPORTED_IMAGE_FORMATS:
            continue
        try:
            out.append(str(path.resolve()))
        except OSError:
            continue
    return out


def read_text_safe(path: Path) -> str:
    """Read file content; return empty string if missing or unreadable."""

    if not path.exists():
        return ""
    try:
        return path.read_text(encoding="utf-8").strip()
    except Exception:
        return ""


def extract_heading(text: str) -> str:
    """Extract the first markdown heading or non-empty line."""

    for line in (text or "").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            return stripped.lstrip("#").strip()
        return stripped
    return ""


def trim_text(text: str, limit: int) -> str:
    normalized = (text or "").strip()
    if len(normalized) <= limit:
        return normalized
    return normalized[: limit - 3].rstrip() + "..."


def format_title_from_filename(path: Path) -> str:
    title = path.stem.replace("_", " ").replace("-", " ")
    return " ".join(token.capitalize() for token in title.split()) or path.stem


def sanitize_bibtex_key(title: str, idx: int, year: str = "") -> str:
    """Derive a stable BibTeX cite key from a title and optional year."""

    text = title.lower()
    text = "".join(c for c in text if c.isalnum() or c == " ").strip()
    words = text.split()
    first_word = words[0] if words else f"ref{idx}"
    key = first_word + year
    return key or f"ref{idx}"


def summarize_analysis_result_json(raw_json: str) -> str:
    """Condense analysis JSON into a markdown-like summary string."""

    raw_json = (raw_json or "").strip()
    if not raw_json:
        return ""

    try:
        data = json.loads(raw_json)
    except json.JSONDecodeError:
        return trim_text(raw_json, 6000)

    lines: list[str] = []
    if isinstance(data, dict):
        summary = data.get("summary")
        if isinstance(summary, dict):
            tables = summary.get("tables")
            row_counts = summary.get("row_counts")
            if tables:
                lines.append("Tables: " + ", ".join(str(table) for table in tables))
            if isinstance(row_counts, dict) and row_counts:
                rendered = ", ".join(
                    f"{name}={count}" for name, count in sorted(row_counts.items())
                )
                lines.append("Row counts: " + rendered)

        for key in ("insights", "findings", "recommendations"):
            value = data.get(key)
            if isinstance(value, list) and value:
                rendered_items = [
                    f"- {trim_text(str(item), 400)}"
                    for item in value[:8]
                    if str(item).strip()
                ]
                if rendered_items:
                    lines.append(f"{key.capitalize()}:\n" + "\n".join(rendered_items))

        conclusions = data.get("conclusions")
        if conclusions:
            lines.append("Conclusions:\n" + trim_text(str(conclusions), 3000))

        if not lines:
            lines.append(trim_text(json.dumps(data, ensure_ascii=False, indent=2), 6000))
        return "\n\n".join(lines)

    return trim_text(str(data), 6000)


# Underscore aliases for legacy import paths
_extract_heading = extract_heading
_trim_text = trim_text
_format_title_from_filename = format_title_from_filename
_sanitize_bibtex_key = sanitize_bibtex_key
_summarize_analysis_result_json = summarize_analysis_result_json


__all__ = [
    "SUPPORTED_IMAGE_FORMATS",
    "collect_figure_paths_under",
    "read_text_safe",
    "extract_heading",
    "trim_text",
    "format_title_from_filename",
    "sanitize_bibtex_key",
    "summarize_analysis_result_json",
    # legacy aliases
    "_extract_heading",
    "_trim_text",
    "_format_title_from_filename",
    "_sanitize_bibtex_key",
    "_summarize_analysis_result_json",
]
