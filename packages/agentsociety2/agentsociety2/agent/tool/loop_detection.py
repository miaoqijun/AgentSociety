"""循环检测服务。

防止 Agent 陷入无效循环：工具调用循环、内容循环、错误重复。

Example:
    from agentsociety2.agent.tool.loop_detection import LoopDetectionService

    detector = LoopDetectionService()
    result = detector.check_tool_loop("bash", {"command": "ls"})
    if result.is_loop:
        print(f"Loop detected: {result.details}")
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Any


@dataclass
class LoopDetectionConfig:
    """循环检测配置。

    :ivar max_tool_repeats: 相同工具+参数连续调用阈值。
    :ivar max_content_repeats: 相同内容连续输出阈值。
    :ivar max_error_repeats: 相同错误连续出现阈值。
    :ivar history_size: 历史记录大小。
    """

    max_tool_repeats: int = 5
    max_content_repeats: int = 10
    max_error_repeats: int = 3
    history_size: int = 20


@dataclass
class LoopDetectionResult:
    """循环检测结果。

    :ivar is_loop: 是否检测到循环。
    :ivar loop_type: 循环类型 ("tool", "content", "error")。
    :ivar details: 详细描述。
    """

    is_loop: bool = False
    loop_type: str = ""
    details: str = ""


class LoopDetectionService:
    """循环检测服务。

    检测三种循环类型：

    1. 工具调用循环：相同工具+参数连续调用
    2. 内容循环：相同输出内容连续出现
    3. 错误重复：相同错误连续出现
    """

    def __init__(self, config: LoopDetectionConfig | None = None):
        """初始化循环检测服务。

        :param config: 检测配置，为 None 时使用默认值。
        :type config: LoopDetectionConfig | None
        """
        self._config = config or LoopDetectionConfig()
        self._tool_call_history: deque[str] = deque(maxlen=self._config.history_size)
        self._content_history: deque[str] = deque(maxlen=self._config.history_size)
        self._error_history: deque[str] = deque(maxlen=self._config.history_size)

    def reset(self) -> None:
        """重置历史记录。"""
        self._tool_call_history.clear()
        self._content_history.clear()
        self._error_history.clear()

    def check_tool_loop(self, tool_name: str, arguments: dict[str, Any]) -> LoopDetectionResult:
        """检测工具调用循环。

        :param tool_name: 工具名称。
        :param arguments: 工具参数。
        :return: 检测结果。
        :rtype: LoopDetectionResult
        """
        call_fingerprint = f"{tool_name}:{self._hash_arguments(arguments)}"
        self._tool_call_history.append(call_fingerprint)

        if len(self._tool_call_history) >= self._config.max_tool_repeats:
            recent = list(self._tool_call_history)[-self._config.max_tool_repeats :]
            if len(set(recent)) == 1:
                return LoopDetectionResult(
                    is_loop=True,
                    loop_type="tool",
                    details=f"Tool '{tool_name}' called {self._config.max_tool_repeats} times with same arguments",
                )
        return LoopDetectionResult(is_loop=False)

    def check_content_loop(self, content: str) -> LoopDetectionResult:
        """检测内容循环。

        :param content: 输出内容。
        :return: 检测结果。
        :rtype: LoopDetectionResult
        """
        content_hash = self._hash_content(content)
        self._content_history.append(content_hash)

        if len(self._content_history) >= self._config.max_content_repeats:
            recent = list(self._content_history)[-self._config.max_content_repeats :]
            if len(set(recent)) == 1:
                return LoopDetectionResult(
                    is_loop=True,
                    loop_type="content",
                    details=f"Same content repeated {self._config.max_content_repeats} times",
                )
        return LoopDetectionResult(is_loop=False)

    def check_error_loop(self, error: str) -> LoopDetectionResult:
        """检测错误循环。

        :param error: 错误信息。
        :return: 检测结果。
        :rtype: LoopDetectionResult
        """
        error_hash = self._hash_content(error)
        self._error_history.append(error_hash)

        if len(self._error_history) >= self._config.max_error_repeats:
            recent = list(self._error_history)[-self._config.max_error_repeats :]
            if len(set(recent)) == 1:
                return LoopDetectionResult(
                    is_loop=True,
                    loop_type="error",
                    details=f"Same error repeated {self._config.max_error_repeats} times: {error[:100]}",
                )
        return LoopDetectionResult(is_loop=False)

    @staticmethod
    def _hash_arguments(args: dict[str, Any]) -> str:
        """生成参数哈希。

        :param args: 参数字典。
        :return: 哈希字符串。
        :rtype: str
        """
        import json
        try:
            return json.dumps(args, sort_keys=True, default=str)
        except Exception:
            return str(args)

    @staticmethod
    def _hash_content(content: str) -> str:
        """生成内容哈希。

        截取前200字符避免内存占用过大。

        :param content: 内容字符串。
        :return: 哈希字符串。
        :rtype: str
        """
        return content.strip()[:200]
