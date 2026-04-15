"""Agent统一配置管理。

本模块提供Agent的统一配置系统，整合所有分散的配置项。

模块结构
========

- :class:`AgentConfig`: 主配置类，包含所有子配置
- :class:`ModelConfig`: 模型相关配置
- :class:`LoopConfig`: 工具循环配置
- :class:`ContextConfig`: 上下文管理配置
- :class:`PersistenceConfig`: 持久化配置
- :class:`ConcurrencyConfig`: 并发控制配置
- :class:`LoopDetectionConfig`: 循环检测配置

设计原则
========

1. **开箱即用**: 所有配置都有合理默认值
2. **环境变量覆盖**: 支持通过环境变量动态调整
3. **分组管理**: 配置按功能分组，便于维护
4. **类型安全**: 使用dataclass确保类型正确

示例
====

基本使用::

    from agentsociety2.agent.config import AgentConfig

    # 使用默认值
    config = AgentConfig()

    # 从环境变量加载
    config = AgentConfig.from_env()

    # 从kwargs覆盖
    config = AgentConfig.from_kwargs({"max_tool_rounds": 30})

访问配置::

    config.model.context_window  # 200000
    config.loop.max_rounds  # 24
    config.persistence.checkpoint_interval  # 10
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

# 环境变量白名单：允许传递给子进程的环境变量
ALLOWED_ENV_VARS = frozenset(
    {
        "PATH",
        "HOME",
        "USER",
        "SHELL",
        "PYTHONPATH",
        "PYTHONUNBUFFERED",
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "LITELLM_MODEL",
        "LITELLM_BASE_URL",
        "AGENT_MEMORY_MAX_ENTRIES",
        "AGENT_MEMORY_STRENGTH",
    }
)
from typing import Any, Optional


def _int(name: str, default: int) -> int:
    """从环境变量读取整数配置。

    :param name: 环境变量名。
    :param default: 默认值。
    :return: 配置值。
    """
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def _float(name: str, default: float) -> float:
    """从环境变量读取浮点数配置。

    :param name: 环境变量名。
    :param default: 默认值。
    :return: 配置值。
    """
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return default


def _bool(name: str, default: bool) -> bool:
    """从环境变量读取布尔值配置。

    :param name: 环境变量名。
    :param default: 默认值。
    :return: 配置值。
    """
    val = os.getenv(name, "").lower()
    if val in ("true", "1", "yes", "on"):
        return True
    if val in ("false", "0", "no", "off"):
        return False
    return default


@dataclass
class ModelConfig:
    """模型配置。

    控制LLM模型相关参数。

    Attributes:
        model: 模型名称（如 "claude-3-opus-20240229"）。
        context_window: 上下文窗口大小（tokens）。
        output_reserve: 输出预留tokens。
        prompt_overhead: 系统提示词开销tokens。
    """

    model: str = ""
    context_window: int = 200_000
    output_reserve: int = 16_000
    prompt_overhead: int = 8_000

    @property
    def effective_window(self) -> int:
        """有效上下文窗口大小。

        :return: 上下文窗口减去输出和开销后的有效大小。
        """
        return max(
            8192, self.context_window - self.output_reserve - self.prompt_overhead
        )


@dataclass
class LoopConfig:
    """工具循环配置。

    控制Agent的工具执行循环行为。

    Attributes:
        max_rounds: 单步最大工具轮数。
        tool_timeout: 单个工具超时时间（秒）。
        step_timeout: 整步超时时间（秒）。
        bash_retries: bash命令超时重试次数。
        llm_retries: LLM调用重试次数。
    """

    max_rounds: int = 24
    tool_timeout: float = 30.0
    step_timeout: int = 300
    bash_retries: int = 1
    llm_retries: int = 3


@dataclass
class ContextConfig:
    """上下文管理配置。

    控制Thread压缩、输出限制等行为。

    Attributes:
        model_context_window: 模型上下文窗口大小。
        compact_warning_ratio: 压缩警告阈值（相对上下文窗口）。
        compact_trigger_ratio: 压缩触发阈值。
        compact_auto_ratio: 自动压缩比例。
        compact_force_ratio: 强制压缩阈值。
        thread_max_messages: Thread最大消息数。
        thread_max_tokens: Thread最大Token数。
        thread_keep_recent: 压缩时保留的最近消息数。
        thread_compact_max_chars: 压缩时最大字符数。
        thread_compact_keep_recent: 压缩保留最近消息数。
        stdout_max_chars: stdout最大字符数。
        stderr_max_chars: stderr最大字符数。
        tool_result_budget: 工具结果预算（字符）。
        workspace_chunk_size: 工作区文件读取块大小。
        summary_msg_limit: 摘要消息限制。
        summary_msg_short_limit: 短摘要消息限制。
        summary_char_budget: 摘要字符预算。
        key_state_file_limit: 关键状态文件限制。
        workspace_read_chunk_cap: 工作区读取块上限。
        tool_result_thread_budget: 工具结果线程预算。
        tool_table_mode: 工具表模式 ("full" | "minimal")。
        workspace_cache_max_entries: 工作区缓存最大条目数。
        grep_max_files: grep 最大扫描文件数。
        grep_max_matches: grep 最大返回匹配数。
        grep_max_file_bytes: grep 最大文件大小（字节）。
    """

    model_context_window: int = 200_000
    compact_warning_ratio: float = 0.60
    compact_trigger_ratio: float = 0.75
    compact_auto_ratio: float = 0.85
    compact_force_ratio: float = 0.90
    thread_max_messages: int = 50
    thread_max_tokens: int = 150_000
    thread_keep_recent: int = 8
    thread_compact_max_chars: int = 100_000
    thread_compact_keep_recent: int = 8
    stdout_max_chars: int = 5000
    stderr_max_chars: int = 2000
    tool_result_budget: int = 32_000
    workspace_chunk_size: int = 32_768
    summary_msg_limit: int = 10
    summary_msg_short_limit: int = 5
    summary_char_budget: int = 4000
    key_state_file_limit: int = 5000
    workspace_read_chunk_cap: int = 32_000
    tool_result_thread_budget: int = 64_000
    tool_table_mode: str = "full"
    workspace_cache_max_entries: int = 50
    grep_max_files: int = 2000
    grep_max_matches: int = 1000
    grep_max_file_bytes: int = 2 * 1024 * 1024


@dataclass
class StateConfig:
    """状态文件配置。

    控制状态文件的发现和摘要提取行为。
    支持内置状态文件和用户扩展。

    Attributes:
        builtin_states: 内置状态文件定义（名称 -> (文件名, 摘要字段)）。
        extra_states: 额外的扩展状态文件定义。
        auto_discover: 是否自动发现 state/ 目录下的所有 JSON 文件。
        summary_max_length: 摘要字段最大长度。
    """

    builtin_states: dict[str, tuple[str, str]] = field(
        default_factory=lambda: {
            "emotion": ("emotion.json", "primary"),
            "intention": ("intention.json", "intention"),
            "needs": ("needs.json", "current_need"),
            "plan": ("plan_state.json", "target"),
        }
    )
    extra_states: dict[str, tuple[str, str]] = field(default_factory=dict)
    auto_discover: bool = True
    summary_max_length: int = 100

    def get_all_states(self) -> dict[str, tuple[str, str]]:
        """获取所有状态文件定义（内置 + 扩展）。

        :return: 状态名称到 (文件名, 摘要字段) 的映射。
        """
        result = dict(self.builtin_states)
        result.update(self.extra_states)
        return result


@dataclass
class PersistenceConfig:
    """持久化配置。

    控制检查点、清理等持久化行为。

    Attributes:
        checkpoint_interval: 检查点间隔（ticks）。
        checkpoint_max: 最大保留检查点数。
        checkpoint_include_workspace: 检查点是否包含工作区文件。
        max_log_files: 最大日志文件数。
        max_memory_entries: 最大记忆条目数。
        archive_after_days: 归档阈值（天）。
        wal_max_entries: WAL 最大保留条目数。
        llm_history_max_entries: LLM 交互历史最大条目数。
        enable_llm_history: 是否启用 LLM 交互历史记录。
    """

    checkpoint_interval: int = 10
    checkpoint_max: int = 20
    checkpoint_include_workspace: bool = True
    max_log_files: int = 50
    max_memory_entries: int = 5000
    archive_after_days: int = 7
    wal_max_entries: int = 1000
    llm_history_max_entries: int = 100
    enable_llm_history: bool = False


@dataclass
class ConcurrencyConfig:
    """并发控制配置。

    控制并行执行和限流行为。

    Attributes:
        max_parallel_tools: 最大并行工具数。
        max_llm_concurrent: 最大并发LLM调用数。
        max_subprocess: 最大并发子进程数。
        rate_limit_rps: 限流阈值（每秒请求数）。
    """

    max_parallel_tools: int = 3
    max_llm_concurrent: int = 5
    max_subprocess: int = 8
    rate_limit_rps: float = 10.0


@dataclass
class LoopDetectionConfig:
    """循环检测配置。

    控制Agent行为循环检测灵敏度。

    Attributes:
        max_tool_repeats: 相同工具+参数连续调用阈值。
        max_content_repeats: 相同内容连续输出阈值。
        max_error_repeats: 相同错误连续出现阈值。
        history_size: 历史记录大小。
        overuse_threshold: 同一工具在 history_size 调用中的过度使用阈值。
    """

    max_tool_repeats: int = 5
    max_content_repeats: int = 10
    max_error_repeats: int = 3
    history_size: int = 20
    overuse_threshold: int = 15


@dataclass
class AgentConfig:
    """Agent统一配置。

    整合所有子配置，提供统一的访问入口。
    大部分配置有合理默认值，用户无需关心。

    Attributes:
        model: 模型配置。
        loop: 工具循环配置。
        context: 上下文管理配置。
        persistence: 持久化配置。
        concurrency: 并发控制配置。
        loop_detection: 循环检测配置。
        state: 状态文件配置。

    Example:

        >>> config = AgentConfig()  # 使用默认值
        >>> config = AgentConfig.from_env()  # 从环境变量
        >>> config = AgentConfig.from_kwargs({"max_tool_rounds": 30})
    """

    model: ModelConfig = field(default_factory=ModelConfig)
    loop: LoopConfig = field(default_factory=LoopConfig)
    context: ContextConfig = field(default_factory=ContextConfig)
    persistence: PersistenceConfig = field(default_factory=PersistenceConfig)
    concurrency: ConcurrencyConfig = field(default_factory=ConcurrencyConfig)
    loop_detection: LoopDetectionConfig = field(default_factory=LoopDetectionConfig)
    state: StateConfig = field(default_factory=StateConfig)

    @classmethod
    def from_env(cls) -> "AgentConfig":
        """从环境变量加载配置。

        仅暴露必要的用户配置项，其他使用合理的默认值。

        支持的环境变量：
            - AGENT_MODEL: 模型名称
            - AGENT_CONTEXT_WINDOW: 上下文窗口大小
            - AGENT_MAX_TOOL_ROUNDS: 最大工具轮数
            - AGENT_CHECKPOINT_INTERVAL: 检查点间隔
            - AGENT_STEP_TIMEOUT: 单步超时(秒)

        :return: 配置实例。
        """
        return cls(
            model=ModelConfig(
                model=os.getenv("AGENT_MODEL", ""),
                context_window=_int("AGENT_CONTEXT_WINDOW", 200_000),
            ),
            loop=LoopConfig(
                max_rounds=_int("AGENT_MAX_TOOL_ROUNDS", 24),
                step_timeout=_int("AGENT_STEP_TIMEOUT", 300),
            ),
            persistence=PersistenceConfig(
                checkpoint_interval=_int("AGENT_CHECKPOINT_INTERVAL", 10),
            ),
        )

    @classmethod
    def from_kwargs(cls, kwargs: Optional[dict[str, Any]] = None) -> "AgentConfig":
        """从参数字典创建配置。

        支持的参数键名映射到对应配置项。

        :param kwargs: 参数字典。
        :return: 配置实例。

        Example:

            >>> config = AgentConfig.from_kwargs({
            ...     "max_tool_rounds": 30,
            ...     "checkpoint_interval": 5,
            ... })
        """
        config = cls.from_env()
        if not kwargs:
            return config

        flat_map = {
            "model": ("model", "model"),
            "context_window": ("model", "context_window"),
            "max_tool_rounds": ("loop", "max_rounds"),
            "step_timeout_sec": ("loop", "step_timeout"),
            "checkpoint_interval": ("persistence", "checkpoint_interval"),
            "max_parallel_tools": ("concurrency", "max_parallel_tools"),
        }

        for key, (section, attr) in flat_map.items():
            if key in kwargs:
                section_obj = getattr(config, section)
                setattr(section_obj, attr, kwargs[key])

        return config

    def to_dict(self) -> dict[str, Any]:
        """转换为字典。

        :return: 包含所有配置的字典。
        """
        import dataclasses

        result = {}
        for section_name in [
            "model",
            "loop",
            "context",
            "persistence",
            "concurrency",
            "loop_detection",
        ]:
            section = getattr(self, section_name)
            result[section_name] = dataclasses.asdict(section)
        return result


# 默认配置实例
DEFAULT_CONFIG = AgentConfig()
