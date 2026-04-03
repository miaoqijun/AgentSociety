"""Agent 上下文配置（阈值与 capability 映射）。

该模块只负责保存「压缩相关阈值与限制」以及从 ``capability_kwargs`` 读取这些数值。

记忆、thread 压缩、token 计量与摘要生成见 :mod:`agentsociety2.agent.context`。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class ContextConfig:
    """上下文相关阈值与限制。

    该配置用于控制 thread 压缩/摘要预算/工作区截断等行为。
    """

    # ── 模型上下文限制（核心参数）──
    model_context_window: int = 128000  # 模型上下文窗口大小（tokens）
    compact_warning_ratio: float = 0.60  # 发出警告的利用率
    compact_trigger_ratio: float = 0.70  # 触发压缩的利用率
    compact_auto_ratio: float = 0.85  # 强制压缩的利用率

    # ── Thread 压缩阈值 ──
    thread_max_messages: int = 40
    thread_compact_keep_recent: int = 6
    thread_compact_max_chars: int = 24000

    # ── 摘要预算 ──
    summary_char_budget: int = 6000
    summary_msg_limit: int = 1600
    summary_msg_short_limit: int = 450

    # ── 工作区快照 ──
    workspace_snapshot_str_cap: int = 16384
    key_state_file_limit: int = 2500

    # ── Prompt 侧车 ──
    world_desc_max_chars: int = 16000
    profile_max_chars: int = 8000

    # ── 工具结果限制 ──
    tool_result_thread_budget: int = 65536
    workspace_read_chunk_cap: int = 32768
    stdout_max_chars: int = 5000
    stderr_max_chars: int = 2000
    system_prompt_max_identity_chars: int = 10000


def get_config_for_agent(
    capability_kwargs: Optional[dict[str, Any]] = None,
) -> ContextConfig:
    """从 ``capability_kwargs`` 读取上下文配置覆盖。

    :param capability_kwargs: 用户提供的配置覆盖项；未给定的字段使用默认值。
    :type capability_kwargs: dict[str, Any] | None
    :return: 配置实例。
    :rtype: ContextConfig
    :raises ValueError: 当某些字段的类型无法转换为对应的数值类型时。
    """
    config = ContextConfig()

    if not capability_kwargs:
        return config

    # 模型上下文限制
    if "model_context_window" in capability_kwargs:
        config.model_context_window = int(capability_kwargs["model_context_window"])
    if "compact_warning_ratio" in capability_kwargs:
        config.compact_warning_ratio = float(capability_kwargs["compact_warning_ratio"])
    if "compact_trigger_ratio" in capability_kwargs:
        config.compact_trigger_ratio = float(capability_kwargs["compact_trigger_ratio"])
    if "compact_auto_ratio" in capability_kwargs:
        config.compact_auto_ratio = float(capability_kwargs["compact_auto_ratio"])

    # Thread 配置
    if "thread_max_messages" in capability_kwargs:
        config.thread_max_messages = int(capability_kwargs["thread_max_messages"])
    if "thread_keep_recent" in capability_kwargs:
        config.thread_compact_keep_recent = int(capability_kwargs["thread_keep_recent"])
    if "thread_compact_chars" in capability_kwargs:
        config.thread_compact_max_chars = int(capability_kwargs["thread_compact_chars"])

    # 工具结果配置
    if "tool_result_thread_budget_chars" in capability_kwargs:
        config.tool_result_thread_budget = int(
            capability_kwargs["tool_result_thread_budget_chars"]
        )
    if "workspace_read_chunk_chars" in capability_kwargs:
        config.workspace_read_chunk_cap = int(
            capability_kwargs["workspace_read_chunk_chars"]
        )

    # Prompt 配置
    if "system_prompt_max_identity_chars" in capability_kwargs:
        config.system_prompt_max_identity_chars = int(
            capability_kwargs["system_prompt_max_identity_chars"]
        )
    if "profile_truncate_chars" in capability_kwargs:
        config.profile_max_chars = int(capability_kwargs["profile_truncate_chars"])
    if "world_desc_max_chars" in capability_kwargs:
        config.world_desc_max_chars = int(capability_kwargs["world_desc_max_chars"])

    # 摘要配置
    if "summary_char_budget" in capability_kwargs:
        config.summary_char_budget = int(capability_kwargs["summary_char_budget"])

    # 输出截断
    if "stdout_max_chars" in capability_kwargs:
        config.stdout_max_chars = int(capability_kwargs["stdout_max_chars"])
    if "stderr_max_chars" in capability_kwargs:
        config.stderr_max_chars = int(capability_kwargs["stderr_max_chars"])

    return config
