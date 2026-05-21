from __future__ import annotations

import json
import math
import os
import sys
from pathlib import Path
from typing import Any


IMPORTANCE_BOOST: dict[str, float] = {
    "high": 2.0,
    "medium": 1.0,
    "low": 0.6,
}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    """Read a JSONL memory file."""
    if not path.exists():
        return []

    entries: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        if isinstance(item, dict):
            entries.append(item)

    return entries


def write_jsonl(path: Path, entries: list[dict[str, Any]]) -> None:
    """Write memory entries as JSONL."""
    path.parent.mkdir(parents=True, exist_ok=True)
    content = "\n".join(json.dumps(entry, ensure_ascii=False, separators=(",", ":")) for entry in entries)
    if content:
        content += "\n"
    path.write_text(content, encoding="utf-8")


def get_tick(entry: dict[str, Any]) -> int | None:
    """Return an integer tick from a memory entry if available."""
    tick = entry.get("tick")
    return tick if isinstance(tick, int) else None


def estimate_retention(entry: dict[str, Any], current_tick: int) -> float:
    """Estimate retention using decay with importance and repetition boosts."""
    strength = float(os.getenv("AGENT_MEMORY_STRENGTH", "20.0"))
    decay = float(os.getenv("AGENT_MEMORY_ACTR_DECAY", "0.5"))

    tick = get_tick(entry)
    age = max(0, current_tick - tick) if tick is not None else 0

    importance = str(entry.get("importance", "medium"))
    importance_boost = IMPORTANCE_BOOST.get(importance, 1.0)

    repetitions = entry.get("_repetitions", 1)
    if not isinstance(repetitions, int) or repetitions < 1:
        repetitions = 1

    repetition_boost = 1.0 + math.log1p(repetitions)
    effective_strength = strength * importance_boost * repetition_boost

    return effective_strength / (effective_strength + (age + 1) ** decay)


def maintain_memory(memory_file: Path, current_tick: int) -> list[dict[str, Any]]:
    """Apply retention scoring and prune weak memory entries."""
    threshold = float(os.getenv("AGENT_MEMORY_RETRIEVAL_THRESHOLD", "0.25"))
    max_entries = int(os.getenv("AGENT_MEMORY_MAX_ENTRIES", "200"))

    entries = read_jsonl(memory_file)
    maintained: list[dict[str, Any]] = []

    for entry in entries:
        retention = estimate_retention(entry, current_tick)
        entry["_retention"] = round(retention, 4)
        entry["_faded"] = retention < threshold

        if retention >= threshold or entry.get("importance") == "high":
            maintained.append(entry)

    maintained.sort(
        key=lambda item: (
            0 if item.get("importance") == "high" else 1,
            -float(item.get("_retention", 0.0)),
            -(get_tick(item) or 0),
        )
    )

    maintained = maintained[:max_entries]
    maintained.sort(key=lambda item: get_tick(item) if get_tick(item) is not None else -1)

    write_jsonl(memory_file, maintained)
    return maintained


def parse_args() -> tuple[Path, int]:
    """Parse CLI arguments (SkillRegistry uses ``--args-json``)."""
    if len(sys.argv) >= 3 and sys.argv[1] == "--args-json":
        payload = json.loads(sys.argv[2])
        if not isinstance(payload, dict):
            raise SystemExit("--args-json must decode to a JSON object")
        memory_file = Path(str(payload.get("memory_file", "state/memory.jsonl")))
        tick = payload.get("current_tick", payload.get("tick", 0))
        return memory_file, int(tick)

    if len(sys.argv) == 2 and sys.argv[1].strip().startswith("{"):
        payload = json.loads(sys.argv[1])
        memory_file = Path(str(payload.get("memory_file", "state/memory.jsonl")))
        tick = payload.get("current_tick", payload.get("tick", 0))
        return memory_file, int(tick)

    if len(sys.argv) >= 3:
        return Path(sys.argv[1]), int(sys.argv[2])

    raise SystemExit(
        "Usage: memory_maintenance.py --args-json '{\"memory_file\":...,\"current_tick\":N}' "
        "or memory_maintenance.py <memory_file> <current_tick>"
    )


def main() -> int:
    """Run memory maintenance."""
    memory_file, current_tick = parse_args()
    maintained = maintain_memory(memory_file, current_tick)
    print(f"Maintained {len(maintained)} memory entries.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
