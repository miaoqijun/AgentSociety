from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


VALID_STATUSES: set[str] = {
    "pending",
    "in_progress",
    "completed",
    "failed",
    "interrupted",
}


def load_json(path: Path) -> dict[str, Any]:
    """Load a JSON object from the given path."""
    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    if not isinstance(data, dict):
        raise ValueError("plan_state.json must contain a JSON object.")

    return data


def validate_plan_state(data: dict[str, Any]) -> list[str]:
    """Validate the structure of plan_state.json and return error messages."""
    errors: list[str] = []

    goal = data.get("goal")
    if not isinstance(goal, str) or not goal.strip():
        errors.append("`goal` must be a non-empty string.")

    steps = data.get("steps")
    if not isinstance(steps, list) or not steps:
        errors.append("`steps` must be a non-empty list.")
    elif len(steps) > 6:
        errors.append("`steps` must contain no more than 6 steps.")
    elif not all(isinstance(step, str) and step.strip() for step in steps):
        errors.append("Every step must be a non-empty string.")

    current_step = data.get("current_step")
    if not isinstance(current_step, int) or current_step < 0:
        errors.append("`current_step` must be a non-negative integer.")
    elif isinstance(steps, list) and steps and current_step >= len(steps):
        errors.append("`current_step` must be within the range of `steps`.")

    status = data.get("status")
    if status not in VALID_STATUSES:
        errors.append(f"`status` must be one of: {sorted(VALID_STATUSES)}.")

    decision_mode = data.get("decision_mode")
    if decision_mode != "system2":
        errors.append("`decision_mode` must be `system2`.")

    failure_count = data.get("failure_count")
    if not isinstance(failure_count, int) or failure_count < 0:
        errors.append("`failure_count` must be a non-negative integer.")

    return errors


def main() -> int:
    """Validate a plan_state.json file."""
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("state/plan_state.json")

    try:
        data = load_json(path)
        errors = validate_plan_state(data)
    except Exception as exc:
        print(f"Invalid plan state: {exc}")
        return 1

    if errors:
        print("Invalid plan state:")
        for error in errors:
            print(f"- {error}")
        return 1

    print("Plan state is valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
