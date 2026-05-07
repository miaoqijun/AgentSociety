"""CRUD for ``artifacts/storyline_map.{md,json}`` pair."""

from __future__ import annotations

import json
from typing import Optional

from agentsociety2.skills.paper.models import StorylineMap
from agentsociety2.skills.paper.paths import (
    PathLike,
    artifacts_dir,
    storyline_json_path,
    storyline_md_path,
)


def load(workspace_path: PathLike) -> Optional[StorylineMap]:
    """Load from JSON; return ``None`` if no storyline has been written."""

    path = storyline_json_path(workspace_path)
    if not path.exists():
        return None
    raw = json.loads(path.read_text(encoding="utf-8"))
    return StorylineMap.model_validate(raw)


def save(workspace_path: PathLike, storyline: StorylineMap) -> None:
    """Persist both JSON (canonical) and rendered Markdown."""

    artifacts_dir(workspace_path).mkdir(parents=True, exist_ok=True)
    storyline_json_path(workspace_path).write_text(
        json.dumps(storyline.model_dump(mode="json"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    storyline_md_path(workspace_path).write_text(
        render_markdown(storyline),
        encoding="utf-8",
    )


def render_markdown(storyline: StorylineMap) -> str:
    """Human-readable rendering of the storyline map."""

    lines: list[str] = ["# Storyline Map", ""]
    if storyline.angle_version:
        lines.append(f"_Angle version: v{storyline.angle_version}_")
        lines.append("")

    def _section(heading: str, body: str) -> None:
        if not body:
            return
        lines.append(f"## {heading}")
        lines.append(body.strip())
        lines.append("")

    _section("Main Question", storyline.main_question)
    _section("Core Tension", storyline.core_tension)
    _section("Why Now", storyline.why_now)
    _section("Contribution Statement", storyline.contribution_statement)
    _section("Current Angle", storyline.current_angle)

    if storyline.rejected_angles:
        lines.append("## Rejected Angles")
        for entry in storyline.rejected_angles:
            lines.append(f"- {entry}")
        lines.append("")

    if storyline.kill_criteria:
        lines.append("## Kill Criteria")
        for entry in storyline.kill_criteria:
            lines.append(f"- {entry}")
        lines.append("")

    if storyline.section_logic:
        lines.append("## Section Logic")
        for sec in storyline.section_logic:
            lines.append(f"### {sec.section}")
            if sec.purpose:
                lines.append(f"_Purpose:_ {sec.purpose}")
            for kp in sec.key_points:
                lines.append(f"- {kp}")
            lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def exists(workspace_path: PathLike) -> bool:
    return storyline_json_path(workspace_path).exists()


__all__ = [
    "load",
    "save",
    "render_markdown",
    "exists",
]
