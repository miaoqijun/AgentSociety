"""Daily rhythm pre-step hook behavior."""

import json
import subprocess
import sys
from pathlib import Path

PKG = Path(__file__).resolve().parents[2]
SCRIPT = PKG / "agentsociety2/agent/v1_deprecated/skills/rhythm/scripts/update_rhythm.py"


def _write_state(
    tmp_path: Path,
    *,
    hunger: float,
    energy: float,
    stress: float,
    current_aoi: int = 100,
    home_aoi: int = 100,
    work_aoi: int | None = 200,
    meal_state: dict | None = None,
) -> None:
    (tmp_path / "state").mkdir(parents=True, exist_ok=True)
    (tmp_path / "state/needs.json").write_text(
        json.dumps({"needs": {"hunger": hunger, "energy": energy, "stress": stress}}),
        encoding="utf-8",
    )
    (tmp_path / "state/observation_ctx.json").write_text(
        json.dumps(
            {
                "observations": {
                    "p1": {
                        "position": {"aoi_id": current_aoi, "xy": [0, 0]},
                        "home_aoi": home_aoi,
                        "work_aoi": work_aoi,
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    if meal_state is not None:
        (tmp_path / "state/meal_state.json").write_text(
            json.dumps(meal_state), encoding="utf-8"
        )


def _run_hook(tmp_path: Path, iso_time: str) -> dict:
    proc = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--args-json",
            json.dumps({"time": iso_time, "agent_id": 7}),
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    return json.loads((tmp_path / "state/rhythm_state.json").read_text())


def test_low_energy_early_morning_recommends_sleep(tmp_path):
    _write_state(tmp_path, hunger=0.2, energy=0.18, stress=0.2)
    state = _run_hook(tmp_path, "2000-01-03T06:30:00")
    assert state["recommendation"] == "sleep"
    assert state["scores"]["sleep"] >= 0.55


def test_lunch_hunger_recommends_meal_once_per_window(tmp_path):
    _write_state(tmp_path, hunger=0.7, energy=0.7, stress=0.2, current_aoi=200)
    state = _run_hook(tmp_path, "2000-01-03T12:00:00")
    assert state["recommendation"] == "meal"
    assert state["meal_window"] == "lunch"

    _write_state(
        tmp_path,
        hunger=0.7,
        energy=0.7,
        stress=0.2,
        current_aoi=200,
        meal_state={
            "last_meal_window": "lunch",
            "last_meal_time": "2000-01-03T12:00:00",
        },
    )
    state = _run_hook(tmp_path, "2000-01-03T12:30:00")
    assert state["recommendation"] != "meal"
    assert state["scores"]["meal"] == 0.0


def test_stale_meal_window_from_previous_day_does_not_block_today(tmp_path):
    _write_state(
        tmp_path,
        hunger=0.7,
        energy=0.7,
        stress=0.2,
        current_aoi=200,
        meal_state={
            "last_meal_window": "lunch",
            "last_meal_time": "2000-01-02T12:00:00",
        },
    )
    state = _run_hook(tmp_path, "2000-01-03T12:00:00")
    assert state["recommendation"] == "meal"
    assert state["scores"]["meal"] > 0.0


def test_work_band_with_energy_recommends_work(tmp_path):
    _write_state(tmp_path, hunger=0.25, energy=0.78, stress=0.25, current_aoi=100)
    state = _run_hook(tmp_path, "2000-01-03T10:00:00")
    assert state["recommendation"] == "work"
    assert state["scores"]["work"] >= 0.55
    assert state["daily_diary"]
    assert state["scheduled_activity"]["activity"] == "work"
    assert state["norm_strength"] >= 0.7


def test_daily_schedule_keeps_low_hunger_lunch_as_work_norm(tmp_path):
    _write_state(tmp_path, hunger=0.25, energy=0.78, stress=0.25, current_aoi=200)
    state = _run_hook(tmp_path, "2000-01-03T12:00:00")
    assert state["scheduled_activity"]["activity"] == "meal"
    assert state["recommendation"] == "work"
    assert state["scores"]["meal"] <= 0.42
    assert state["social_norms"]


def test_midnight_defaults_to_sleep_even_when_energy_is_not_low(tmp_path):
    _write_state(tmp_path, hunger=0.25, energy=0.78, stress=0.20)
    state = _run_hook(tmp_path, "2000-01-03T00:00:00")
    assert state["recommendation"] == "sleep"
    assert state["scores"]["sleep"] >= 0.55


def test_work_without_work_anchor_is_only_weak_prior(tmp_path):
    _write_state(
        tmp_path,
        hunger=0.25,
        energy=0.78,
        stress=0.25,
        current_aoi=100,
        work_aoi=None,
    )
    state = _run_hook(tmp_path, "2000-01-03T10:00:00")
    assert state["recommendation"] != "work"
    assert state["scores"]["work"] <= 0.4
