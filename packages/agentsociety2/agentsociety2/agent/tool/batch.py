"""LLM 批量调用路由器。

提供 :class:`~agentsociety2.agent.tool.batch.BatchLLMRouter`，用于批量处理多个 Agent 的 LLM 请求，
提升并发效率，减少 API 调用开销。
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Optional

from agentsociety2.logger import get_logger

logger = get_logger()


@dataclass
class BatchRequest:
    """批处理请求。

    :param agent_id: Agent ID。
    :param messages: LLM 消息列表。
    :param future: 用于返回结果的 Future。
    :param created_at: 请求创建时间。
    """

    agent_id: int
    messages: list[dict[str, str]]
    future: asyncio.Future[Any]
    created_at: float = field(default_factory=time.monotonic)


class BatchLLMRouter:
    """LLM 批量调用路由器。

    收集多个 Agent 的 LLM 请求，批量发送以提升效率。

    :param batch_size: 批量大小阈值。
    :param timeout: 批量超时秒数。
    :param max_concurrent: 最大并发请求数。
    """

    def __init__(
        self,
        batch_size: int = 10,
        timeout: float = 0.1,
        max_concurrent: int = 100,
    ) -> None:
        self._batch_size = batch_size
        self._timeout = timeout
        self._max_concurrent = max_concurrent
        self._pending: list[BatchRequest] = []
        self._lock = asyncio.Lock()
        self._flush_task: asyncio.Task[None] | None = None
        self._caller: Callable[[int, list[dict[str, str]]], Awaitable[Any]] | None = (
            None
        )
        self._running = False

    def set_caller(
        self, caller: Callable[[int, list[dict[str, str]]], Awaitable[Any]]
    ) -> None:
        """设置 LLM 调用函数。"""
        self._caller = caller

    async def start(self) -> None:
        """启动批处理路由器。"""
        if self._running:
            return
        self._running = True
        self._flush_task = asyncio.create_task(self._flush_loop())
        logger.info(
            f"BatchLLMRouter started: batch_size={self._batch_size}, "
            f"timeout={self._timeout}s, max_concurrent={self._max_concurrent}"
        )

    async def stop(self) -> None:
        """停止批处理路由器，处理剩余请求。"""
        self._running = False
        if self._flush_task is not None:
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass
            self._flush_task = None
        # 处理剩余请求
        if self._pending:
            await self._flush()
        logger.info("BatchLLMRouter stopped")

    async def submit(self, agent_id: int, messages: list[dict[str, str]]) -> Any:
        """提交 LLM 请求，自动批处理。

        :param agent_id: Agent ID。
        :param messages: LLM 消息列表。
        :return: LLM 响应。
        :raises RuntimeError: 路由器未启动或未设置调用函数。
        """
        if not self._running:
            raise RuntimeError("BatchLLMRouter not started")
        if self._caller is None:
            raise RuntimeError("BatchLLMRouter: caller not set")

        loop = asyncio.get_running_loop()
        future: asyncio.Future[Any] = loop.create_future()

        async with self._lock:
            self._pending.append(
                BatchRequest(
                    agent_id=agent_id,
                    messages=messages,
                    future=future,
                )
            )
            # 达到批量大小时立即发送
            if len(self._pending) >= self._batch_size:
                await self._flush()

        return await future

    async def _flush_loop(self) -> None:
        """定期刷新批次的循环。"""
        while self._running:
            await asyncio.sleep(self._timeout)
            async with self._lock:
                if self._pending:
                    await self._flush()

    async def _flush(self) -> None:
        """批量发送请求。

        注意：当前实现使用并行发送而非真正的 batch API。
        当 LiteLLM 支持 batch API 时可切换。
        """
        if not self._pending:
            return

        batch = self._pending.copy()
        self._pending.clear()

        if self._caller is None:
            for req in batch:
                req.future.set_exception(RuntimeError("caller not set"))
            return

        # 并行发送所有请求
        tasks = [self._call_llm_with_retry(req) for req in batch]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for req, result in zip(batch, results):
            if isinstance(result, Exception):
                req.future.set_exception(result)
            else:
                req.future.set_result(result)

    async def _call_llm_with_retry(self, req: BatchRequest) -> Any:
        """带重试的 LLM 调用。

        :param req: 批处理请求。
        :return: LLM 响应。
        """
        max_retries = 2
        last_err: Exception | None = None

        for attempt in range(max_retries + 1):
            try:
                if self._caller is None:
                    raise RuntimeError("caller not set")
                return await self._caller(req.agent_id, req.messages)
            except Exception as e:
                last_err = e
                # 检查是否为瞬时错误
                is_transient = self._is_transient_error(e)
                if not is_transient or attempt >= max_retries:
                    raise
                delay = 0.5 * (2**attempt)
                logger.warning(
                    f"BatchLLMRouter: transient error for agent {req.agent_id} "
                    f"(attempt {attempt + 1}/{max_retries + 1}): {e}; retry in {delay}s"
                )
                await asyncio.sleep(delay)

        raise last_err or RuntimeError("Unexpected error in _call_llm_with_retry")

    @staticmethod
    def _is_transient_error(e: Exception) -> bool:
        """检查是否为瞬时错误。

        :param e: 异常。
        :return: 是否为瞬时错误。
        """
        # 限流类错误
        err_str = str(e).lower()
        if any(
            x in err_str for x in ("rate limit", "429", "too many requests", "timeout")
        ):
            return True
        # 连接类错误
        if isinstance(e, (asyncio.TimeoutError, ConnectionError, OSError)):
            return True
        return False


class BatchLLMRouterSingleton:
    """BatchLLMRouter 单例管理器。

    提供全局共享的批处理路由器实例。
    """

    _instance: BatchLLMRouter | None = None
    _lock = asyncio.Lock()

    @classmethod
    async def get_instance(
        cls,
        batch_size: int = 10,
        timeout: float = 0.1,
        max_concurrent: int = 100,
    ) -> BatchLLMRouter:
        """获取单例实例。"""
        async with cls._lock:
            if cls._instance is None:
                cls._instance = BatchLLMRouter(
                    batch_size=batch_size,
                    timeout=timeout,
                    max_concurrent=max_concurrent,
                )
                await cls._instance.start()
            return cls._instance

    @classmethod
    async def shutdown(cls) -> None:
        """关闭单例实例。"""
        async with cls._lock:
            if cls._instance is not None:
                await cls._instance.stop()
                cls._instance = None
