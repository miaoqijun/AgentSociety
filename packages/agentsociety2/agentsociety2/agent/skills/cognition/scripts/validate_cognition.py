from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


VALID_PRIORITIES: set[str] = {"critical", "high", "medium", "low"}
VALID_SOURCES: set[str] = {"need", "observation", "memory", "plan", "social", "profile", "user"}


def read_json(path: Path) -> dict[str, Any]:
    """Read a JSON object from a file."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object.")
    return data


def validate_emotion(data: dict[str, Any]) -> list[str]:
    """Validate emotion.json."""
    errors: list[str] = []

    if not isinstance(data.get("mood"), str) or not data["mood"].strip():
        errors.append("emotion.mood must be a non-empty string.")

    needs = data.get("needs")
    if not isinstance(needs, dict):
        errors.append("emotion.needs must be an object.")
    else:
        for key, value in needs.items():
            if not isinstance(value, (int, float)) or not 0 <= float(value) <= 1:
                errors.append(f"emotion.needs.{key} must be a number in [0, 1].")

    drivers = data.get("drivers")
    if not isinstance(drivers, list) or not drivers:
        errors.append("emotion.drivers must be a non-empty list.")
    elif len(drivers) > 5:
        errors.append("emotion.drivers should contain at most 5 items.")
    elif not all(isinstance(item, str) and item.strip() for item in drivers):
        errors.append("emotion.drivers must contain non-empty strings.")

    return errors


def validate_intention(data: dict[str, Any]) -> list[str]:
    """Validate intention.json."""
    errors: list[str] = []

    if not isinstance(data.get("goal"), str) or not data["goal"].strip():
        errors.append("intention.goal must be a non-empty string.")

    if not isinstance(data.get("reason"), str) or not data["reason"].strip():
        errors.append("intention.reason must be a non-empty string.")

    if data.get("priority") not in VALID_PRIORITIES:
        errors.append(f"intention.priority must be one of {sorted(VALID_PRIORITIES)}.")

    if data.get("source") not in VALID_SOURCES:
        errors.append(f"intention.source must be one of {sorted(VALID_SOURCES)}.")

    return errors


def validate_needs_consistency(state_dir: Path, emotion: dict[str, Any]) -> list[str]:
    """Warn when emotion.needs conflicts with state/needs.json."""
    needs_path = state_dir / "needs.json"
    if not needs_path.exists():
        return []

    errors: list[str] = []
    try:
        needs = read_json(needs_path)
    except Exception as exc:
        return [f"Invalid needs.json: {exc}"]

    emotion_needs = emotion.get("needs")
    if not isinstance(emotion_needs, dict):
        return ["emotion.needs is missing while needs.json exists."]

    for key, value in needs.items():
        if not isinstance(value, (int, float)):
            continue
        other = emotion_needs.get(key)
        if isinstance(other, (int, float)) and abs(float(value) - float(other)) > 1e-6:
            errors.append(f"emotion.needs.{key} conflicts with needs.json.{key}")

    return errors


def main() -> int:
    """Validate cognition output artifacts."""
    state_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("state")

    errors: list[str] = []

    emotion_path = state_dir / "emotion.json"
    intention_path = state_dir / "intention.json"

    emotion: dict[str, Any] | None = None
    try:
        emotion = read_json(emotion_path)
        errors.extend(validate_emotion(emotion))
    except Exception as exc:
        errors.append(f"Invalid emotion.json: {exc}")

    if emotion is not None:
        errors.extend(validate_needs_consistency(state_dir, emotion))

    try:
        errors.extend(validate_intention(read_json(intention_path)))
    except Exception as exc:
        errors.append(f"Invalid intention.json: {exc}")

    if errors:
        print("Invalid cognition artifacts:")
        for error in errors:
            print(f"- {error}")
        return 1

    print("Cognition artifacts are valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
