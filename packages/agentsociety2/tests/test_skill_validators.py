"""Builtin agent skill output validators."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from agentsociety2.agent.init_utils import init_emotion_state, init_intention_state

PKG_ROOT = Path(__file__).resolve().parents[1]
SKILLS_ROOT = PKG_ROOT / "agentsociety2" / "agent" / "skills"


def _run_validator(script_rel: str, arg: str) -> subprocess.CompletedProcess[str]:
    script = SKILLS_ROOT / script_rel
    return subprocess.run(
        [sys.executable, str(script), arg],
        capture_output=True,
        text=True,
        check=False,
    )


def test_validate_cognition_accepts_skill_schema(tmp_path: Path) -> None:
    state = tmp_path / "state"
    state.mkdir()
    (state / "emotion.json").write_text(
        json.dumps(init_emotion_state(mood="concerned"), ensure_ascii=False),
        encoding="utf-8",
    )
    (state / "intention.json").write_text(
        json.dumps(
            init_intention_state(
                goal="eat available food",
                reason="satiety low",
                priority="critical",
                source="need",
            ),
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    proc = _run_validator("cognition/scripts/validate_cognition.py", str(state))
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_validate_plan_state_accepts_schema(tmp_path: Path) -> None:
    path = tmp_path / "plan_state.json"
    path.write_text(
        json.dumps(
            {
                "goal": "buy groceries",
                "steps": ["walk to store", "pay"],
                "current_step": 0,
                "started_tick": 1,
                "status": "in_progress",
                "decision_mode": "system2",
                "failure_count": 0,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    proc = _run_validator("plan/scripts/validate_plan_state.py", str(path))
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_validate_memory_requires_tags(tmp_path: Path) -> None:
    path = tmp_path / "memory.jsonl"
    path.write_text(
        json.dumps(
            {
                "tick": 1,
                "type": "event",
                "summary": "Met Alice.",
                "tags": ["alice", "social"],
                "importance": "medium",
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    proc = _run_validator("memory/scripts/validate_memory.py", str(path))
    assert proc.returncode == 0, proc.stdout + proc.stderr


@pytest.mark.parametrize(
    "rel_path",
    [
        "cognition/references/emotion_schema.json",
        "cognition/references/intention_schema.json",
        "plan/references/plan_state_schema.json",
    ],
)
def test_skill_schema_files_exist(rel_path: str) -> None:
    path = SKILLS_ROOT / rel_path
    assert path.is_file()
    schema = json.loads(path.read_text(encoding="utf-8"))
    assert schema.get("type") == "object"
    assert schema.get("required")
