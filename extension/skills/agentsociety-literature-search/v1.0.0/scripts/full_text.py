#!/usr/bin/env python3
"""Manage optional full-text PDFs for literature search results.

This helper intentionally lives in the Claude skill rather than the core
AgentSociety Python API. It helps Claude perform follow-up full-text work after
metadata search: list candidate URLs, download open PDFs when available, or
register a user-provided/local PDF in literature_index.json.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


USER_AGENT = (
    "AgentSociety2 literature skill "
    "(+https://github.com/tsinghua-fib-lab/agentsociety)"
)


def _load_index(workspace: Path) -> tuple[Path, dict[str, Any]]:
    index_path = workspace / "papers" / "literature_index.json"
    if not index_path.exists():
        raise SystemExit(f"Literature index not found: {index_path}")
    try:
        return index_path, json.loads(index_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid JSON in {index_path}: {exc}") from exc


def _save_index(index_path: Path, data: dict[str, Any]) -> None:
    data["updated_at"] = datetime.now(timezone.utc).isoformat()
    index_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _entries(data: dict[str, Any]) -> list[dict[str, Any]]:
    entries = data.get("entries", [])
    if not isinstance(entries, list):
        raise SystemExit("literature_index.json has no valid entries array")
    return entries


def _pick_entry(data: dict[str, Any], entry_number: int) -> dict[str, Any]:
    entries = _entries(data)
    if entry_number < 1 or entry_number > len(entries):
        raise SystemExit(
            f"Entry {entry_number} is out of range; index has {len(entries)} entries"
        )
    entry = entries[entry_number - 1]
    if not isinstance(entry, dict):
        raise SystemExit(f"Entry {entry_number} is not an object")
    return entry


def _extra(entry: dict[str, Any]) -> dict[str, Any]:
    extra = entry.get("extra_fields")
    if not isinstance(extra, dict):
        extra = {}
        entry["extra_fields"] = extra
    return extra


def _add_candidate(candidates: list[str], value: Any) -> None:
    if not isinstance(value, str):
        return
    value = value.strip()
    if not value or not re.match(r"^https?://", value, re.IGNORECASE):
        return
    if value not in candidates:
        candidates.append(value)


def _arxiv_pdf_url(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    patterns = [
        r"arxiv\.org/(?:abs|pdf)/([0-9]{4}\.[0-9]{4,5})(?:v\d+)?",
        r"10\.48550/arxiv\.([0-9]{4}\.[0-9]{4,5})(?:v\d+)?",
        r"\barxiv[:/ ]+([0-9]{4}\.[0-9]{4,5})(?:v\d+)?",
    ]
    for pattern in patterns:
        match = re.search(pattern, value, re.IGNORECASE)
        if match:
            return f"https://arxiv.org/pdf/{match.group(1)}.pdf"
    return None


def _candidate_urls(entry: dict[str, Any]) -> list[str]:
    candidates: list[str] = []
    extra = (
        entry.get("extra_fields") if isinstance(entry.get("extra_fields"), dict) else {}
    )

    for source in (entry, extra):
        for field in (
            "pdf_url",
            "pdf",
            "full_text_url",
            "fulltext_url",
            "download_url",
            "url",
        ):
            value = source.get(field)
            arxiv_url = _arxiv_pdf_url(value)
            _add_candidate(candidates, arxiv_url or value)

        for nested_key in ("open_access", "best_oa_location", "primary_location"):
            nested = source.get(nested_key)
            if isinstance(nested, dict):
                for field in ("pdf_url", "landing_page_url", "url"):
                    value = nested.get(field)
                    arxiv_url = _arxiv_pdf_url(value)
                    _add_candidate(candidates, arxiv_url or value)

    doi = entry.get("doi") or extra.get("doi")
    arxiv_url = _arxiv_pdf_url(doi)
    if arxiv_url:
        _add_candidate(candidates, arxiv_url)
    elif isinstance(doi, str) and doi.strip():
        doi = doi.strip()
        _add_candidate(
            candidates,
            (
                doi
                if doi.startswith(("http://", "https://"))
                else f"https://doi.org/{doi}"
            ),
        )

    return candidates


def _safe_stem(entry: dict[str, Any]) -> str:
    file_path = entry.get("file_path")
    if isinstance(file_path, str) and file_path:
        return Path(file_path).stem
    title = entry.get("title") or "full_text"
    stem = re.sub(r'[<>:"/\\|?*\s]+', "_", str(title)).strip("_")
    return stem[:100] or "full_text"


def _looks_like_pdf(url: str, content_type: str, content: bytes) -> bool:
    return (
        "application/pdf" in content_type.lower()
        or urlparse(url).path.lower().endswith(".pdf")
        or content.startswith(b"%PDF-")
    )


def _download_pdf(url: str) -> tuple[bytes, str]:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urlopen(request, timeout=60) as response:
            content = response.read()
            final_url = response.geturl()
            content_type = response.headers.get("content-type", "")
            if not _looks_like_pdf(final_url, content_type, content):
                raise SystemExit(
                    "The candidate URL did not return a PDF. "
                    f"content-type={content_type!r}, final_url={final_url}"
                )
            return content, final_url
    except HTTPError as exc:
        raise SystemExit(f"Download failed: HTTP {exc.code} for {url}") from exc
    except URLError as exc:
        raise SystemExit(f"Download failed: {exc.reason}") from exc


def _relative_path(workspace: Path, target: Path) -> str:
    return target.resolve().relative_to(workspace.resolve()).as_posix()


def _record_full_text(
    entry: dict[str, Any],
    *,
    status: str,
    file_path: str | None = None,
    source_url: str | None = None,
    reason: str | None = None,
) -> None:
    info: dict[str, Any] = {
        "status": status,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    if file_path:
        info["file_path"] = file_path
    if source_url:
        info["source_url"] = source_url
    if reason:
        info["reason"] = reason
    _extra(entry)["full_text"] = info


def command_candidates(args: argparse.Namespace) -> int:
    _, data = _load_index(args.workspace)
    entries = _entries(data)
    selected = [args.entry] if args.entry else list(range(1, len(entries) + 1))
    for number in selected:
        entry = _pick_entry(data, number)
        print(f"\n[{number}] {entry.get('title', 'Untitled')}")
        urls = _candidate_urls(entry)
        if not urls:
            print("  No candidate URLs found.")
            continue
        for url in urls:
            print(f"  - {url}")
    return 0


def command_download(args: argparse.Namespace) -> int:
    index_path, data = _load_index(args.workspace)
    entry = _pick_entry(data, args.entry)
    urls = [args.url] if args.url else _candidate_urls(entry)
    if not urls:
        _record_full_text(
            entry,
            status="no_candidate",
            reason="No open PDF candidate URL was found in the metadata.",
        )
        _save_index(index_path, data)
        print("No candidate URLs found; index marked as no_candidate.")
        return 2

    full_text_dir = args.workspace / "papers" / "full_texts"
    full_text_dir.mkdir(parents=True, exist_ok=True)
    output_name = args.output_name or f"{_safe_stem(entry)}.pdf"
    target = full_text_dir / output_name

    errors: list[str] = []
    for url in urls:
        try:
            content, final_url = _download_pdf(url)
            target.write_bytes(content)
            rel = _relative_path(args.workspace, target)
            _record_full_text(
                entry,
                status="downloaded",
                file_path=rel,
                source_url=final_url,
            )
            _save_index(index_path, data)
            print(f"Downloaded PDF: {rel}")
            print(f"Updated index: {index_path}")
            return 0
        except SystemExit as exc:
            errors.append(f"{url}: {exc}")

    _record_full_text(
        entry,
        status="failed",
        reason="; ".join(errors),
    )
    _save_index(index_path, data)
    print("No PDF could be downloaded. Index marked as failed.")
    for error in errors:
        print(f"- {error}")
    return 1


def command_register(args: argparse.Namespace) -> int:
    index_path, data = _load_index(args.workspace)
    entry = _pick_entry(data, args.entry)
    source = args.file.expanduser().resolve()
    if not source.exists() or not source.is_file():
        raise SystemExit(f"PDF file not found: {source}")

    full_text_dir = args.workspace / "papers" / "full_texts"
    full_text_dir.mkdir(parents=True, exist_ok=True)
    if source.suffix.lower() != ".pdf":
        raise SystemExit("Only PDF files should be registered as full_text artifacts")

    try:
        rel = _relative_path(args.workspace, source)
        is_in_full_text_dir = source.is_relative_to(full_text_dir.resolve())
    except ValueError:
        is_in_full_text_dir = False

    if not is_in_full_text_dir:
        target = full_text_dir / (args.output_name or f"{_safe_stem(entry)}.pdf")
        shutil.copy2(source, target)
        rel = _relative_path(args.workspace, target)

    _record_full_text(
        entry,
        status="downloaded",
        file_path=rel,
        source_url=args.source_url,
    )
    _save_index(index_path, data)
    print(f"Registered PDF: {rel}")
    print(f"Updated index: {index_path}")
    return 0


def command_mark(args: argparse.Namespace) -> int:
    index_path, data = _load_index(args.workspace)
    entry = _pick_entry(data, args.entry)
    _record_full_text(
        entry,
        status=args.status,
        source_url=args.source_url,
        reason=args.reason,
    )
    _save_index(index_path, data)
    print(f"Marked entry {args.entry} as {args.status}")
    print(f"Updated index: {index_path}")
    return 0


def _is_enrichable(entry: dict[str, Any]) -> bool:
    """Check if an entry can be enriched (no PDF and not yet enriched)."""
    extra = (
        entry.get("extra_fields") if isinstance(entry.get("extra_fields"), dict) else {}
    )
    full_text = (
        extra.get("full_text") if isinstance(extra.get("full_text"), dict) else {}
    )
    status = full_text.get("status", "")
    enriched = full_text.get("enriched", False)
    # Enrichable when download failed or no candidate, and not already enriched
    return status in ("failed", "no_candidate") and not enriched


def command_enrich(args: argparse.Namespace) -> int:
    index_path, data = _load_index(args.workspace)
    entries = _entries(data)

    if args.dry_run:
        found = []
        for i, entry in enumerate(entries, 1):
            if _is_enrichable(entry):
                title = entry.get("title", "Untitled")
                ft = (entry.get("extra_fields") or {}).get("full_text") or {}
                status = ft.get("status", "")
                reason = ft.get("reason", "")
                found.append(i)
                print(f"[{i}] {title} (status: {status})")
                if reason:
                    print(f"     Reason: {reason[:120]}")
        if not found:
            print("No enrichable entries found.")
        else:
            print(f"\n{len(found)} enrichable entry/entries: {found}")
        return 0

    if args.entry:
        entry = _pick_entry(data, args.entry)
        extra = _extra(entry)
        full_text = (
            extra.get("full_text") if isinstance(extra.get("full_text"), dict) else {}
        )
        full_text["enriched"] = True
        full_text["enriched_at"] = datetime.now(timezone.utc).isoformat()
        extra["full_text"] = full_text
        _save_index(index_path, data)
        print(f"Marked entry {args.entry} as enriched")
        print(f"Updated index: {index_path}")
        return 0

    print(
        "Provide --entry N to mark an entry as enriched, or --dry-run to list enrichable entries."
    )
    return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage literature full-text PDFs")
    parser.add_argument(
        "--workspace", type=Path, default=Path("."), help="Workspace path"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    candidates = subparsers.add_parser("candidates", help="List candidate PDF URLs")
    candidates.add_argument("--entry", type=int, help="1-based literature entry number")
    candidates.set_defaults(func=command_candidates)

    download = subparsers.add_parser(
        "download", help="Download an open PDF and update index"
    )
    download.add_argument(
        "--entry", type=int, required=True, help="1-based literature entry number"
    )
    download.add_argument("--url", help="Explicit PDF URL to try first")
    download.add_argument(
        "--output-name", help="Filename to use under papers/full_texts/"
    )
    download.set_defaults(func=command_download)

    register = subparsers.add_parser("register", help="Register an existing local PDF")
    register.add_argument(
        "--entry", type=int, required=True, help="1-based literature entry number"
    )
    register.add_argument("--file", type=Path, required=True, help="PDF path")
    register.add_argument("--source-url", help="Original URL, if known")
    register.add_argument(
        "--output-name",
        help="Filename if the PDF must be copied into papers/full_texts/",
    )
    register.set_defaults(func=command_register)

    mark = subparsers.add_parser("mark", help="Record full-text status without a PDF")
    mark.add_argument(
        "--entry", type=int, required=True, help="1-based literature entry number"
    )
    mark.add_argument("--status", choices=["no_candidate", "failed"], required=True)
    mark.add_argument("--reason", help="Human-readable reason")
    mark.add_argument("--source-url", help="Candidate URL, if relevant")
    mark.set_defaults(func=command_mark)

    enrich = subparsers.add_parser(
        "enrich", help="List or mark entries enriched via web research"
    )
    enrich.add_argument(
        "--entry", type=int, help="1-based literature entry number to mark as enriched"
    )
    enrich.add_argument(
        "--dry-run",
        action="store_true",
        help="List entries that can be enriched (do not modify)",
    )
    enrich.set_defaults(func=command_enrich)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.workspace = args.workspace.expanduser().resolve()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
