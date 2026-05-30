from __future__ import annotations

from pathlib import Path

from agentsociety2.skills.analysis.harness.layout import (
    FILE_CLAIMS,
    FILE_PLAN,
    FILE_STATE,
    hypothesis_harness_dir,
    synthesis_harness_dir,
)

hypothesis_analysis_dir = hypothesis_harness_dir


def hypothesis_state_path(workspace: Path, hypothesis_id: str) -> Path:
    return hypothesis_harness_dir(workspace, hypothesis_id) / FILE_STATE


def hypothesis_plan_path(workspace: Path, hypothesis_id: str) -> Path:
    return hypothesis_harness_dir(workspace, hypothesis_id) / FILE_PLAN


def hypothesis_claims_path(workspace: Path, hypothesis_id: str) -> Path:
    return hypothesis_harness_dir(workspace, hypothesis_id) / FILE_CLAIMS


def synthesis_analysis_dir(workspace: Path) -> Path:
    return synthesis_harness_dir(workspace)


def synthesis_state_path(workspace: Path) -> Path:
    return synthesis_harness_dir(workspace) / FILE_STATE


def hypothesis_report_review_path(workspace: Path, hypothesis_id: str) -> Path:
    return hypothesis_harness_dir(workspace, hypothesis_id) / "report_review.json"


def synthesis_report_review_path(workspace: Path) -> Path:
    return synthesis_harness_dir(workspace) / "synthesis_review.json"


def memory_dir(workspace: Path) -> Path:
    return workspace / ".agentsociety" / "memory"


def reflection_dir(workspace: Path) -> Path:
    return memory_dir(workspace) / "reflections"


def hypothesis_reflection_path(workspace: Path, hypothesis_id: str) -> Path:
    return reflection_dir(workspace) / f"hypothesis_{hypothesis_id}.json"


def synthesis_reflection_path(workspace: Path) -> Path:
    return reflection_dir(workspace) / "synthesis.json"


def hypothesis_feedback_path(workspace: Path, hypothesis_id: str) -> Path:
    return reflection_dir(workspace) / f"hypothesis_{hypothesis_id}_feedback.json"


def synthesis_feedback_path(workspace: Path) -> Path:
    return reflection_dir(workspace) / "synthesis_feedback.json"


def hypothesis_reflection_review_path(workspace: Path, hypothesis_id: str) -> Path:
    return reflection_dir(workspace) / f"hypothesis_{hypothesis_id}_review.json"


def synthesis_reflection_review_path(workspace: Path) -> Path:
    return reflection_dir(workspace) / "synthesis_review.json"


def memory_index_path(workspace: Path) -> Path:
    return memory_dir(workspace) / "memory_index.yaml"


def project_lessons_path(workspace: Path) -> Path:
    return memory_dir(workspace) / "project_lessons.jsonl"


def method_recipes_dir(workspace: Path) -> Path:
    return memory_dir(workspace) / "method_recipes"
