#!/usr/bin/env python3
"""Experiment progress tracker for AgentSociety research workflows.

Manages a single workspace governance file: `.agentsociety/progress.json`.

Usage:
    python progress.py <command> [options]

Commands:
    status              Show current progress summary
    init                Initialize progress.json for a workspace
    update-stage        Update a pipeline stage's status
    set-verification    Set a stage verification status
    next-action         Suggest the next recommended action
    where-am-i          Determine current pipeline position (with legacy fallback)
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

STAGE_ORDER = [
    "literature_search",
    "hypothesis",
    "experiment_config",
    "run_experiment",
    "analysis",
    "generate_paper",
]

VALID_STATUSES = {"not_started", "in_progress", "completed", "failed", "skipped"}
VERIFICATION_STATUSES = {"not_started", "partial", "complete"}

PROGRESS_VERSION = "1.2"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _progress_path(workspace: Path) -> Path:
    return workspace / ".agentsociety" / "progress.json"


def _make_empty_stage_state() -> dict[str, Any]:
    return {
        "status": "not_started",
        "started_at": None,
        "completed_at": None,
        "attempts": 0,
        "error": None,
        "metadata": {},
        "verification_status": "not_started",
    }


def _make_empty_stages() -> dict[str, dict[str, Any]]:
    return {stage: _make_empty_stage_state() for stage in STAGE_ORDER}


def _default_progress(topic: str = "") -> dict[str, Any]:
    return {
        "version": PROGRESS_VERSION,
        "workspace": {
            "topic": topic,
            "created_at": _now_iso(),
            "current_stage": "literature_search",
            "current_hypothesis_id": None,
            "current_experiment_id": None,
        },
        "stages": _make_empty_stages(),
        "hypotheses": {},
    }


def _normalize_progress_data(data: dict[str, Any] | None) -> dict[str, Any]:
    normalized = _default_progress()
    if isinstance(data, dict):
        normalized.update({k: v for k, v in data.items() if k not in {"workspace", "stages"}})

        workspace = normalized["workspace"]
        existing_workspace = data.get("workspace", {}) if isinstance(data.get("workspace"), dict) else {}
        workspace.update(existing_workspace)
        if workspace.get("current_stage") not in STAGE_ORDER:
            workspace["current_stage"] = "literature_search"

        normalized_stages = normalized["stages"]
        existing_stages = data.get("stages", {}) if isinstance(data.get("stages"), dict) else {}
        for stage in STAGE_ORDER:
            state = _make_empty_stage_state()
            state.update(existing_stages.get(stage, {}))
            if state.get("status") not in VALID_STATUSES:
                state["status"] = "not_started"
            if state.get("verification_status") not in VERIFICATION_STATUSES:
                state["verification_status"] = "not_started"
            if not isinstance(state.get("metadata"), dict):
                state["metadata"] = {}
            # Drop legacy fields that older progress.json files may carry.
            state.pop("gate_status", None)
            normalized_stages[stage] = state

    normalized["version"] = PROGRESS_VERSION
    if not isinstance(normalized.get("hypotheses"), dict):
        normalized["hypotheses"] = {}
    return normalized


def _read_progress(workspace: Path) -> dict[str, Any] | None:
    data = _read_json(_progress_path(workspace))
    if data is None:
        return None
    return _normalize_progress_data(data)


def _write_progress(workspace: Path, data: dict[str, Any]) -> None:
    _write_json(_progress_path(workspace), _normalize_progress_data(data))


def _compute_next_actions(progress: dict[str, Any]) -> list[dict[str, Any]]:
    workspace = progress["workspace"]
    stage = workspace["current_stage"]
    stage_state = progress["stages"][stage]

    return [
        {
            "kind": "continue",
            "title": f"Continue {stage}",
            "reason": f"stage status is {stage_state['status']}",
            "stage": stage,
            "priority": "medium",
        }
    ]


# ── Commands ──────────────────────────────────────────────────────────


def cmd_init(args: argparse.Namespace) -> int:
    progress_path = _progress_path(args.workspace)
    if progress_path.exists() and not args.force:
        print(f"progress.json already exists: {progress_path}")
        return 1

    _write_progress(args.workspace, _default_progress(args.topic or ""))
    print(f"Initialized progress tracking in {args.workspace / '.agentsociety/'}")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    progress = _read_progress(args.workspace)
    if progress is None:
        print("No progress.json found. Run 'init' first.")
        return 1

    if args.json:
        payload = dict(progress)
        payload["next_recommended_actions"] = _compute_next_actions(progress)
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0

    workspace = progress["workspace"]
    current_stage = workspace["current_stage"]
    current_stage_state = progress["stages"][current_stage]
    print(f"Topic: {workspace['topic'] or '(not set)'}")
    print(f"Current stage: {current_stage}")
    print(f"Verification: {current_stage_state['verification_status']}")
    if workspace.get("current_hypothesis_id"):
        print(f"Current hypothesis: {workspace['current_hypothesis_id']}")
    if workspace.get("current_experiment_id"):
        print(f"Current experiment: {workspace['current_experiment_id']}")

    print()
    marker_map = {
        "completed": "+",
        "in_progress": ">",
        "failed": "!",
        "skipped": "-",
        "not_started": " ",
    }
    for stage_name in STAGE_ORDER:
        stage = progress["stages"].get(stage_name, {})
        status = stage.get("status", "unknown")
        marker = marker_map.get(status, "?")
        line = f"  [{marker}] {stage_name}: {status}"
        if stage.get("attempts", 0) > 1:
            line += f" ({stage['attempts']} attempts)"
        if stage.get("error"):
            line += f" — {stage['error']}"
        print(line)

    return 0


def cmd_update_stage(args: argparse.Namespace) -> int:
    progress = _read_progress(args.workspace)
    if progress is None:
        print("No progress.json found. Run 'init' first.")
        return 1

    if args.stage not in STAGE_ORDER:
        print(f"Unknown stage: {args.stage}. Valid: {', '.join(STAGE_ORDER)}")
        return 1
    if args.status not in VALID_STATUSES:
        print(f"Invalid status: {args.status}. Valid: {', '.join(sorted(VALID_STATUSES))}")
        return 1

    stage = progress["stages"][args.stage]
    prev_status = stage["status"]
    stage["status"] = args.status

    if (
        args.status != prev_status
        and prev_status != "in_progress"
        and args.status in {"in_progress", "completed", "failed"}
    ):
        stage["attempts"] += 1

    now = _now_iso()
    if args.status == "in_progress" and prev_status != "in_progress":
        stage["started_at"] = now
        stage["completed_at"] = None
    if args.status in {"completed", "failed", "skipped"}:
        stage["completed_at"] = now
    if args.error:
        stage["error"] = args.error
    if args.status == "completed":
        stage["error"] = None
    if args.verification_status:
        stage["verification_status"] = args.verification_status

    if args.metadata:
        try:
            stage["metadata"].update(json.loads(args.metadata))
        except json.JSONDecodeError as exc:
            print(f"Invalid metadata JSON: {exc}")
            return 1

    if args.status == "completed":
        idx = STAGE_ORDER.index(args.stage)
        if idx + 1 < len(STAGE_ORDER):
            progress["workspace"]["current_stage"] = STAGE_ORDER[idx + 1]
    elif args.status == "in_progress":
        progress["workspace"]["current_stage"] = args.stage

    _write_progress(args.workspace, progress)
    print(f"Updated {args.stage}: {prev_status} → {args.status}")
    return 0


def cmd_set_verification(args: argparse.Namespace) -> int:
    progress = _read_progress(args.workspace)
    if progress is None:
        print("No progress.json found. Run 'init' first.")
        return 1

    if args.stage not in STAGE_ORDER:
        print(f"Unknown stage: {args.stage}. Valid: {', '.join(STAGE_ORDER)}")
        return 1
    if args.verification_status not in VERIFICATION_STATUSES:
        print(
            "Invalid verification status: "
            f"{args.verification_status}. Valid: {', '.join(sorted(VERIFICATION_STATUSES))}"
        )
        return 1

    progress["stages"][args.stage]["verification_status"] = args.verification_status
    _write_progress(args.workspace, progress)
    print(f"Updated verification for {args.stage}: {args.verification_status}")
    return 0


def cmd_next_action(args: argparse.Namespace) -> int:
    progress = _read_progress(args.workspace)
    if progress is None:
        print("No progress.json found. Run 'init' first.")
        return 1

    actions = _compute_next_actions(progress)

    if args.json:
        print(
            json.dumps(
                {
                    "current_stage": progress["workspace"]["current_stage"],
                    "actions": actions,
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        return 0

    print(f"Current stage: {progress['workspace']['current_stage']}")
    for action in actions:
        print(f"- [{action['priority']}] {action['title']}")
        if action.get("reason"):
            print(f"  {action['reason']}")
    return 0


def _detect_stage_from_files(workspace: Path) -> str:
    """Fallback: determine stage from file existence for legacy workspaces."""
    if not (workspace / "TOPIC.md").exists():
        return "literature_search"

    literature_index = workspace / "papers" / "literature_index.json"
    if not literature_index.exists():
        return "literature_search"
    try:
        index = json.loads(literature_index.read_text(encoding="utf-8"))
        if not index.get("papers"):
            return "literature_search"
    except Exception:
        return "literature_search"

    hypothesis_dirs = sorted(workspace.glob("hypothesis_*/HYPOTHESIS.md"))
    if not hypothesis_dirs:
        return "hypothesis"

    config_files = sorted(workspace.glob("hypothesis_*/experiment_*/init/init_config.json"))
    if not config_files:
        return "experiment_config"

    db_files = sorted(workspace.glob("hypothesis_*/experiment_*/run/sqlite.db"))
    if not db_files:
        return "run_experiment"

    report_files = sorted(workspace.glob("presentation/hypothesis_*/report.md"))
    if not report_files:
        return "analysis"

    return "generate_paper"


def cmd_where_am_i(args: argparse.Namespace) -> int:
    progress = _read_progress(args.workspace)

    if progress is not None:
        workspace = progress["workspace"]
        stage = workspace["current_stage"]
        stage_info = progress["stages"].get(stage, {})
        result = {
            "source": "progress.json",
            "current_stage": stage,
            "topic": workspace.get("topic", ""),
            "current_hypothesis_id": workspace.get("current_hypothesis_id"),
            "current_experiment_id": workspace.get("current_experiment_id"),
            "stage_status": stage_info.get("status", "unknown"),
            "stage_attempts": stage_info.get("attempts", 0),
            "verification_status": stage_info.get("verification_status", "not_started"),
            "next_recommended_actions": _compute_next_actions(progress),
        }
        if stage_info.get("error"):
            result["stage_error"] = stage_info["error"]
    else:
        stage = _detect_stage_from_files(args.workspace)
        result = {
            "source": "file_detection",
            "current_stage": stage,
            "note": "No progress.json found. Detected from workspace files.",
        }

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"Current stage: {result['current_stage']}")
        print(f"Source: {result['source']}")
        if result.get("current_hypothesis_id"):
            print(f"Current hypothesis: {result['current_hypothesis_id']}")
        if result.get("current_experiment_id"):
            print(f"Current experiment: {result['current_experiment_id']}")
        if result.get("verification_status"):
            print(f"Verification: {result['verification_status']}")
        if result.get("stage_error"):
            print(f"Stage error: {result['stage_error']}")

    return 0


# ── Main ──────────────────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(description="AgentSociety experiment progress tracker")
    parser.add_argument("--workspace", type=Path, default=Path("."), help="Workspace root path")
    sub = parser.add_subparsers(dest="command")

    p_init = sub.add_parser("init", help="Initialize progress.json")
    p_init.add_argument("--topic", help="Research topic")
    p_init.add_argument("--force", action="store_true", help="Overwrite existing progress.json")

    p_status = sub.add_parser("status", help="Show current progress summary")
    p_status.add_argument("--json", action="store_true", help="JSON output")

    p_update = sub.add_parser("update-stage", help="Update a stage's status")
    p_update.add_argument("stage", help="Stage name")
    p_update.add_argument("status", help="New status")
    p_update.add_argument("--error", help="Error message (for failed status)")
    p_update.add_argument("--metadata", help="JSON metadata to merge")
    p_update.add_argument(
        "--verification-status",
        choices=sorted(VERIFICATION_STATUSES),
        help="Optional verification status to set together with the stage update",
    )

    p_verify = sub.add_parser("set-verification", help="Update a stage verification status")
    p_verify.add_argument("stage", help="Stage name")
    p_verify.add_argument("verification_status", help="Verification status")

    p_next = sub.add_parser("next-action", help="Suggest the next recommended action")
    p_next.add_argument("--json", action="store_true", help="JSON output")

    p_wai = sub.add_parser("where-am-i", help="Determine current pipeline position")
    p_wai.add_argument("--json", action="store_true", help="JSON output")

    args = parser.parse_args()
    if args.command is None:
        parser.print_help()
        return 1

    commands = {
        "init": cmd_init,
        "status": cmd_status,
        "update-stage": cmd_update_stage,
        "set-verification": cmd_set_verification,
        "next-action": cmd_next_action,
        "where-am-i": cmd_where_am_i,
    }

    return commands[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())
