"""Agent 上下文配置（阈值与 capability 映射）。

该模块集中管理所有配置常量，包括：
- 压缩相关阈值与限制
- 安全配置（环境变量白名单）
- 循环检测阈值
- 内存限制
- 超时配置
- 并发配置

记忆、thread 压缩、token 计量与摘要生成见 :mod:`agentsociety2.agent.context`。
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# 全局配置常量
# ═══════════════════════════════════════════════════════════════════════════════


def _get_int_env(name: str, default: int) -> int:
    """从环境变量读取整数配置。

    :param name: 环境变量名。
    :param default: 默认值。
    :return: 配置值。
    """
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


# ── 默认上下文窗口 ──
DEFAULT_CONTEXT_WINDOW: int = 100_000

# ── 安全配置 ──
#: 允许传递给 Skill 脚本的环境变量白名单
ALLOWED_ENV_VARS: frozenset[str] = frozenset(
    {
        "PATH",
        "HOME",
        "USER",
        "SHELL",
        "PYTHONPATH",
        "PYTHONUNBUFFERED",
        "LANG",
        "LC_ALL",
    }
)

# ── 循环检测配置 ──
LOOP_MAX_TOOL_REPEATS: int = 5
LOOP_MAX_CONTENT_REPEATS: int = 10
LOOP_MAX_ERROR_REPEATS: int = 3
LOOP_HISTORY_SIZE: int = 20
LOOP_OVERUSE_THRESHOLD: int = 15

# ── 内存限制 ──
MAX_STEP_CONTEXT_CHARS: int = 100_000  # 100KB

# ── 超时配置 ──
DEFAULT_STEP_TIMEOUT_SEC: int = _get_int_env("AGENT_STEP_TIMEOUT_SEC", 300)
DEFAULT_BASH_TIMEOUT_SEC: int = 30
DEFAULT_SKILL_TIMEOUT_SEC: int = 30

# ── 并发配置 ──
MAX_SUBPROCESS_CONCURRENT: int = _get_int_env("AGENT_MAX_SUBPROCESS_CONCURRENT", 16)


def get_model_context_window(model: str) -> int:
    """获取模型的上下文窗口大小。

    从 LiteLLM 获取，未找到则返回默认值 100k。

    :param model: 模型名（如 "openai/gpt-4o"）。
    :return: 上下文窗口大小（tokens）。
    """
    if not model:
        return DEFAULT_CONTEXT_WINDOW

    try:
        from litellm.utils import get_model_info

        info = get_model_info(model)
        max_input = info.get("max_input_tokens")
        if isinstance(max_input, int) and max_input > 0:
            return max_input
    except Exception:
        pass

    return DEFAULT_CONTEXT_WINDOW


@dataclass
class ContextConfig:
    """上下文相关阈值与限制。

    该配置用于控制 thread 压缩/摘要预算/工作区截断等行为。
    """

    # ── 模型信息 ──
    model: str = ""  # 模型名，用于动态获取上下文窗口

    # ── 上下文窗口（可通过 model 自动获取，也可手动覆盖）──
    _model_context_window: int = field(default=0, repr=False)

    # ── 压缩阈值（相对比例）──
    compact_warning_ratio: float = 0.60
    compact_trigger_ratio: float = 0.70
    compact_auto_ratio: float = 0.85
    compact_block_ratio: float = 0.95

    # ── Token 预算 ──
    output_reserve: int = 16000
    prompt_overhead: int = 8000

    # ── 熔断机制 ──
    max_retries: int = 3
    backoff: float = 2.0

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

    @property
    def model_context_window(self) -> int:
        """模型上下文窗口大小（tokens）。"""
        if self._model_context_window > 0:
            return self._model_context_window
        if self.model:
            return get_model_context_window(self.model)
        return DEFAULT_CONTEXT_WINDOW

    @model_context_window.setter
    def model_context_window(self, value: int) -> None:
        self._model_context_window = max(0, int(value))

    @property
    def effective_window(self) -> int:
        """有效上下文窗口大小。"""
        return max(
            8192,
            self.model_context_window - self.output_reserve - self.prompt_overhead,
        )


def get_config_for_agent(
    capability_kwargs: Optional[dict[str, Any]] = None,
) -> ContextConfig:
    """从 ``capability_kwargs`` 读取上下文配置覆盖。

    :param capability_kwargs: 用户提供的配置覆盖项。
    :return: 配置实例。
    """
    config = ContextConfig()

    if not capability_kwargs:
        return config

    if "model" in capability_kwargs:
        config.model = str(capability_kwargs["model"])
    if "model_context_window" in capability_kwargs:
        config.model_context_window = int(capability_kwargs["model_context_window"])
    if "compact_warning_ratio" in capability_kwargs:
        config.compact_warning_ratio = float(capability_kwargs["compact_warning_ratio"])
    if "compact_trigger_ratio" in capability_kwargs:
        config.compact_trigger_ratio = float(capability_kwargs["compact_trigger_ratio"])
    if "compact_auto_ratio" in capability_kwargs:
        config.compact_auto_ratio = float(capability_kwargs["compact_auto_ratio"])
    if "compact_block_ratio" in capability_kwargs:
        config.compact_block_ratio = float(capability_kwargs["compact_block_ratio"])
    if "output_reserve" in capability_kwargs:
        config.output_reserve = int(capability_kwargs["output_reserve"])
    if "prompt_overhead" in capability_kwargs:
        config.prompt_overhead = int(capability_kwargs["prompt_overhead"])
    if "max_retries" in capability_kwargs:
        config.max_retries = int(capability_kwargs["max_retries"])
    if "backoff" in capability_kwargs:
        config.backoff = float(capability_kwargs["backoff"])
    if "thread_max_messages" in capability_kwargs:
        config.thread_max_messages = int(capability_kwargs["thread_max_messages"])
    if "thread_compact_keep_recent" in capability_kwargs:
        config.thread_compact_keep_recent = int(
            capability_kwargs["thread_compact_keep_recent"]
        )
    if "thread_compact_max_chars" in capability_kwargs:
        config.thread_compact_max_chars = int(
            capability_kwargs["thread_compact_max_chars"]
        )
    if "summary_char_budget" in capability_kwargs:
        config.summary_char_budget = int(capability_kwargs["summary_char_budget"])
    if "summary_msg_limit" in capability_kwargs:
        config.summary_msg_limit = int(capability_kwargs["summary_msg_limit"])
    if "summary_msg_short_limit" in capability_kwargs:
        config.summary_msg_short_limit = int(
            capability_kwargs["summary_msg_short_limit"]
        )
    if "workspace_snapshot_str_cap" in capability_kwargs:
        config.workspace_snapshot_str_cap = int(
            capability_kwargs["workspace_snapshot_str_cap"]
        )
    if "key_state_file_limit" in capability_kwargs:
        config.key_state_file_limit = int(capability_kwargs["key_state_file_limit"])
    if "world_desc_max_chars" in capability_kwargs:
        config.world_desc_max_chars = int(capability_kwargs["world_desc_max_chars"])
    if "profile_max_chars" in capability_kwargs:
        config.profile_max_chars = int(capability_kwargs["profile_max_chars"])
    if "tool_result_thread_budget" in capability_kwargs:
        config.tool_result_thread_budget = int(
            capability_kwargs["tool_result_thread_budget"]
        )
    if "workspace_read_chunk_cap" in capability_kwargs:
        config.workspace_read_chunk_cap = int(
            capability_kwargs["workspace_read_chunk_cap"]
        )
    if "stdout_max_chars" in capability_kwargs:
        config.stdout_max_chars = int(capability_kwargs["stdout_max_chars"])
    if "stderr_max_chars" in capability_kwargs:
        config.stderr_max_chars = int(capability_kwargs["stderr_max_chars"])
    if "system_prompt_max_identity_chars" in capability_kwargs:
        config.system_prompt_max_identity_chars = int(
            capability_kwargs["system_prompt_max_identity_chars"]
        )

    return config
