"""测试与阈值计算用的精简上下文配置。

``model_context_window`` 与主线路 :class:`~agentsociety2.agent.config.ModelConfig` 的声明窗口语义一致；
:meth:`ContextConfig.effective_window` 使用 :func:`~agentsociety2.agent.config.input_token_budget`。
"""

from __future__ import annotations

from dataclasses import dataclass

from agentsociety2.agent.config import DEFAULT_MODEL_CONTEXT_WINDOW, input_token_budget

#: 与 :data:`~agentsociety2.agent.config.DEFAULT_MODEL_CONTEXT_WINDOW` 相同。
DEFAULT_CONTEXT_WINDOW = DEFAULT_MODEL_CONTEXT_WINDOW


@dataclass
class ContextConfig:
    """用于单测或独立阈值实验的轻量上下文参数集。"""

    model: str = ""

    model_context_window: int = DEFAULT_CONTEXT_WINDOW
    output_reserve: int = 16_000
    prompt_overhead: int = 8_000

    compact_warning_ratio: float = 0.58
    compact_trigger_ratio: float = 0.72
    compact_auto_ratio: float = 0.84
    compact_block_ratio: float = 0.95

    max_retries: int = 3
    backoff: float = 2.0

    thread_max_messages: int = 40
    thread_compact_keep_recent: int = 6

    summary_char_budget: int = 6000
    summary_msg_limit: int = 1600

    @property
    def effective_window(self) -> int:
        """输入侧 token 预算。

        :returns: 对 ``model_context_window`` 调用 :func:`~agentsociety2.agent.config.input_token_budget` 的结果。
        """
        return input_token_budget(self.model_context_window)
