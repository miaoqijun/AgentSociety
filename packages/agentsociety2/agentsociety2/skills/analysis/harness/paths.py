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
