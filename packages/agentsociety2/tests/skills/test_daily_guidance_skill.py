from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml

from agentsociety2.agent.person import PersonAgent

PKG_ROOT = Path(__file__).resolve().parents[2]
SKILL_ROOT = PKG_ROOT / "agentsociety2" / "agent" / "skills" / "daily-guidance"
SCRIPT = SKILL_ROOT / "scripts" / "daily_guidance.py"


def _segment(segment_id: str = "morning_work") -> dict[str, Any]:
    return {
        "id": segment_id,
        "start": "09:00",
        "end": "12:00",
        "activity": "work",
        "location_policy": "work_aoi",
        "maslow_reason": {
            "need": "esteem.role_obligation",
            "reason": "work satisfies the agent role",
            "risk": "worker profile would lack a realistic workday",
            "required": "required",
        },
        "tpb_reason": {
            "want": {
                "reason": "agent wants to complete expected work duties",
                "status": "supported",
            },
            "norm": {
                "reason": "weekday work is normal for this role",
                "status": "supported",
            },
            "can": {
                "reason": "work location is reachable from home",
                "status": "supported",
            },
            "proof": "profile occupation, weekday morning, home AOI, and work AOI support work",
            "choice": "commit",
        },
    }


def _write_yaml(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")


def _write_day(tmp_path: Path) -> Path:
    day = tmp_path / "state" / "daily_guidance" / "2026-06-12"
    _write_yaml(
        day / "story.yaml",
        {
            "story_id": "agent_0007:2026-06-12",
            "date": "2026-06-12",
            "status": "ready",
            "segments": [
                _segment("morning_work"),
                {
                    **_segment("lunch"),
                    "start": "12:00",
                    "end": "13:00",
                    "activity": "meal",
                    "maslow_reason": {
                        "need": "physiological.food",
                        "reason": "lunch keeps the day routine realistic",
                        "risk": "afternoon work loses daily-life continuity",
                        "required": "soft_required",
                    },
                },
            ],
            "self_check": {
                "maslow_result": "pass",
                "tpb_result": "pass",
                "issues": [],
            },
            "execution": {
                "current_segment_id": "morning_work",
                "completed_segments": [],
                "actual_timeline": [],
                "pending_deviation": None,
            },
            "change_log": [
                {
                    "event_id": "story_001",
                    "type": "story_created",
                    "time": "2026-06-12T06:00:00",
                    "reason": "initial daily planning",
                }
            ],
        },
    )
    return day


def _run(*args: str, cwd: Path | None = None, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def _run_hook(tmp_path: Path) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["AGENT_WORK_DIR"] = str(tmp_path)
    payload = {
        "hook_type": "pre_step",
        "time": "2026-06-12T06:00:00",
        "agent_id": 7,
        "step_count": 1,
    }
    return _run("--args-json", json.dumps(payload), env=env)


def test_person_agent_default_activates_daily_guidance() -> None:
    agent = PersonAgent(
        id=7,
        profile={"name": "Alice"},
        default_activated_skill_ids=["built-in@daily-guidance"],
    )

    assert "built-in@daily-guidance" in agent._default_activated_skill_ids  # noqa: SLF001


def test_person_agent_default_daily_guidance_can_be_disabled() -> None:
    agent = PersonAgent(
        id=8,
        profile={"name": "Disabled"},
        disabled_skill_ids=["built-in@daily-guidance"],
    )

    assert "built-in@daily-guidance" not in agent._default_activated_skill_ids  # noqa: SLF001


def test_daily_guidance_init_creates_todo_file(tmp_path: Path) -> None:
    env = os.environ.copy()
    env["AGENT_WORK_DIR"] = str(tmp_path)
    proc = _run(
        "init",
        "--agent-id",
        "7",
        "--date",
        "2026-06-12",
        env=env,
    )

    assert proc.returncode == 0, proc.stdout + proc.stderr
    result = yaml.safe_load(proc.stdout)
    assert result["ok"] is True
    assert result["next"] == "fill story.yaml, then run check --date 2026-06-12"
    story = tmp_path / "state" / "daily_guidance" / "2026-06-12" / "story.yaml"
    assert story.is_file()
    assert story.read_text(encoding="utf-8").startswith("# TODO daily-guidance")

    check = _run("check", "--date", "2026-06-12", env=env)
    assert check.returncode == 1, check.stdout + check.stderr
    check_result = yaml.safe_load(check.stdout)
    assert check_result["recommend"][0]["field"] == "story.yaml"


def test_daily_guidance_hook_creates_ready_default_story(tmp_path: Path) -> None:
    proc = _run_hook(tmp_path)

    assert proc.returncode == 0, proc.stdout + proc.stderr
    result = yaml.safe_load(proc.stdout)
    assert result["created"] is True
    assert result["ok"] is True
    assert result["active_segment"]["activity"] == "sleep"
    story = tmp_path / "state" / "daily_guidance" / "2026-06-12" / "story.yaml"
    assert yaml.safe_load(story.read_text(encoding="utf-8"))["status"] == "ready"

    second = _run_hook(tmp_path)
    second_result = yaml.safe_load(second.stdout)
    assert second_result["created"] is False
    assert second_result["ok"] is True


def test_daily_guidance_check_accepts_ready_story(tmp_path: Path) -> None:
    _write_day(tmp_path)

    env = os.environ.copy()
    env["AGENT_WORK_DIR"] = str(tmp_path)
    proc = _run("check", "--date", "2026-06-12", env=env)

    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert yaml.safe_load(proc.stdout)["ok"] is True


def test_daily_guidance_check_rejects_duplicate_segment_ids(tmp_path: Path) -> None:
    day = _write_day(tmp_path)
    story = yaml.safe_load((day / "story.yaml").read_text(encoding="utf-8"))
    story["segments"].append(story["segments"][0].copy())
    _write_yaml(day / "story.yaml", story)

    proc = _run("check", str(day / "story.yaml"))

    assert proc.returncode == 1
    assert "duplicate id" in proc.stdout


def test_daily_guidance_check_rejects_contradicted_control_commit(tmp_path: Path) -> None:
    day = _write_day(tmp_path)
    story = yaml.safe_load((day / "story.yaml").read_text(encoding="utf-8"))
    story["segments"][0]["tpb_reason"]["can"]["status"] = "contradicted"
    _write_yaml(day / "story.yaml", story)

    proc = _run("check", str(day / "story.yaml"))

    assert proc.returncode == 1
    assert "cannot commit" in proc.stdout


def test_daily_guidance_check_accepts_custom_maslow_need(tmp_path: Path) -> None:
    day = _write_day(tmp_path)
    story = yaml.safe_load((day / "story.yaml").read_text(encoding="utf-8"))
    story["segments"][0]["maslow_reason"]["need"] = "career.identity"
    _write_yaml(day / "story.yaml", story)

    proc = _run("check", str(day / "story.yaml"))

    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_daily_guidance_check_recommends_missing_fields(tmp_path: Path) -> None:
    day = _write_day(tmp_path)
    story = yaml.safe_load((day / "story.yaml").read_text(encoding="utf-8"))
    segment = story["segments"][0]
    segment.pop("start")
    segment.pop("end")
    _write_yaml(day / "story.yaml", story)

    proc = _run("check", str(day / "story.yaml"))

    assert proc.returncode == 1
    result = yaml.safe_load(proc.stdout)
    assert result["recommend"]
    assert any(item["field"] == "start" for item in result["recommend"])


def test_daily_guidance_check_rejects_non_continuous_time(tmp_path: Path) -> None:
    day = _write_day(tmp_path)
    story = yaml.safe_load((day / "story.yaml").read_text(encoding="utf-8"))
    story["segments"][1]["start"] = "12:30"
    _write_yaml(day / "story.yaml", story)

    proc = _run("check", str(day / "story.yaml"))

    assert proc.returncode == 1
    result = yaml.safe_load(proc.stdout)
    assert "previous segment end" in proc.stdout
    assert any(item["field"] == "segments[].start" for item in result["recommend"])


def test_daily_guidance_check_accepts_24_as_day_end(tmp_path: Path) -> None:
    day = _write_day(tmp_path)
    story = yaml.safe_load((day / "story.yaml").read_text(encoding="utf-8"))
    story["segments"][1]["end"] = "24:00"
    _write_yaml(day / "story.yaml", story)

    proc = _run("check", str(day / "story.yaml"))

    assert proc.returncode == 0, proc.stdout + proc.stderr


# ---------------------------------------------------------------------------
# New CLI: plan / current / show / record / revise, and clock-derived execution
# ---------------------------------------------------------------------------

def _env_at(tmp_path: Path, iso_time: str) -> dict[str, str]:
    """Env with AGENT_WORK_DIR and AGENT.json fixed at iso_time."""
    state = tmp_path / "state"
    state.mkdir(parents=True, exist_ok=True)
    (state / "agent_state.json").write_text(
        json.dumps({"agent_id": 7, "time": iso_time, "tick": 900}),
        encoding="utf-8",
    )
    (tmp_path / "AGENT.json").write_text(
        json.dumps({"agent_id": 7, "current_time": iso_time, "tick": 900}),
        encoding="utf-8",
    )
    env = os.environ.copy()
    env["AGENT_WORK_DIR"] = str(tmp_path)
    return env


def _plan_json() -> str:
    return json.dumps({
        "story_id": "agent_0007:2026-06-10",
        "date": "2026-06-10",
        "segments": [
            {**_segment("sleep_night"), "start": "00:00", "end": "07:00",
             "activity": "sleep", "location_policy": "home_aoi"},
            {**_segment("work_day"), "start": "07:00", "end": "24:00",
             "activity": "work", "location_policy": "work_aoi"},
        ],
    })


def test_plan_accepts_json_and_writes_valid_story(tmp_path: Path) -> None:
    env = _env_at(tmp_path, "2026-06-10T00:30:00")
    proc = _run("plan", "--date", "2026-06-10", "--json", _plan_json(), env=env)

    assert proc.returncode == 0, proc.stdout + proc.stderr
    result = yaml.safe_load(proc.stdout)
    assert result["ok"] is True
    # The synthesized story must pass the full validator.
    check = _run("check", "--date", "2026-06-10", env=env)
    assert check.returncode == 0, check.stdout


def test_plan_rejects_invalid_json_without_writing(tmp_path: Path) -> None:
    env = _env_at(tmp_path, "2026-06-10T00:30:00")
    proc = _run("plan", "--date", "2026-06-10", "--json", "{not valid json", env=env)

    assert proc.returncode == 0
    result = yaml.safe_load(proc.stdout)
    assert result["ok"] is False
    # Nothing should have been written.
    assert not (tmp_path / "state" / "daily_guidance" / "2026-06-10" / "story.yaml").exists()


def test_plan_missing_json_value_returns_structured_feedback(tmp_path: Path) -> None:
    env = _env_at(tmp_path, "2026-06-10T00:30:00")
    proc = _run("plan", "--date", "2026-06-10", "--json", env=env)

    assert proc.returncode == 0
    result = yaml.safe_load(proc.stdout)
    assert result["ok"] is False
    assert result["mode"] == "plan"
    assert "--json is required" in result["errors"][0]


def test_plan_rejects_discontinuous_segments(tmp_path: Path) -> None:
    env = _env_at(tmp_path, "2026-06-10T00:30:00")
    bad = json.loads(_plan_json())
    bad["segments"][1]["start"] = "08:00"  # gap after 07:00
    proc = _run("plan", "--date", "2026-06-10", "--json", json.dumps(bad), env=env)

    assert proc.returncode == 0
    result = yaml.safe_load(proc.stdout)
    assert result["ok"] is False
    assert "previous segment end" in proc.stdout


def test_plan_defaults_invalid_optional_self_check(tmp_path: Path) -> None:
    env = _env_at(tmp_path, "2026-06-10T00:30:00")
    payload = json.loads(_plan_json())
    payload["self_check"] = "pass"
    proc = _run("plan", "--date", "2026-06-10", "--json", json.dumps(payload), env=env)

    assert proc.returncode == 0, proc.stdout + proc.stderr
    story = yaml.safe_load(
        (tmp_path / "state" / "daily_guidance" / "2026-06-10" / "story.yaml").read_text(
            encoding="utf-8"
        )
    )
    assert story["self_check"] == {
        "maslow_result": "pass",
        "tpb_result": "pass",
        "issues": [],
    }


def test_plan_completes_partial_optional_self_check(tmp_path: Path) -> None:
    env = _env_at(tmp_path, "2026-06-10T00:30:00")
    payload = json.loads(_plan_json())
    payload["self_check"] = {"maslow_result": "pass"}
    proc = _run("plan", "--date", "2026-06-10", "--json", json.dumps(payload), env=env)

    assert proc.returncode == 0, proc.stdout + proc.stderr
    story = yaml.safe_load(
        (tmp_path / "state" / "daily_guidance" / "2026-06-10" / "story.yaml").read_text(
            encoding="utf-8"
        )
    )
    assert story["self_check"] == {
        "maslow_result": "pass",
        "tpb_result": "pass",
        "issues": [],
    }


def test_returns_active_segment(tmp_path: Path) -> None:
    env = _env_at(tmp_path, "2026-06-10T00:30:00")
    _run("plan", "--date", "2026-06-10", "--json", _plan_json(), env=env)
    proc = _run("current", "--date", "2026-06-10", env=env)

    assert proc.returncode == 0, proc.stdout
    result = yaml.safe_load(proc.stdout)
    assert result["current_segment"]["id"] == "sleep_night"
    assert result["current_segment"]["activity"] == "sleep"


def test_date_only_argv_defaults_to(tmp_path: Path) -> None:
    env = _env_at(tmp_path, "2026-06-10T00:30:00")
    _run("plan", "--date", "2026-06-10", "--json", _plan_json(), env=env)
    proc = _run("2026-06-10", env=env)

    assert proc.returncode == 0, proc.stdout + proc.stderr
    result = yaml.safe_load(proc.stdout)
    assert result["mode"] == "current"
    assert result["current_segment"]["id"] == "sleep_night"


def test_misordered_argv_is_normalized(tmp_path: Path) -> None:
    env = _env_at(tmp_path, "2026-06-10T00:30:00")
    _run("plan", "--date", "2026-06-10", "--json", _plan_json(), env=env)
    proc = _run("--date", "2026-06-10", "current", env=env)

    assert proc.returncode == 0, proc.stdout + proc.stderr
    result = yaml.safe_load(proc.stdout)
    assert result["mode"] == "current"
    assert result["current_segment"]["id"] == "sleep_night"


def test_redundant_skill_name_argv_is_ignored(tmp_path: Path) -> None:
    env = _env_at(tmp_path, "2026-06-10T00:30:00")
    _run("plan", "--date", "2026-06-10", "--json", _plan_json(), env=env)
    proc = _run("current", "--date", "2026-06-10", "daily_guidance", env=env)

    assert proc.returncode == 0, proc.stdout + proc.stderr
    result = yaml.safe_load(proc.stdout)
    assert result["mode"] == "current"
    assert result["current_segment"]["id"] == "sleep_night"


def test_date_activity_location_argv_defaults_to_record(tmp_path: Path) -> None:
    env = _env_at(tmp_path, "2026-06-10T00:30:00")
    _run("plan", "--date", "2026-06-10", "--json", _plan_json(), env=env)
    proc = _run(
        "--date",
        "2026-06-10",
        "--activity",
        "sleep",
        "--location",
        "home_aoi",
        env=env,
    )

    assert proc.returncode == 0, proc.stdout + proc.stderr
    result = yaml.safe_load(proc.stdout)
    assert result["mode"] == "record"
    assert result["entry"]["activity"] == "sleep"


def test_positional_date_activity_location_argv_defaults_to_record(tmp_path: Path) -> None:
    env = _env_at(tmp_path, "2026-06-10T00:30:00")
    _run("plan", "--date", "2026-06-10", "--json", _plan_json(), env=env)
    proc = _run(
        "2026-06-10",
        "--activity",
        "sleep",
        "--location",
        "home_aoi",
        "--note",
        "Continuing sleep segment, 12:30 AM",
        env=env,
    )

    assert proc.returncode == 0, proc.stdout + proc.stderr
    result = yaml.safe_load(proc.stdout)
    assert result["mode"] == "record"
    assert result["entry"]["activity"] == "sleep"
    assert result["entry"]["note"] == "Continuing sleep segment, 12:30 AM"


def test_misordered_record_argv_is_normalized(tmp_path: Path) -> None:
    env = _env_at(tmp_path, "2026-06-10T00:30:00")
    _run("plan", "--date", "2026-06-10", "--json", _plan_json(), env=env)
    proc = _run(
        "--date",
        "2026-06-10",
        "record",
        "--activity",
        "sleep",
        "--location",
        "home_aoi",
        env=env,
    )

    assert proc.returncode == 0, proc.stdout + proc.stderr
    result = yaml.safe_load(proc.stdout)
    assert result["mode"] == "record"


def test_option_first_record_argv_is_normalized(tmp_path: Path) -> None:
    env = _env_at(tmp_path, "2026-06-10T00:30:00")
    _run("plan", "--date", "2026-06-10", "--json", _plan_json(), env=env)
    proc = _run(
        "--activity",
        "sleep",
        "--location",
        "home_aoi",
        "--note",
        "Continuing night sleep at home",
        "--date",
        "2026-06-10",
        env=env,
    )

    assert proc.returncode == 0, proc.stdout + proc.stderr
    result = yaml.safe_load(proc.stdout)
    assert result["mode"] == "record"
    assert result["entry"]["activity"] == "sleep"
    assert result["entry"]["note"] == "Continuing night sleep at home"


def test_repeated_record_token_is_ignored(tmp_path: Path) -> None:
    env = _env_at(tmp_path, "2026-06-10T00:30:00")
    _run("plan", "--date", "2026-06-10", "--json", _plan_json(), env=env)
    proc = _run(
        "record",
        "--date",
        "2026-06-10",
        "record",
        "--activity",
        "sleep",
        "--location",
        "home_aoi",
        "--note",
        "continuing night sleep",
        env=env,
    )

    assert proc.returncode == 0, proc.stdout + proc.stderr
    result = yaml.safe_load(proc.stdout)
    assert result["mode"] == "record"
    assert result["entry"]["activity"] == "sleep"


def test_split_note_argv_is_coalesced(tmp_path: Path) -> None:
    env = _env_at(tmp_path, "2026-06-10T00:30:00")
    _run("plan", "--date", "2026-06-10", "--json", _plan_json(), env=env)
    proc = _run(
        "--date",
        "2026-06-10",
        "--activity",
        "sleep",
        "--location",
        "home_aoi",
        "--note",
        "continuing",
        "night",
        "sleep",
        env=env,
    )

    assert proc.returncode == 0, proc.stdout + proc.stderr
    result = yaml.safe_load(proc.stdout)
    assert result["mode"] == "record"
    assert result["entry"]["note"] == "continuing night sleep"


def test_date_json_argv_defaults_to_plan(tmp_path: Path) -> None:
    env = _env_at(tmp_path, "2026-06-10T00:30:00")
    proc = _run("--date", "2026-06-10", "--json", _plan_json(), env=env)

    assert proc.returncode == 0, proc.stdout + proc.stderr
    result = yaml.safe_load(proc.stdout)
    assert result["mode"] == "plan"


def test_misordered_show_argv_is_normalized(tmp_path: Path) -> None:
    env = _env_at(tmp_path, "2026-06-10T00:30:00")
    _run("plan", "--date", "2026-06-10", "--json", _plan_json(), env=env)
    proc = _run("--date", "2026-06-10", "show", env=env)

    assert proc.returncode == 0, proc.stdout + proc.stderr
    result = yaml.safe_load(proc.stdout)
    assert result["mode"] == "show"


def test_plan_args_json_alias_is_normalized(tmp_path: Path) -> None:
    env = _env_at(tmp_path, "2026-06-10T00:30:00")
    proc = _run("plan", "--date", "2026-06-10", "--args-json", _plan_json(), env=env)

    assert proc.returncode == 0, proc.stdout + proc.stderr
    result = yaml.safe_load(proc.stdout)
    assert result["mode"] == "plan"


def test_plan_trailing_date_is_ignored(tmp_path: Path) -> None:
    env = _env_at(tmp_path, "2026-06-10T00:30:00")
    proc = _run(
        "plan",
        "--date",
        "2026-06-10",
        "--json",
        _plan_json(),
        "2026-06-10",
        env=env,
    )

    assert proc.returncode == 0, proc.stdout + proc.stderr
    result = yaml.safe_load(proc.stdout)
    assert result["mode"] == "plan"


def test_plan_split_json_argv_is_coalesced(tmp_path: Path) -> None:
    env = _env_at(tmp_path, "2026-06-10T00:30:00")
    split_json = _plan_json().split(" ")
    proc = _run(
        "plan",
        "--date",
        "2026-06-10",
        "--json",
        *split_json,
        env=env,
    )

    assert proc.returncode == 0, proc.stdout + proc.stderr
    result = yaml.safe_load(proc.stdout)
    assert result["mode"] == "plan"


def test_completion_is_derived_from_clock(tmp_path: Path) -> None:
    # At 00:30 nothing is complete; advancing to 09:00 auto-completes sleep_night.
    env_early = _env_at(tmp_path, "2026-06-10T00:30:00")
    _run("plan", "--date", "2026-06-10", "--json", _plan_json(), env=env_early)

    show_early = yaml.safe_load(
        _run("show", "--date", "2026-06-10", env=env_early).stdout
    )
    assert show_early["active_segment"] == "sleep_night"
    assert show_early["completed_count"] == 0

    env_late = _env_at(tmp_path, "2026-06-10T09:00:00")
    show_late = yaml.safe_load(
        _run("show", "--date", "2026-06-10", env=env_late).stdout
    )
    assert show_late["active_segment"] == "work_day"
    assert show_late["completed_count"] == 1


def test_record_appends_to_actual_timeline(tmp_path: Path) -> None:
    env = _env_at(tmp_path, "2026-06-10T09:00:00")
    _run("plan", "--date", "2026-06-10", "--json", _plan_json(), env=env)
    proc = _run("record", "--date", "2026-06-10", "--activity", "work",
                "--location", "work_aoi", "--note", "at office", env=env)

    assert proc.returncode == 0, proc.stdout
    result = yaml.safe_load(proc.stdout)
    assert result["ok"] is True
    assert result["entry"]["activity"] == "work"
    assert result["timeline_size"] == 1


def test_record_is_idempotent_for_same_time_activity_and_location(tmp_path: Path) -> None:
    env = _env_at(tmp_path, "2026-06-10T09:00:00")
    _run("plan", "--date", "2026-06-10", "--json", _plan_json(), env=env)
    first = _run(
        "record",
        "--date",
        "2026-06-10",
        "--activity",
        "work",
        "--location",
        "work_aoi",
        "--note",
        "at office",
        env=env,
    )
    second = _run(
        "record",
        "--date",
        "2026-06-10",
        "--activity",
        "work",
        "--location",
        "work_aoi",
        "--note",
        "still at office",
        env=env,
    )

    assert first.returncode == 0, first.stdout + first.stderr
    assert second.returncode == 0, second.stdout + second.stderr
    result = yaml.safe_load(second.stdout)
    assert result["duplicate"] is True
    assert result["timeline_size"] == 1
    story = yaml.safe_load(
        (tmp_path / "state" / "daily_guidance" / "2026-06-10" / "story.yaml").read_text(
            encoding="utf-8"
        )
    )
    assert len(story["execution"]["actual_timeline"]) == 1


def test_revise_replaces_tail_and_revalidates(tmp_path: Path) -> None:
    env = _env_at(tmp_path, "2026-06-10T12:00:00")
    _run("plan", "--date", "2026-06-10", "--json", _plan_json(), env=env)

    new_tail = json.dumps([
        {**_segment("work_day"), "start": "07:00", "end": "18:00",
         "activity": "work", "location_policy": "work_aoi"},
        {**_segment("evening"), "start": "18:00", "end": "24:00",
         "activity": "leisure", "location_policy": "near_home_aoi",
         "maslow_reason": {"need": "recovery.leisure", "reason": "relax",
                           "risk": "stress", "required": "optional"}},
    ])
    proc = _run("revise", "--date", "2026-06-10", "--from", "work_day",
                "--json", new_tail, env=env)

    assert proc.returncode == 0, proc.stdout
    result = yaml.safe_load(proc.stdout)
    assert result["total_segments"] == 3
    # Story must still be valid after the revision.
    assert _run("check", "--date", "2026-06-10", env=env).returncode == 0


def test_revise_accepts_single_segment_object_as_local_patch(tmp_path: Path) -> None:
    env = _env_at(tmp_path, "2026-06-10T00:30:00")
    _run("plan", "--date", "2026-06-10", "--json", _plan_json(), env=env)

    patch = {
        **_segment("midnight_meal"),
        "start": "00:00",
        "end": "01:00",
        "activity": "meal",
        "location_policy": "near_home_aoi",
        "maslow_reason": {
            "need": "physiological.food",
            "reason": "hungry before sleeping",
            "risk": "going to bed hungry is uncomfortable",
            "required": "soft_required",
        },
    }
    proc = _run(
        "revise",
        "--date",
        "2026-06-10",
        "--from",
        "sleep_night",
        "--json",
        json.dumps(patch),
        env=env,
    )

    assert proc.returncode == 0, proc.stdout + proc.stderr
    story = yaml.safe_load(
        (tmp_path / "state" / "daily_guidance" / "2026-06-10" / "story.yaml").read_text(
            encoding="utf-8"
        )
    )
    assert [seg["id"] for seg in story["segments"]] == [
        "midnight_meal",
        "sleep_night_after_patch",
        "work_day",
    ]
    assert story["segments"][1]["start"] == "01:00"
    assert story["segments"][1]["end"] == "07:00"
    assert _run("check", "--date", "2026-06-10", env=env).returncode == 0


def test_date_from_json_argv_defaults_to_revise(tmp_path: Path) -> None:
    env = _env_at(tmp_path, "2026-06-10T00:30:00")
    _run("plan", "--date", "2026-06-10", "--json", _plan_json(), env=env)

    patch = {
        **_segment("midnight_meal"),
        "start": "00:00",
        "end": "01:00",
        "activity": "meal",
        "location_policy": "near_home_aoi",
    }
    proc = _run(
        "--date",
        "2026-06-10",
        "--from",
        "sleep_night",
        "--json",
        json.dumps(patch),
        env=env,
    )

    assert proc.returncode == 0, proc.stdout + proc.stderr
    result = yaml.safe_load(proc.stdout)
    assert result["mode"] == "revise"


def test_revise_accepts_segments_wrapper_and_infers_from_time(tmp_path: Path) -> None:
    env = _env_at(tmp_path, "2026-06-10T19:30:00")
    _run("plan", "--date", "2026-06-10", "--json", _plan_json(), env=env)

    replacement = {
        "segments": [
            {
                **_segment("dinner"),
                "start": "19:00",
                "end": "20:00",
                "activity": "meal",
                "location_policy": "near_home_aoi",
            },
            {
                **_segment("sleep_late"),
                "start": "20:00",
                "end": "24:00",
                "activity": "sleep",
                "location_policy": "home_aoi",
            },
        ]
    }
    proc = _run(
        "revise",
        "--date",
        "2026-06-10",
        "--from",
        "dinner",
        "--json",
        json.dumps(replacement),
        env=env,
    )

    assert proc.returncode == 0, proc.stdout + proc.stderr
    story = yaml.safe_load(
        (tmp_path / "state" / "daily_guidance" / "2026-06-10" / "story.yaml").read_text(
            encoding="utf-8"
        )
    )
    assert [seg["id"] for seg in story["segments"]] == [
        "sleep_night",
        "work_day_before_patch",
        "dinner",
        "sleep_late",
    ]
    assert story["segments"][1]["start"] == "07:00"
    assert story["segments"][1]["end"] == "19:00"
    assert _run("check", "--date", "2026-06-10", env=env).returncode == 0


def test_hook_injects_active_segment_when_story_ready(tmp_path: Path) -> None:
    env = _env_at(tmp_path, "2026-06-10T00:30:00")
    _run("plan", "--date", "2026-06-10", "--json", _plan_json(), env=env)

    payload = {"hook_type": "pre_step", "time": "2026-06-10T00:30:00",
               "agent_id": 7, "step_count": 1}
    proc = _run("--args-json", json.dumps(payload), env=env)

    assert proc.returncode == 0, proc.stdout
    result = yaml.safe_load(proc.stdout)
    assert result["ok"] is True
    assert result["active_segment"]["activity"] == "sleep"
    assert "guidance" in result


def test_hook_without_payload_uses_agent_json_sim_date(tmp_path: Path) -> None:
    env = _env_at(tmp_path, "2000-01-01T00:30:00")
    proc = _run(env=env)

    assert proc.returncode == 0, proc.stdout + proc.stderr
    result = yaml.safe_load(proc.stdout)
    assert result["date"] == "2000-01-01"
    assert (tmp_path / "state" / "daily_guidance" / "2000-01-01" / "story.yaml").exists()
    assert not (tmp_path / "state" / "daily_guidance" / "2026-06-14").exists()


def test_plan_corrects_date_to_sim_clock_without_wrong_directory(tmp_path: Path) -> None:
    env = _env_at(tmp_path, "2000-01-01T00:30:00")
    payload = json.loads(_plan_json())
    payload["story_id"] = "agent_0007:2000-01-02"
    payload["date"] = "2000-01-02"
    proc = _run("plan", "--date", "2000-01-02", "--json", json.dumps(payload), env=env)

    assert proc.returncode == 0, proc.stdout + proc.stderr
    result = yaml.safe_load(proc.stdout)
    assert result["ok"] is True
    assert result["corrected_date"]["from"] == "2000-01-02"
    assert result["corrected_date"]["to"] == "2000-01-01"
    story_path = tmp_path / "state" / "daily_guidance" / "2000-01-01" / "story.yaml"
    assert story_path.exists()
    story = yaml.safe_load(story_path.read_text(encoding="utf-8"))
    assert story["date"] == "2000-01-01"
    assert story["story_id"] == "agent_0007:2000-01-01"
    assert not (tmp_path / "state" / "daily_guidance" / "2000-01-02").exists()


def test_unknown_command_lists_valid_choices(tmp_path: Path) -> None:
    env = _env_at(tmp_path, "2026-06-10T00:30:00")
    proc = _run("update", "--date", "2026-06-10", env=env)

    assert proc.returncode != 0
    # argparse prints the valid command set to stderr.
    assert "plan" in proc.stderr and "current" in proc.stderr
