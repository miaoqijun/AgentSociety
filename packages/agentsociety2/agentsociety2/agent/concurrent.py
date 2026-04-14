"""并发控制模块。

提供Agent的并发执行和限流功能。

模块结构
========

- :class:`ParallelExecutor`: 并行工具执行器
- :class:`RateLimiter`: 令牌桶限流器
- :class:`TaskManager`: 后台任务管理器
- :func:`get_executor`: 获取全局执行器
- :func:`get_limiter`: 获取全局限流器
- :func:`get_task_manager`: 获取全局任务管理器

并行执行
========

部分工具可以安全并行执行（读操作），其他必须顺序执行（写操作）。

可安全并行的工具：
    - workspace_read
    - glob
    - grep
    - workspace_list
    - read_skill

必须顺序执行的工具：
    - workspace_write
    - bash
    - codegen
    - execute_skill

示例::

    from agentsociety2.agent.concurrent import ParallelExecutor
    
    executor = ParallelExecutor(config)
    results = await executor.execute(
        tools=[("workspace_read", {"path": "a.json"}), ...],
        executor=my_executor_func
    )

限流控制
========

使用令牌桶算法控制请求速率::

    from agentsociety2.agent.concurrent import RateLimiter
    
    limiter = RateLimiter(rps=10.0)
    await limiter.acquire()  # 等待可用令牌
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Callable, Coroutine, Optional, TypeVar

from .config import AgentConfig

T = TypeVar("T")


class ParallelExecutor:
    """并行工具执行器。

    自动识别可安全并行执行的工具，优化执行效率。

    Attributes:
        config: Agent配置。
        PARALLEL_SAFE: 可安全并行的工具集合。

    Example:

        >>> executor = ParallelExecutor(config)
        >>> results = await executor.execute(tools, my_executor)
    """

    PARALLEL_SAFE = {"workspace_read", "glob", "grep", "workspace_list", "read_skill"}

    def __init__(self, config: AgentConfig):
        """初始化执行器。

        :param config: Agent配置。
        """
        self.config = config
        self._semaphore = asyncio.Semaphore(config.concurrency.max_parallel_tools)

    def is_safe(self, tool: str) -> bool:
        """检查工具是否可安全并行。

        :param tool: 工具名称。
        :return: 是否可安全并行。
        """
        return tool in self.PARALLEL_SAFE

    async def execute(
        self,
        tools: list[tuple[str, dict[str, Any]]],
        executor: Callable[[str, dict[str, Any]], Coroutine[Any, Any, dict[str, Any]]],
    ) -> list[dict[str, Any]]:
        """执行工具列表。

        可安全并行的工具会并行执行，其他顺序执行。

        :param tools: (工具名, 参数) 元组列表。
        :param executor: 单个工具执行函数。
        :return: 结果列表，与输入顺序一致。
        """
        if not tools:
            return []

        parallel = [(i, t, a) for i, (t, a) in enumerate(tools) if self.is_safe(t)]
        sequential = [(i, t, a) for i, (t, a) in enumerate(tools) if not self.is_safe(t)]

        results: list[dict[str, Any]] = [{}] * len(tools)

        # 并行执行
        if parallel:
            tasks = [self._exec(executor, t, a) for _, t, a in parallel]
            outcomes = await asyncio.gather(*tasks, return_exceptions=True)
            for (idx, _, _), result in zip(parallel, outcomes):
                results[idx] = {"ok": False, "error": str(result)} if isinstance(result, Exception) else result

        # 顺序执行
        for idx, tool, args in sequential:
            try:
                results[idx] = await executor(tool, args)
            except Exception as e:
                results[idx] = {"ok": False, "error": str(e)}

        return results

    async def _exec(
        self,
        executor: Callable,
        tool: str,
        args: dict[str, Any],
    ) -> dict[str, Any]:
        """带信号量保护的执行。

        :param executor: 执行函数。
        :param tool: 工具名。
        :param args: 参数。
        :return: 执行结果。
        """
        async with self._semaphore:
            return await executor(tool, args)


class RateLimiter:
    """令牌桶限流器。

    控制操作速率，防止过载。

    Attributes:
        rate: 每秒令牌数。
        burst: 桶容量。

    Example:

        >>> limiter = RateLimiter(rps=10.0)
        >>> await limiter.acquire()  # 等待令牌
    """

    def __init__(self, rps: float, burst: int = 10):
        """初始化限流器。

        :param rps: 每秒请求数。
        :param burst: 桶容量，允许短时突发。
        """
        self.rate = rps
        self.burst = burst
        self._tokens = float(burst)
        self._last = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """等待可用令牌。"""
        async with self._lock:
            now = time.monotonic()
            self._tokens = min(self.burst, self._tokens + (now - self._last) * self.rate)
            self._last = now

            if self._tokens < 1:
                await asyncio.sleep((1 - self._tokens) / self.rate)
                self._tokens = 0
            else:
                self._tokens -= 1


class TaskManager:
    """后台任务管理器。

    管理后台异步任务，支持启动、取消和等待。

    Example:

        >>> manager = TaskManager()
        >>> await manager.start("task1", my_coroutine())
        >>> await manager.cancel("task1")
    """

    def __init__(self):
        """初始化任务管理器。"""
        self._tasks: dict[str, asyncio.Task] = {}
        self._lock = asyncio.Lock()

    async def start(self, task_id: str, coro: Coroutine) -> None:
        """启动后台任务。

        :param task_id: 任务ID。
        :param coro: 协程。
        :raises ValueError: 任务已存在。
        """
        async with self._lock:
            if task_id in self._tasks and not self._tasks[task_id].done():
                raise ValueError(f"Task {task_id} already running")
            self._tasks[task_id] = asyncio.create_task(coro)

    async def cancel(self, task_id: str) -> bool:
        """取消后台任务。

        :param task_id: 任务ID。
        :return: 是否成功取消。
        """
        async with self._lock:
            if task_id not in self._tasks:
                return False
            task = self._tasks[task_id]
            if task.done():
                return False
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            return True

    async def cancel_all(self) -> None:
        """取消所有后台任务。"""
        async with self._lock:
            for task in self._tasks.values():
                if not task.done():
                    task.cancel()
            await asyncio.gather(*self._tasks.values(), return_exceptions=True)
            self._tasks.clear()

    def list(self) -> list[str]:
        """列出所有任务ID。

        :return: 任务ID列表。
        """
        return list(self._tasks.keys())


# 全局实例
_executor: Optional[ParallelExecutor] = None
_limiter: Optional[RateLimiter] = None
_manager: Optional[TaskManager] = None


def get_executor(config: AgentConfig) -> ParallelExecutor:
    """获取全局并行执行器。

    :param config: Agent配置。
    :return: 并行执行器实例。
    """
    global _executor
    if _executor is None:
        _executor = ParallelExecutor(config)
    return _executor


def get_limiter(config: AgentConfig) -> RateLimiter:
    """获取全局限流器。

    :param config: Agent配置。
    :return: 限流器实例。
    """
    global _limiter
    if _limiter is None:
        _limiter = RateLimiter(config.concurrency.rate_limit_rps)
    return _limiter


def get_task_manager() -> TaskManager:
    """获取全局任务管理器。

    :return: 任务管理器实例。
    """
    global _manager
    if _manager is None:
        _manager = TaskManager()
    return _manager
