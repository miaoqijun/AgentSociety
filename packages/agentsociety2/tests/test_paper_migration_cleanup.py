from __future__ import annotations

import importlib
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[3]


def test_research_skills_package_no_longer_exports_deleted_paper_module() -> None:
    skills = importlib.import_module("agentsociety2.skills")

    assert "paper" not in skills.__all__
    assert not hasattr(skills, "paper")
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("agentsociety2.skills.paper")


def test_workspace_launcher_no_longer_dispatches_deleted_paper_skills() -> None:
    text = (REPO_ROOT / "extension/runtime/agentsociety/bin/ags.py").read_text(
        encoding="utf-8"
    )

    assert "agentsociety-paper-orchestrator" not in text
    assert "agentsociety-paper-adapter" not in text
    assert '"paper-orchestrator"' not in text
    assert '"paper-adapter"' not in text


def test_research_workflow_docs_route_paper_work_to_external_toolkit() -> None:
    checked_files = [
        REPO_ROOT / "extension/skills/agentsociety-research-pipeline/v1.0.0/SKILL.md",
        REPO_ROOT / "extension/src/workspaceManager.ts",
        REPO_ROOT / "packages/agentsociety2/docs/skills.rst",
        REPO_ROOT / "packages/agentsociety2/docs/api/skills.rst",
    ]

    for path in checked_files:
        text = path.read_text(encoding="utf-8")
        assert "agentsociety-paper-orchestrator" not in text
        assert "agentsociety-paper-adapter" not in text
        assert "agentsociety2.skills.paper" not in text

    pipeline_text = checked_files[0].read_text(encoding="utf-8")
    assert "paper-toolkit" in pipeline_text


def test_no_stale_in_tree_paper_skill_references_remain() -> None:
    checked_roots = [
        REPO_ROOT / "packages/agentsociety2/agentsociety2",
        REPO_ROOT / "packages/agentsociety2/docs",
        REPO_ROOT / "extension/skills",
        REPO_ROOT / "extension/runtime",
        REPO_ROOT / "extension/src",
        REPO_ROOT / "extension/DEVELOPMENT.md",
    ]
    stale_terms = [
        "agentsociety2.skills.paper",
        "agentsociety-paper-orchestrator",
        "agentsociety-paper-adapter",
        "paper-orchestrator",
        "paper-adapter",
    ]
    offenders: list[str] = []

    for root in checked_roots:
        paths = [root] if root.is_file() else root.rglob("*")
        for path in paths:
            if not path.is_file():
                continue
            if "__pycache__" in path.parts or "locale" in path.parts or "_build" in path.parts:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            for term in stale_terms:
                if term in text:
                    offenders.append(f"{path.relative_to(REPO_ROOT)}: {term}")

    assert offenders == []
