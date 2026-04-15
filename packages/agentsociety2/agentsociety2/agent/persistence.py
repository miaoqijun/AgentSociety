"""Agent持久化模块。

整合检查点、预写日志、清理和会话恢复功能。

模块结构
========

- :class:`Checkpoint`: 检查点管理，支持崩溃恢复
- :class:`WriteAheadLog`: 预写日志（追加写入 + 内存索引）
- :class:`WorkspaceCleaner`: 工作区清理
- :class:`SessionRecovery`: 会话恢复上下文构建

性能优化
========

WriteAheadLog 采用追加日志 + 内存索引架构：

1. **追加写入**: log_intent 只追加，不重写文件
2. **内存索引**: 维护 intent_id -> offset 映射
3. **延迟压缩**: 超过 max_entries 时自动压缩

示例
====

基本使用::

    from agentsociety2.agent.persistence import Checkpoint, WriteAheadLog

    # 检查点
    checkpoint = Checkpoint(workspace, config)
    checkpoint.save(tick=100, state={"step_count": 42})
    data = checkpoint.restore(100)

    # 预写日志
    wal = WriteAheadLog(workspace, max_entries=1000)
    intent_id = wal.log_intent("workspace_write", {"path": "test.txt"}, tick=1)
    wal.log_result(intent_id, {"ok": True})
    pending = wal.get_pending()
"""

from __future__ import annotations

import gzip
import json
import shutil
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Optional

import json_repair

from .config import AgentConfig


def _json_dumps(obj: Any, indent: int | None = 2) -> str:
    """JSON序列化辅助函数。

    :param obj: 要序列化的对象。
    :param indent: 缩进级别。
    :return: JSON字符串。
    """
    return json.dumps(obj, ensure_ascii=False, indent=indent, default=str)


class IntentStatus(str, Enum):
    """意图状态枚举。"""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class Checkpoint:
    """检查点管理器。

    支持保存和恢复Agent在特定tick的完整状态。
    """

    def __init__(self, workspace: Path, config: AgentConfig):
        self.workspace = workspace
        self.config = config
        self.dir = workspace / "checkpoints"
        self.dir.mkdir(parents=True, exist_ok=True)

    def _path(self, tick: int) -> Path:
        return self.dir / f"checkpoint_{tick}.json"

    def save(self, tick: int, state: dict[str, Any]) -> Path:
        """保存检查点。"""
        data = {
            "tick": tick,
            "timestamp": datetime.now().isoformat(),
            "state": state,
        }
        path = self._path(tick)
        path.write_text(_json_dumps(data), encoding="utf-8")
        self._cleanup()
        return path

    def restore(self, tick: int) -> Optional[dict[str, Any]]:
        """恢复检查点。"""
        path = self._path(tick)
        if not path.exists():
            return None
        return json_repair.loads(path.read_text(encoding="utf-8"))

    def latest_tick(self) -> Optional[int]:
        """获取最新检查点的tick。"""
        checkpoints = sorted(self.dir.glob("checkpoint_*.json"))
        if not checkpoints:
            return None
        # 从文件名解析tick
        name = checkpoints[-1].stem
        parts = name.split("_")
        if len(parts) >= 2 and parts[1].isdigit():
            return int(parts[1])
        return None

    def _cleanup(self) -> None:
        """清理旧检查点。"""
        checkpoints = sorted(self.dir.glob("checkpoint_*.json"))
        while len(checkpoints) > self.config.persistence.checkpoint_max:
            checkpoints[0].unlink()
            checkpoints = checkpoints[1:]


class WriteAheadLog:
    """预写日志管理器。

    在工具执行前记录意图，执行后记录结果。
    使用追加日志 + 内存索引，避免全量文件重写。

    Attributes:
        path: 日志文件路径。
        index_path: 索引文件路径。
        max_entries: 最大保留条目数。
    """

    def __init__(self, workspace: Path, max_entries: int = 1000):
        """初始化 WAL。

        :param workspace: 工作区根目录。
        :param max_entries: 最大保留条目数。
        """
        self.path = workspace / "wal" / "wal.jsonl"
        self.index_path = workspace / "wal" / "index.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.max_entries = max_entries
        self._counter = 0
        self._index: dict[str, int] = self._load_index()
        self._pending: dict[str, dict[str, Any]] = {}

    def _load_index(self) -> dict[str, int]:
        """从磁盘加载索引。

        :return: intent_id -> 文件偏移量 的字典。
        """
        if not self.index_path.exists():
            return {}
        try:
            data = json_repair.loads(self.index_path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return {k: int(v) for k, v in data.items() if isinstance(v, (int, str))}
        except Exception:
            pass
        return {}

    def _save_index(self) -> None:
        """保存索引到磁盘。"""
        self.index_path.write_text(
            _json_dumps(self._index, indent=None), encoding="utf-8"
        )

    def log_intent(self, action: str, arguments: dict[str, Any], tick: int) -> str:
        """记录执行意图，返回意图ID。

        追加写入，不重写文件。

        :param action: 工具名称。
        :param arguments: 工具参数。
        :param tick: 当前 tick。
        :return: 意图 ID。
        """
        self._counter += 1
        intent_id = f"intent_{tick}_{self._counter}"
        intent = {
            "intent_id": intent_id,
            "action": action,
            "arguments": arguments,
            "tick": tick,
            "timestamp": datetime.now().isoformat(),
            "status": IntentStatus.PENDING.value,
        }

        # 追加写入
        entry = _json_dumps(intent) + "\n"
        offset = self.path.stat().st_size if self.path.exists() else 0
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(entry)

        # 更新索引
        self._index[intent_id] = offset
        self._pending[intent_id] = intent
        self._save_index()
        self._maybe_compact()

        return intent_id

    def log_result(self, intent_id: str, result: dict[str, Any]) -> None:
        """记录执行结果。

        使用追加写入而非重写，通过内存索引追踪最新状态。

        :param intent_id: 意图 ID。
        :param result: 执行结果。
        """
        # 追加结果记录
        result_entry = {
            "intent_id": intent_id,
            "status": IntentStatus.COMPLETED.value,
            "result": result,
            "timestamp": datetime.now().isoformat(),
        }

        entry = _json_dumps(result_entry) + "\n"
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(entry)

        # 从内存 pending 中移除
        self._pending.pop(intent_id, None)

    def get_pending(self) -> list[dict[str, Any]]:
        """获取待处理意图列表。

        :return: 待处理意图列表。
        """
        return list(self._pending.values())

    def _maybe_compact(self) -> None:
        """当条目数超过限制时压缩文件。

        保留最近 max_entries 条记录。
        """
        total_entries = len(self._index)
        if total_entries <= self.max_entries:
            return

        try:
            # 读取所有行
            lines = self.path.read_text(encoding="utf-8").strip().split("\n")
            if len(lines) <= self.max_entries:
                return

            # 保留最近条目，重建索引
            recent_lines = lines[-self.max_entries :]
            self.path.write_text("\n".join(recent_lines) + "\n", encoding="utf-8")

            # 重建索引
            self._index.clear()
            offset = 0
            for line in recent_lines:
                try:
                    data = json_repair.loads(line)
                    intent_id = data.get("intent_id")
                    if intent_id:
                        self._index[intent_id] = offset
                except Exception:
                    pass
                offset += len(line.encode("utf-8")) + 1

            self._save_index()
        except Exception:
            pass


class WorkspaceCleaner:
    """工作区清理器。"""

    def __init__(self, workspace: Path, config: AgentConfig):
        self.workspace = workspace
        self.config = config

    def cleanup(self) -> dict[str, Any]:
        """执行清理。"""
        stats = {"files_removed": 0, "bytes_freed": 0}

        # 清理日志
        log_dir = self.workspace / "logs"
        if log_dir.exists():
            logs = sorted(
                log_dir.glob("*.log"), key=lambda p: p.stat().st_mtime, reverse=True
            )
            for log in logs[self.config.persistence.max_log_files :]:
                stats["bytes_freed"] += log.stat().st_size
                log.unlink()
                stats["files_removed"] += 1

        # 清理检查点
        cp_dir = self.workspace / "checkpoints"
        if cp_dir.exists():
            cps = sorted(
                cp_dir.glob("checkpoint_*.json"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
            for cp in cps[self.config.persistence.checkpoint_max :]:
                stats["bytes_freed"] += cp.stat().st_size
                cp.unlink()
                stats["files_removed"] += 1

        # 归档旧文件
        archive_threshold = datetime.now() - timedelta(
            days=self.config.persistence.archive_after_days
        )
        archive_dir = self.workspace / "archive"
        archive_dir.mkdir(exist_ok=True)

        if log_dir.exists():
            for log_file in log_dir.glob("*.log"):
                mtime = datetime.fromtimestamp(log_file.stat().st_mtime)
                if mtime < archive_threshold:
                    archive_path = archive_dir / f"{log_file.name}.gz"
                    with open(log_file, "rb") as f_in:
                        with gzip.open(archive_path, "wb") as f_out:
                            shutil.copyfileobj(f_in, f_out)
                    log_file.unlink()

        return stats

    def disk_usage(self) -> dict[str, Any]:
        """获取磁盘使用情况。"""
        total = 0
        counts: dict[str, int] = {}
        for path in self.workspace.rglob("*"):
            if path.is_file():
                total += path.stat().st_size
                ext = path.suffix or "no_ext"
                counts[ext] = counts.get(ext, 0) + 1
        return {
            "total_bytes": total,
            "total_mb": round(total / 1024 / 1024, 2),
            "counts": counts,
        }


class SessionRecovery:
    """会话恢复上下文构建器。"""

    def __init__(self, workspace: Path, checkpoint: Checkpoint):
        self.workspace = workspace
        self.checkpoint = checkpoint

    def build_context(self, current_tick: int) -> str:
        """构建恢复上下文。"""
        parts = []

        latest = self.checkpoint.latest_tick()
        if latest is not None:
            parts.append(f"**Last Checkpoint**: tick {latest}")
            if latest < current_tick:
                parts.append(f"**Ticks Since**: {current_tick - latest}")

        ctx_path = self.workspace / "AGENT_CONTEXT.md"
        if ctx_path.exists():
            content = ctx_path.read_text(encoding="utf-8")
            if content:
                parts.append(f"**Context**:\n{content[:500]}")

        state_summary = self._state_summary()
        if state_summary:
            parts.append(f"**State**:\n{state_summary}")

        return "\n\n".join(parts) if parts else ""

    def _state_summary(self) -> str:
        """构建状态摘要（动态发现所有状态文件）。"""
        summaries = []
        state_dir = self.workspace / "state"
        if not state_dir.exists():
            return ""

        for path in sorted(state_dir.glob("*.json")):
            try:
                data = json_repair.loads(path.read_text())
                key = path.stem
                # 找第一个字符串值作为摘要
                for v in data.values():
                    if isinstance(v, str) and v:
                        summaries.append(f"- {key}: {v[:50]}")
                        break
            except Exception:
                pass

        return "\n".join(summaries)
