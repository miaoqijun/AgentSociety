#!/usr/bin/env python3
"""Memory maintenance script for forgetting curve implementation.

Implements Ebbinghaus forgetting curve with configurable parameters.
Run periodically to decay old memories and reinforce frequently accessed ones.

Usage:
    python memory_maintenance.py --memory-file state/memory.jsonl --current-tick 100
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional


def json_loads(s: str) -> Any:
    """Load JSON with repair fallback."""
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        import json_repair

        return json_repair.loads(s)


def json_dumps(obj: Any, indent: int | None = 2) -> str:
    """Dump JSON with consistent formatting."""
    return json.dumps(obj, ensure_ascii=False, indent=indent, default=str)


@dataclass
class ForgettingConfig:
    """Configuration for memory forgetting curve.

    All parameters can be overridden via environment variables or arguments.
    """

    # Memory strength coefficient (ticks)
    strength_coefficient: float = float(os.getenv("AGENT_MEMORY_STRENGTH", "100"))

    # Retention thresholds
    fade_threshold: float = float(os.getenv("AGENT_MEMORY_FADE_THRESHOLD", "0.1"))
    remove_threshold: float = float(os.getenv("AGENT_MEMORY_REMOVE_THRESHOLD", "0.05"))

    # Reinforcement
    reinforce_amount: float = float(os.getenv("AGENT_MEMORY_REINFORCE_AMOUNT", "0.1"))
    max_reinforce: float = float(os.getenv("AGENT_MEMORY_MAX_REINFORCE", "0.95"))

    # Importance multipliers
    importance_multipliers: dict[str, float] = field(
        default_factory=lambda: {
            "high": 1.5,
            "medium": 1.0,
            "low": 0.5,
        }
    )

    # Maximum memories to keep
    max_memories: int = int(os.getenv("AGENT_MEMORY_MAX_ENTRIES", "1000"))


@dataclass
class MemoryEntry:
    """Represents a single memory entry with forgetting state."""

    raw: dict[str, Any]
    tick: int
    importance: str
    retention: float = 1.0
    access_count: int = 0
    last_access_tick: int = 0

    @classmethod
    def from_dict(cls, data: dict[str, Any], current_tick: int) -> "MemoryEntry":
        """Create MemoryEntry from raw dict."""
        return cls(
            raw=data,
            tick=data.get("tick", current_tick),
            importance=data.get("importance", "medium"),
            retention=data.get("_retention", 1.0),
            access_count=data.get("_access_count", 0),
            last_access_tick=data.get("_last_access_tick", current_tick),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict for serialization (preserves internal state)."""
        result = dict(self.raw)
        result["_retention"] = self.retention
        result["_access_count"] = self.access_count
        result["_last_access_tick"] = self.last_access_tick
        return result

    def compute_retention(self, current_tick: int, config: ForgettingConfig) -> float:
        """Compute retention based on Ebbinghaus forgetting curve.

        Formula: retention = e^(-t / (S * importance_multiplier))

        Where:
        - t = ticks since creation
        - S = strength coefficient
        - importance_multiplier = high:1.5, medium:1.0, low:0.5
        """
        t = current_tick - self.tick
        if t <= 0:
            return self.retention

        multiplier = config.importance_multipliers.get(self.importance, 1.0)
        S = config.strength_coefficient * multiplier

        retention = math.exp(-t / S)

        # Apply reinforcement from previous access
        if self.access_count > 0:
            retention = min(
                retention + (self.access_count * 0.05), config.max_reinforce
            )

        return retention

    def reinforce(self, current_tick: int, config: ForgettingConfig) -> None:
        """Reinforce this memory (called when accessed)."""
        self.access_count += 1
        self.last_access_tick = current_tick
        self.retention = min(
            self.retention + config.reinforce_amount, config.max_reinforce
        )


class MemoryMaintenance:
    """Memory maintenance manager with forgetting curve."""

    def __init__(self, memory_path: Path, config: ForgettingConfig | None = None):
        self.memory_path = memory_path
        self.config = config or ForgettingConfig()

    def load_memories(self) -> list[MemoryEntry]:
        """Load all memories from file."""
        if not self.memory_path.exists():
            return []

        memories = []
        with self.memory_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json_loads(line)
                    memories.append(MemoryEntry.from_dict(data, 0))
                except Exception:
                    continue

        return memories

    def save_memories(self, memories: list[MemoryEntry]) -> None:
        """Save memories back to file."""
        self.memory_path.parent.mkdir(parents=True, exist_ok=True)
        with self.memory_path.open("w", encoding="utf-8") as f:
            for m in memories:
                f.write(json_dumps(m.to_dict(), indent=None) + "\n")

    def run_maintenance(
        self,
        current_tick: int,
        accessed_tags: Optional[set[str]] = None,
    ) -> dict[str, Any]:
        """Run memory maintenance: decay old memories, remove forgotten ones.

        :param current_tick: Current simulation tick.
        :param accessed_tags: Tags of memories that were recently accessed (for reinforcement).
        :returns: Statistics about the maintenance operation.
        """
        memories = self.load_memories()

        stats = {
            "total_before": len(memories),
            "faded": 0,
            "removed": 0,
            "reinforced": 0,
            "total_after": 0,
        }

        # 1. Compute retention for each memory
        for m in memories:
            m.retention = m.compute_retention(current_tick, self.config)

        # 2. Reinforce accessed memories
        if accessed_tags:
            for m in memories:
                tags = set(m.raw.get("tags", []))
                if tags & accessed_tags:
                    m.reinforce(current_tick, self.config)
                    stats["reinforced"] += 1

        # 3. Filter out forgotten memories
        kept = []
        for m in memories:
            if m.retention < self.config.remove_threshold:
                stats["removed"] += 1
            elif m.retention < self.config.fade_threshold:
                # Mark as faded but keep
                m.raw["_faded"] = True
                stats["faded"] += 1
                kept.append(m)
            else:
                # Remove faded marker if recovered
                m.raw.pop("_faded", None)
                kept.append(m)

        # 4. If still over limit, remove lowest retention
        if len(kept) > self.config.max_memories:
            kept.sort(key=lambda m: m.retention, reverse=True)
            removed_extra = len(kept) - self.config.max_memories
            stats["removed"] += removed_extra
            kept = kept[: self.config.max_memories]

        stats["total_after"] = len(kept)

        # 5. Save back
        self.save_memories(kept)

        return stats


def main():
    parser = argparse.ArgumentParser(
        description="Memory maintenance with forgetting curve"
    )
    parser.add_argument(
        "--memory-file",
        type=str,
        required=True,
        help="Path to memory.jsonl file",
    )
    parser.add_argument(
        "--current-tick",
        type=int,
        required=True,
        help="Current simulation tick",
    )
    parser.add_argument(
        "--accessed-tags",
        type=str,
        default="",
        help="Comma-separated list of accessed tags for reinforcement",
    )
    parser.add_argument(
        "--strength",
        type=float,
        default=float(os.getenv("AGENT_MEMORY_STRENGTH", "100")),
        help="Memory strength coefficient",
    )
    parser.add_argument(
        "--max-memories",
        type=int,
        default=int(os.getenv("AGENT_MEMORY_MAX_ENTRIES", "1000")),
        help="Maximum memories to keep",
    )

    args = parser.parse_args()

    config = ForgettingConfig(
        strength_coefficient=args.strength,
        max_memories=args.max_memories,
    )

    maintenance = MemoryMaintenance(Path(args.memory_file), config)

    accessed_tags = set()
    if args.accessed_tags:
        accessed_tags = set(
            t.strip() for t in args.accessed_tags.split(",") if t.strip()
        )

    stats = maintenance.run_maintenance(args.current_tick, accessed_tags)

    print(
        json_dumps(
            {
                "ok": True,
                "stats": stats,
                "config": {
                    "strength_coefficient": config.strength_coefficient,
                    "fade_threshold": config.fade_threshold,
                    "remove_threshold": config.remove_threshold,
                    "max_memories": config.max_memories,
                },
            }
        )
    )


if __name__ == "__main__":
    main()
