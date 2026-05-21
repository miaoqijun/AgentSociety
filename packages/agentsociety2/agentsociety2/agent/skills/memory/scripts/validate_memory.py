from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


VALID_TYPES: set[str] = {
    "need",
    "emotion",
    "cognition",
    "intention",
    "plan",
    "plan_execution",
    "react",
    "event",
    "observation",
    "social",
    "decision",
    "discovery",
    "plan_outcome",
}

VALID_IMPORTANCE: set[str] = {"high", "medium", "low"}


def validate_entry(entry: dict[str, Any], line_number: int) -> list[str]:
    """Validate a single memory entry."""
    errors: list[str] = []

    entry_type = entry.get("type")
    if entry_type not in VALID_TYPES:
        errors.append(f"line {line_number}: invalid type: {entry_type}")

    summary = entry.get("summary")
    if not isinstance(summary, str) or not summary.strip():
        errors.append(f"line {line_number}: summary must be a non-empty string")

    tags = entry.get("tags")
    if not isinstance(tags, list) or not 2 <= len(tags) <= 5:
        errors.append(f"line {line_number}: tags must contain 2-5 items")
    elif not all(isinstance(tag, str) and tag.strip() for tag in tags):
        errors.append(f"line {line_number}: all tags must be non-empty strings")

    importance = entry.get("importance")
    if importance not in VALID_IMPORTANCE:
        errors.append(f"line {line_number}: invalid importance: {importance}")

    tick = entry.get("tick")
    if tick is not None and not isinstance(tick, int):
        errors.append(f"line {line_number}: tick must be an integer if present")

    return errors


def validate_memory_file(path: Path) -> list[str]:
    """Validate a memory JSONL file."""
    errors: list[str] = []

    if not path.exists():
        return errors

    latest_summary: str | None = None

    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue

        try:
            entry = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(f"line {line_number}: invalid JSON: {exc}")
            continue

        if not isinstance(entry, dict):
            errors.append(f"line {line_number}: entry must be a JSON object")
            continue

        errors.extend(validate_entry(entry, line_number))

        summary = entry.get("summary")
        if isinstance(summary, str):
            normalized = summary.strip().lower()
            if latest_summary == normalized:
                errors.append(f"line {line_number}: duplicates previous summary")
            latest_summary = normalized

    return errors


def main() -> int:
    """Validate state/memory.jsonl."""
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("state/memory.jsonl")
    errors = validate_memory_file(path)

    if errors:
        print("Invalid memory file:")
        for error in errors:
            print(f"- {error}")
        return 1

    print("Memory file is valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
