"""Workspace helpers for agents.

中文：提供 agent workspace 相关的模块常量和 ``dump_json`` 工具函数。
English: Provides module-level workspace constants and the ``dump_json``
helper for agents.
"""

from __future__ import annotations

import json
from typing import Any

__all__ = [
    "AGENT_JSON_PATH",
    "STANDARD_WORKSPACE_DIRS",
    "dump_json",
]

AGENT_JSON_PATH = "AGENT.json"
STANDARD_WORKSPACE_DIRS = ("state", "memory")


def dump_json(obj: Any, *, indent: int | None = None) -> str:
    """Serialize ``obj`` to a UTF-8 JSON string (compact by default).

    Args:
        obj: JSON-serializable object.
        indent: Optional indentation.

    Returns:
        JSON string.
    """
    return json.dumps(obj, ensure_ascii=False, indent=indent, default=str)
