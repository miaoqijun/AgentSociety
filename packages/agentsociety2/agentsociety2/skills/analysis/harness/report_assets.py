from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import List, Set

MD_ASSET_REF_RE = re.compile(r"!\[[^\]]*\]\((?:assets|charts)/([^)]+)\)")
HTML_ASSET_REF_RE = re.compile(
    r"""<img[^>]*\ssrc=["'](?:assets|charts)/([^"']+)["']""",
    re.IGNORECASE,
)
CHARTS_PATH_IN_BODY_RE = re.compile(r"""(?:\]\(|src=["'])(charts/[^"')]+)""")


def referenced_asset_names(presentation_dir: Path) -> Set[str]:
    names: Set[str] = set()
    for fname in (
        "report_zh.md",
        "report_en.md",
        "report_zh.html",
        "report_en.html",
    ):
        path = presentation_dir / fname
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        names |= set(MD_ASSET_REF_RE.findall(text))
        names |= set(HTML_ASSET_REF_RE.findall(text))
    return names


def charts_path_refs_in_reports(presentation_dir: Path) -> List[str]:
    found: List[str] = []
    for fname in (
        "report_zh.md",
        "report_en.md",
        "report_zh.html",
        "report_en.html",
    ):
        path = presentation_dir / fname
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        found.extend(CHARTS_PATH_IN_BODY_RE.findall(text))
    return found


def sync_report_assets_from_reports(presentation_dir: Path) -> dict:
    """Copy chart files referenced in reports from charts/ into assets/."""
    presentation_dir = presentation_dir.resolve()
    charts_dir = presentation_dir / "charts"
    assets_dir = presentation_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)

    copied: List[str] = []
    missing: List[str] = []

    for name in sorted(referenced_asset_names(presentation_dir)):
        dest = assets_dir / name
        if dest.is_file():
            continue
        src = charts_dir / name
        if src.is_file():
            shutil.copy2(src, dest)
            copied.append(name)
            continue
        missing.append(name)

    return {
        "copied": copied,
        "missing": missing,
        "assets_dir": str(assets_dir),
    }
