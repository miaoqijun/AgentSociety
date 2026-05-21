from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


def read_text(path: Path) -> str:
    """Read a UTF-8 text file."""
    return path.read_text(encoding="utf-8")


def validate_observation_txt(path: Path) -> list[str]:
    """Validate state/observation.txt."""
    errors: list[str] = []

    if not path.exists():
        errors.append(f"Missing file: {path}")
        return errors

    content = read_text(path)
    if not content.strip():
        errors.append("state/observation.txt is empty.")

    return errors


def validate_observation_ctx(path: Path) -> list[str]:
    """Validate state/observation_ctx.json if it exists."""
    errors: list[str] = []

    if not path.exists():
        return errors

    try:
        data: Any = json.loads(read_text(path))
    except json.JSONDecodeError as exc:
        errors.append(f"state/observation_ctx.json is not valid JSON: {exc}")
        return errors

    if not isinstance(data, dict):
        errors.append("state/observation_ctx.json must contain a JSON object.")

    return errors


def validate_memory_jsonl(path: Path) -> list[str]:
    """Validate state/memory.jsonl if it exists."""
    errors: list[str] = []

    if not path.exists():
        return errors

    for line_number, line in enumerate(read_text(path).splitlines(), start=1):
        if not line.strip():
            continue

        try:
            item = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(f"Invalid JSONL at line {line_number}: {exc}")
            continue

        if not isinstance(item, dict):
            errors.append(f"Memory line {line_number} must be a JSON object.")
            continue

        if item.get("type") == "observation" and not item.get("content"):
            errors.append(f"Observation memory line {line_number} is missing content.")

    return errors


def main() -> int:
    """Validate observation artifacts in a state directory."""
    state_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("state")

    errors: list[str] = []
    errors.extend(validate_observation_txt(state_dir / "observation.txt"))
    errors.extend(validate_observation_ctx(state_dir / "observation_ctx.json"))
    errors.extend(validate_memory_jsonl(state_dir / "memory.jsonl"))

    if errors:
        print("Invalid observation artifacts:")
        for error in errors:
            print(f"- {error}")
        return 1

    print("Observation artifacts are valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
