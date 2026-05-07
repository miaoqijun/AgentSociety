"""CRUD for ``artifacts/evidence_backlog.{md,json}``."""

from __future__ import annotations

import json
from typing import List, Optional

from agentsociety2.skills.paper.models import EvidenceBacklog, EvidenceGap
from agentsociety2.skills.paper.paths import (
    PathLike,
    artifacts_dir,
    evidence_backlog_json_path,
    evidence_backlog_md_path,
)


def load(workspace_path: PathLike) -> Optional[EvidenceBacklog]:
    path = evidence_backlog_json_path(workspace_path)
    if not path.exists():
        return None
    raw = json.loads(path.read_text(encoding="utf-8"))
    return EvidenceBacklog.model_validate(raw)


def save(workspace_path: PathLike, backlog: EvidenceBacklog) -> None:
    artifacts_dir(workspace_path).mkdir(parents=True, exist_ok=True)
    evidence_backlog_json_path(workspace_path).write_text(
        json.dumps(backlog.model_dump(mode="json"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    evidence_backlog_md_path(workspace_path).write_text(
        render_markdown(backlog),
        encoding="utf-8",
    )


def render_markdown(backlog: EvidenceBacklog) -> str:
    lines: list[str] = ["# Evidence Backlog", ""]
    if not backlog.items:
        lines.append("_Backlog is empty._")
        return "\n".join(lines) + "\n"
    by_priority = {"high": [], "medium": [], "low": []}
    for item in backlog.items:
        by_priority.setdefault(item.priority, []).append(item)
    for priority in ("high", "medium", "low"):
        items = by_priority.get(priority, [])
        if not items:
            continue
        lines.append(f"## Priority: {priority}")
        for item in items:
            tag = []
            if item.auto_executable:
                tag.append("auto-exec")
            if item.human_gated:
                tag.append("human-gate")
            tag_str = f" ({', '.join(tag)})" if tag else ""
            lines.append(
                f"- **{item.gap_id}** [{item.category}]{tag_str}: {item.description}"
            )
            if item.related_claim_ids:
                lines.append(
                    "  - claims: " + ", ".join(item.related_claim_ids)
                )
            if item.notes:
                lines.append(f"  - notes: {item.notes}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def filter_auto_executable(backlog: EvidenceBacklog) -> List[EvidenceGap]:
    """Return items the orchestrator may auto-execute (not human-gated)."""

    return [
        item
        for item in backlog.items
        if item.auto_executable and not item.human_gated
    ]


def filter_human_gated(backlog: EvidenceBacklog) -> List[EvidenceGap]:
    return [item for item in backlog.items if item.human_gated]


def by_priority(backlog: EvidenceBacklog, priority: str) -> List[EvidenceGap]:
    return [item for item in backlog.items if item.priority == priority]


def exists(workspace_path: PathLike) -> bool:
    return evidence_backlog_json_path(workspace_path).exists()


__all__ = [
    "load",
    "save",
    "render_markdown",
    "filter_auto_executable",
    "filter_human_gated",
    "by_priority",
    "exists",
]
