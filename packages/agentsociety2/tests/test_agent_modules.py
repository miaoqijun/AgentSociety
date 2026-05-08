"""持久化、并发和上下文模块的单元测试。"""

import asyncio
import json

import pytest

from agentsociety2.agent.skills import SkillRegistry
from agentsociety2.agent.persistence import (
    Checkpoint,
    WriteAheadLog,
)
from agentsociety2.agent.concurrent import (
    Priority,
    PriorityScheduler,
    ParallelExecutor,
    RateLimiter,
    TaskManager,
    DeadlockDetector,
)
from agentsociety2.agent.context import AgentMemory
from agentsociety2.agent.config import AgentConfig


class TestSkillRegistry:
    """SkillRegistry 内置技能脚本发现与执行测试。"""

    def test_builtin_script_metadata(self):
        registry = SkillRegistry()
        scripts = {info.name: info.script for info in registry.list_all()}

        assert scripts["cognition"] == "scripts/update_cognition.py"
        assert scripts["memory"] == "scripts/memory_maintenance.py"

    @pytest.mark.asyncio
    async def test_memory_maintenance_execute(self, tmp_path):
        registry = SkillRegistry()
        state_dir = tmp_path / "state"
        state_dir.mkdir()
        memory_file = state_dir / "memory.jsonl"
        memory_file.write_text(
            json.dumps(
                {
                    "tick": 1,
                    "type": "event",
                    "summary": "Met Alice.",
                    "importance": "high",
                }
            )
            + "\n",
            encoding="utf-8",
        )

        result = await registry.execute(
            "memory",
            {"memory_file": "state/memory.jsonl", "current_tick": 2},
            tmp_path,
        )

        assert result["ok"] is True
        rows = [
            json.loads(line)
            for line in memory_file.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        assert rows
        assert "_retention" in rows[0]


class TestCheckpoint:
    """Checkpoint 类的测试。"""

    def test_save_and_restore(self, tmp_path):
        config = AgentConfig()
        checkpoint = Checkpoint(tmp_path, config)

        state = {"step_count": 42, "data": "test"}
        path = checkpoint.save(tick=100, state=state)
        assert path.exists()

        restored = checkpoint.restore(100)
        assert restored is not None
        assert restored["tick"] == 100
        assert restored["state"]["step_count"] == 42

    def test_restore_nonexistent(self, tmp_path):
        config = AgentConfig()
        checkpoint = Checkpoint(tmp_path, config)

        result = checkpoint.restore(999)
        assert result is None

    def test_latest_tick(self, tmp_path):
        config = AgentConfig()
        checkpoint = Checkpoint(tmp_path, config)

        checkpoint.save(tick=10, state={"a": 1})
        checkpoint.save(tick=20, state={"b": 2})
        checkpoint.save(tick=15, state={"c": 3})

        assert checkpoint.latest_tick() == 20


class TestWriteAheadLog:
    """WriteAheadLog 类的测试。"""

    def test_log_intent_and_result(self, tmp_path):
        wal = WriteAheadLog(tmp_path)

        intent_id = wal.log_intent("execute_skill", {"skill_name": "test"}, tick=1)
        assert intent_id.startswith("intent_1_")

        pending = wal.get_pending()
        assert len(pending) == 1
        assert pending[0]["action"] == "execute_skill"

        wal.log_result(intent_id, {"ok": True}, success=True)
        assert len(wal.get_pending()) == 0

    def test_pending_after_tick(self, tmp_path):
        wal = WriteAheadLog(tmp_path)

        wal.log_intent("bash", {"command": "ls"}, tick=1)
        wal.log_intent("bash", {"command": "pwd"}, tick=2)
        wal.log_intent("bash", {"command": "whoami"}, tick=3)

        pending_after_1 = wal.get_pending_after_tick(1)
        assert len(pending_after_1) == 2

    def test_persistence(self, tmp_path):
        wal1 = WriteAheadLog(tmp_path)
        wal1.log_intent("test_action", {"key": "value"}, tick=1)

        wal2 = WriteAheadLog(tmp_path)
        pending = wal2.get_pending()
        assert len(pending) == 1


class TestRateLimiter:
    """RateLimiter 类的测试。"""

    @pytest.mark.asyncio
    async def test_acquire(self):
        limiter = RateLimiter(rps=10.0, burst=5)
        await limiter.acquire()
        assert limiter._tokens < 5

    @pytest.mark.asyncio
    async def test_burst(self):
        limiter = RateLimiter(rps=1.0, burst=3)
        for _ in range(3):
            await limiter.acquire()
        assert limiter._tokens < 1


class TestTaskManager:
    """TaskManager 类的测试。"""

    @pytest.mark.asyncio
    async def test_start_and_cancel(self):
        manager = TaskManager()

        async def long_task():
            await asyncio.sleep(10)
            return "done"

        await manager.start("task1", long_task())
        assert "task1" in manager.list()

        cancelled = await manager.cancel("task1")
        assert cancelled is True

    @pytest.mark.asyncio
    async def test_cancel_all(self):
        manager = TaskManager()

        async def task():
            await asyncio.sleep(10)

        await manager.start("t1", task())
        await manager.start("t2", task())

        await manager.cancel_all()
        assert len(manager.list()) == 0


class TestPriorityScheduler:
    """PriorityScheduler 类的测试。"""

    @pytest.mark.asyncio
    async def test_priority_order(self):
        scheduler = PriorityScheduler(max_concurrent=2)
        results = []

        async def task(val):
            results.append(val)
            return val

        await scheduler.submit("low", task(1), Priority.LOW)
        await scheduler.submit("high", task(2), Priority.HIGH)
        await scheduler.submit("normal", task(3), Priority.NORMAL)

        for tid in ("low", "high", "normal"):
            r = await scheduler.get_result(tid, timeout=2.0)
            assert r["ok"] is True

        assert results[0] == 2
        assert set(results) == {1, 2, 3}


class TestDeadlockDetector:
    """DeadlockDetector 类的测试。"""

    def test_no_deadlock(self):
        detector = DeadlockDetector(timeout=1.0)
        detector.register("op1")
        assert len(detector.check()) == 0
        detector.complete("op1")
        assert len(detector.check()) == 0

    def test_deadlock_detected(self):
        detector = DeadlockDetector(timeout=0.01)
        detector.register("op1")
        import time

        time.sleep(0.02)
        deadlocked = detector.check()
        assert "op1" in deadlocked


class TestAgentMemory:
    """AgentMemory 类的测试。"""

    def test_set_and_get_task(self, tmp_path):
        memory = AgentMemory(tmp_path)
        memory.set_current_task("Complete analysis")

        assert memory._data["current_task"] == "Complete analysis"

    def test_add_decision(self, tmp_path):
        memory = AgentMemory(tmp_path)
        memory.add_decision("Use SQLite")
        memory.add_decision("Add caching")

        assert len(memory._data["decisions"]) == 2

    def test_add_error(self, tmp_path):
        memory = AgentMemory(tmp_path)
        memory.add_error({"action": "bash", "error": "failed"})

        assert len(memory._data["errors"]) == 1

    def test_complete_task(self, tmp_path):
        memory = AgentMemory(tmp_path)
        memory.set_current_task("Task 1")
        memory.complete_task("Task 1")

        assert memory._data["current_task"] == ""
        assert len(memory._data["completed_tasks"]) == 1

    def test_to_prompt_context(self, tmp_path):
        memory = AgentMemory(tmp_path)
        memory.set_current_task("Main task")
        memory.update("goals", ["Goal 1"])
        memory.add_decision("Decision 1")

        prompt = memory.to_prompt_context()
        assert "Main task" in prompt
        assert "Goal 1" in prompt
        assert "Decision 1" in prompt

    def test_clear(self, tmp_path):
        memory = AgentMemory(tmp_path)
        memory.set_current_task("Task")
        memory.add_decision("Decision")
        memory.clear()

        assert memory._data["current_task"] == ""
        assert len(memory._data["decisions"]) == 0


class TestParallelExecutor:
    """ParallelExecutor 类的测试。"""

    def test_is_safe(self):
        config = AgentConfig()
        executor = ParallelExecutor(config)

        assert executor.is_safe("workspace_read") is True
        assert executor.is_safe("bash") is False

    @pytest.mark.asyncio
    async def test_execute_parallel(self):
        config = AgentConfig()
        executor = ParallelExecutor(config)

        results = []

        async def mock_executor(tool, args):
            await asyncio.sleep(0.01)
            results.append(tool)
            return {"ok": True, "tool": tool}

        tools = [
            ("workspace_read", {"path": "a.txt"}),
            ("workspace_read", {"path": "b.txt"}),
        ]

        outcomes = await executor.execute(tools, mock_executor)
        assert len(outcomes) == 2
        assert all(o["ok"] for o in outcomes)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
