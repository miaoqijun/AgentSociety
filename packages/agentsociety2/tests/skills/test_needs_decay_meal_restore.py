import json
import subprocess
import sys
from pathlib import Path

PKG = Path(__file__).resolve().parents[2]
SCRIPT = PKG / "agentsociety2/agent/v1_deprecated/skills/cognition/scripts/decay_needs.py"


def _run_decay(tmp_path: Path, time: str) -> dict:
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--args-json", json.dumps({"time": time})],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


def test_legacy_meal_restore_requires_actual_meal_state(tmp_path):
    state = tmp_path / "state"
    state.mkdir()
    (state / "needs.json").write_text(
        json.dumps(
            {
                "needs": {"hunger": 0.65, "energy": 0.7, "stress": 0.1},
                "last_decay_time": "2000-01-03T11:30:00",
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "_restore_intention.json").write_text(
        json.dumps({"goal": "eating out"}),
        encoding="utf-8",
    )

    result = _run_decay(tmp_path, "2000-01-03T12:00:00")
    assert result["ok"] is True
    assert not any("(meal)" in c for c in result["changes"])


def test_questionnaire_label_alone_does_not_restore_without_poi(tmp_path):
    state = tmp_path / "state"
    state.mkdir()
    (state / "needs.json").write_text(
        json.dumps(
            {
                "needs": {"hunger": 0.65, "energy": 0.7, "stress": 0.1},
                "last_decay_time": "2000-01-03T11:30:00",
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "_restore_intention.json").write_text(
        json.dumps(
            {
                "goal": "eating out",
                "source": "questionnaire",
                "time": "2000-01-03T12:00:00",
                "meal_window": "lunch",
            }
        ),
        encoding="utf-8",
    )

    result = _run_decay(tmp_path, "2000-01-03T12:00:00")
    assert result["ok"] is True
    assert not any("(meal)" in c for c in result["changes"])
    assert result["needs"]["hunger"] > 0.45


def test_meal_restore_after_recorded_poi_visit(tmp_path):
    state = tmp_path / "state"
    state.mkdir()
    (state / "needs.json").write_text(
        json.dumps(
            {
                "needs": {"hunger": 0.65, "energy": 0.7, "stress": 0.1},
                "last_decay_time": "2000-01-03T11:30:00",
            }
        ),
        encoding="utf-8",
    )
    (state / "meal_state.json").write_text(
        json.dumps(
            {
                "last_meal_window": "lunch",
                "last_meal_time": "2000-01-03T12:00:00",
                "last_meal_poi_id": 700005480,
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "_restore_intention.json").write_text(
        json.dumps(
            {
                "goal": "eating out",
                "source": "questionnaire",
                "time": "2000-01-03T12:00:00",
                "meal_window": "lunch",
            }
        ),
        encoding="utf-8",
    )

    result = _run_decay(tmp_path, "2000-01-03T12:00:00")
    assert result["ok"] is True
    assert any("(meal)" in c for c in result["changes"])
    assert result["needs"]["hunger"] == 0.18


def test_meal_restore_happens_once_per_window(tmp_path):
    state = tmp_path / "state"
    state.mkdir()
    (state / "needs.json").write_text(
        json.dumps(
            {
                "needs": {"hunger": 0.65, "energy": 0.7, "stress": 0.1},
                "last_decay_time": "2000-01-03T11:30:00",
            }
        ),
        encoding="utf-8",
    )
    (state / "meal_state.json").write_text(
        json.dumps(
            {
                "last_meal_window": "lunch",
                "last_meal_time": "2000-01-03T11:45:00",
                "last_meal_poi_id": 700005480,
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "_restore_intention.json").write_text(
        json.dumps(
            {
                "goal": "eating out",
                "meal_window": "lunch",
                "time": "2000-01-03T12:00:00",
            }
        ),
        encoding="utf-8",
    )

    first = _run_decay(tmp_path, "2000-01-03T12:00:00")
    assert any("(meal)" in c for c in first["changes"])
    assert first["needs"]["hunger"] == 0.18

    data = json.loads((state / "needs.json").read_text(encoding="utf-8"))
    data["needs"]["hunger"] = 0.65
    data["hunger"] = 0.65
    data["last_decay_time"] = "2000-01-03T12:00:00"
    (state / "needs.json").write_text(json.dumps(data), encoding="utf-8")

    second = _run_decay(tmp_path, "2000-01-03T12:30:00")
    assert not any("(meal)" in c for c in second["changes"])


def test_questionnaire_meal_restore_rejected_outside_window(tmp_path):
    state = tmp_path / "state"
    state.mkdir()
    (state / "needs.json").write_text(
        json.dumps(
            {
                "needs": {"hunger": 0.65, "energy": 0.7, "stress": 0.1},
                "last_decay_time": "2000-01-03T09:30:00",
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "_restore_intention.json").write_text(
        json.dumps(
            {
                "goal": "eating out",
                "source": "questionnaire",
                "time": "2000-01-03T10:00:00",
            }
        ),
        encoding="utf-8",
    )

    result = _run_decay(tmp_path, "2000-01-03T10:00:00")
    assert result["ok"] is True
    assert not any("(meal)" in c for c in result["changes"])
    assert result["needs"]["hunger"] > 0.45


def test_questionnaire_meal_restore_dedup_restored_windows(tmp_path):
    state = tmp_path / "state"
    state.mkdir()
    (state / "needs.json").write_text(
        json.dumps(
            {
                "needs": {"hunger": 0.65, "energy": 0.7, "stress": 0.1},
                "last_decay_time": "2000-01-03T11:30:00",
            }
        ),
        encoding="utf-8",
    )
    (state / "meal_state.json").write_text(
        json.dumps(
            {
                "restored_windows": {"2000-01-03:lunch": "2000-01-03T12:00:00"},
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "_restore_intention.json").write_text(
        json.dumps(
            {
                "goal": "eating out",
                "source": "questionnaire",
                "time": "2000-01-03T12:30:00",
                "meal_window": "lunch",
            }
        ),
        encoding="utf-8",
    )

    result = _run_decay(tmp_path, "2000-01-03T12:30:00")
    assert result["ok"] is True
    assert not any("(meal)" in c for c in result["changes"])


def test_high_hunger_outside_meal_window_still_drives_hunger(tmp_path):
    state = tmp_path / "state"
    state.mkdir()
    (state / "needs.json").write_text(
        json.dumps(
            {
                "needs": {"hunger": 0.68, "energy": 0.7, "stress": 0.1},
                "last_decay_time": "2000-01-03T09:30:00",
            }
        ),
        encoding="utf-8",
    )

    result = _run_decay(tmp_path, "2000-01-03T10:00:00")
    assert result["ok"] is True
    assert result["current_need"] == "hunger"
