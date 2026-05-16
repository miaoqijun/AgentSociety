"""Agent 配置：模型、循环、上下文、持久化与并发等子配置的聚合入口。

常用项带默认值；少数入口可通过构造参数或环境变量覆盖。

Example:
    >>> from agentsociety2.agent.config import AgentConfig
    >>> AgentConfig().loop.max_rounds
    24
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional

# 子进程环境继承白名单
ALLOWED_ENV_VARS = frozenset(
    {
        "PATH",
        "HOME",
        "USER",
        "SHELL",
        "PYTHONUNBUFFERED",
        "LITELLM_MODEL",
        "LITELLM_BASE_URL",
        "AGENT_MEMORY_MAX_ENTRIES",
        "AGENT_MEMORY_STRENGTH",
    }
)


def _int(name: str, default: int) -> int:
    """将环境变量解析为有符号十进制整数。

    :param name: 环境变量名。
    :param default: 未设置或解析失败时的返回值。

    :returns: 解析得到的整数，或 ``default``。
    """
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def _optional_positive_float(name: str, default: float | None) -> float | None:
    raw = os.getenv(name)
    if raw is None:
        return default
    s = raw.strip().lower()
    if s in ("", "none", "off", "false", "0"):
        return None
    try:
        v = float(s)
        return v if v > 0 else None
    except ValueError:
        return default


_COMPACT_WARNING_RATIO = 0.58
_COMPACT_TRIGGER_RATIO = 0.72
_COMPACT_AUTO_RATIO = 0.84
_COMPACT_FORCE_RATIO = 0.90

_THREAD_MAX_MESSAGES = 50
_THREAD_MAX_TOKENS = 150_000
_THREAD_KEEP_RECENT = 12

_STDOUT_MAX_CHARS = 10_000
_STDERR_MAX_CHARS = 5_000
_TOOL_RESULT_BUDGET = 32_000

_WORKSPACE_READ_CHUNK_CAP = 32_000
_WORKSPACE_CACHE_MAX_ENTRIES = 50

_MAX_TOOL_REPEATS = 5
_MAX_CONTENT_REPEATS = 10
_MAX_ERROR_REPEATS = 3
_LOOP_HISTORY_SIZE = 20

_MAX_PARALLEL_TOOLS = 5
_MAX_LLM_CONCURRENT = 5
_MAX_SUBPROCESS = 8
_RATE_LIMIT_RPS = 10.0

_TIKTOKEN_ENCODING = "cl100k_base"

#: 声明上下文窗口的下限（tokens），低于此值的输入会被抬升。
MIN_USABLE_CONTEXT_TOKENS = 8_192
#: 无显式配置且 LiteLLM 无法解析时的默认声明窗口（tokens）。
DEFAULT_MODEL_CONTEXT_WINDOW = 200_000


def _litellm_max_input_tokens(model: str) -> Optional[int]:
    """调用 LiteLLM ``get_model_info`` 读取 ``max_input_tokens``。

    :param model: LiteLLM 模型名（可含 ``provider/model`` 形式）。

    :returns: 正整数表示输入侧上下文上限；未知模型或异常时为 ``None``。
    """
    name = (model or "").strip()
    if not name:
        return None
    try:
        from litellm import get_model_info

        info = get_model_info(name)
    except Exception:
        return None
    mi = info.get("max_input_tokens")
    if isinstance(mi, int) and mi > 0:
        return mi
    return None


def input_token_budget(total_context_tokens: int) -> int:
    """由声明窗口推算 thread 侧可用输入 token 预算。

    预留为 ``total`` 的 12%，并夹在 ``4096`` 与 ``72000`` 之间，再从 ``total`` 中扣除。

    :param total_context_tokens: 模型声明的总上下文长度（tokens）。

    :returns: 输入预算（tokens），不低于 :data:`MIN_USABLE_CONTEXT_TOKENS`。
    """
    total = max(MIN_USABLE_CONTEXT_TOKENS, int(total_context_tokens))
    reserve = max(4_096, min(72_000, int(total * 0.12)))
    return max(MIN_USABLE_CONTEXT_TOKENS, total - reserve)


@dataclass
class ModelConfig:
    """模型名与可选显式上下文窗口。

    ``context_window`` 为 ``None`` 时：若 ``model`` 非空则尝试 LiteLLM，否则使用
    :data:`DEFAULT_MODEL_CONTEXT_WINDOW`。

    Attributes:
        model: 模型名。
        context_window: 显式声明窗口（tokens）；``None`` 表示按上式自动解析。
    """

    model: str = ""
    context_window: Optional[int] = None

    @property
    def declared_context_window(self) -> int:
        """声明的总上下文 token 上限（含下限裁剪）。

        :returns: 总上下文 tokens，至少为 :data:`MIN_USABLE_CONTEXT_TOKENS`。
        """
        if self.context_window is not None:
            return max(MIN_USABLE_CONTEXT_TOKENS, int(self.context_window))
        m = (self.model or "").strip()
        if m:
            lit = _litellm_max_input_tokens(m)
            if lit is not None:
                return max(MIN_USABLE_CONTEXT_TOKENS, lit)
        return DEFAULT_MODEL_CONTEXT_WINDOW

    @property
    def effective_window(self) -> int:
        """输入侧 token 预算（thread 压缩与利用率分母）。

        :returns: :func:`input_token_budget` 作用于 :meth:`declared_context_window` 的结果。
        """
        return input_token_budget(self.declared_context_window)


@dataclass
class LoopConfig:
    """工具循环与 LLM 调用相关限制。"""

    max_rounds: int = 24
    step_timeout: int = 600
    llm_request_timeout: float | None = 120.0

    tool_timeout: float = 30.0
    bash_retries: int = 1
    llm_retries: int = 3
    llm_transient_retries: int = 2
    tool_decision_max_retries: int = 10


@dataclass
class PersistenceConfig:
    """检查点、WAL、日志与归档相关参数。"""

    checkpoint_interval: int = 10
    checkpoint_max: int = 20
    thread_history_max_files: int = 20

    checkpoint_include_workspace: bool = True
    max_log_files: int = 50
    max_memory_entries: int = 5000
    wal_max_entries: int = 1000
    llm_history_max_entries: int = 100
    enable_llm_history: bool = False
    archive_after_days: int = 30


@dataclass
class ContextConfig:
    """对话线程、工具输出与工作区读写的预算与压缩档位。"""

    workspace_cache_max_entries: int = 50
    preload_workspace_paths: list[str] = field(default_factory=list)

    compact_warning_ratio: float = field(default=_COMPACT_WARNING_RATIO, repr=False)
    compact_trigger_ratio: float = field(default=_COMPACT_TRIGGER_RATIO, repr=False)
    compact_auto_ratio: float = field(default=_COMPACT_AUTO_RATIO, repr=False)
    compact_force_ratio: float = field(default=_COMPACT_FORCE_RATIO, repr=False)

    thread_max_messages: int = field(default=_THREAD_MAX_MESSAGES, repr=False)
    thread_max_tokens: int = field(default=_THREAD_MAX_TOKENS, repr=False)
    thread_keep_recent: int = field(default=_THREAD_KEEP_RECENT, repr=False)
    thread_compact_max_chars: int = field(default=100_000, repr=False)
    thread_compact_keep_recent: int = field(default=8, repr=False)

    stdout_max_chars: int = field(default=_STDOUT_MAX_CHARS, repr=False)
    stderr_max_chars: int = field(default=_STDERR_MAX_CHARS, repr=False)
    tool_result_budget: int = field(default=_TOOL_RESULT_BUDGET, repr=False)
    tool_result_thread_budget: int = field(default=64_000, repr=False)

    workspace_read_chunk_cap: int = field(default=_WORKSPACE_READ_CHUNK_CAP, repr=False)
    workspace_chunk_size: int = field(default=32_768, repr=False)
    key_state_file_limit: int = field(default=5000, repr=False)

    tool_table_mode: str = field(default="full", repr=False)
    grep_max_files: int = field(default=2000, repr=False)
    grep_max_matches: int = field(default=1000, repr=False)
    grep_max_file_bytes: int = field(default=2 * 1024 * 1024, repr=False)
    summary_msg_limit: int = field(default=10, repr=False)
    summary_msg_short_limit: int = field(default=5, repr=False)
    summary_char_budget: int = field(default=4000, repr=False)
    model_context_window: int = field(default=DEFAULT_MODEL_CONTEXT_WINDOW, repr=False)
    world_desc_max_chars: int = field(default=10_000, repr=False)
    workspace_snapshot_str_cap: int = field(default=5_000, repr=False)
    thread_key_state_paths: list[str] = field(default_factory=list, repr=False)
    system_prompt_max_identity_chars: int = field(default=10_000, repr=False)
    tiktoken_encoding: str = field(default=_TIKTOKEN_ENCODING, repr=False)
    profile_max_chars: int = field(default=4000, repr=False)


@dataclass
class LoopDetectionConfig:
    """工具与内容重复、错误风暴等循环行为检测阈值。"""

    max_tool_repeats: int = field(default=_MAX_TOOL_REPEATS, repr=False)
    max_content_repeats: int = field(default=_MAX_CONTENT_REPEATS, repr=False)
    max_error_repeats: int = field(default=_MAX_ERROR_REPEATS, repr=False)
    history_size: int = field(default=_LOOP_HISTORY_SIZE, repr=False)
    overuse_threshold: int = field(default=15, repr=False)


@dataclass
class ConcurrencyConfig:
    """并行工具、LLM 请求、子进程与全局限流。"""

    max_parallel_tools: int = field(default=_MAX_PARALLEL_TOOLS, repr=False)
    max_llm_concurrent: int = field(default=_MAX_LLM_CONCURRENT, repr=False)
    max_subprocess: int = field(default=_MAX_SUBPROCESS, repr=False)
    rate_limit_rps: float = field(default=_RATE_LIMIT_RPS, repr=False)


@dataclass
class StateConfig:
    """Agent 状态 JSON 文件名与摘要字段名的映射。"""

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
        """合并内置与扩展状态映射。

        :returns: 状态名到 ``(json 文件名, 摘要字段名)`` 的浅拷贝。
        """
        result = dict(self.builtin_states)
        result.update(self.extra_states)
        return result


@dataclass
class AgentConfig:
    """根配置：聚合 ``ModelConfig``、``LoopConfig``、``ContextConfig`` 等子对象。"""

    model: ModelConfig = field(default_factory=ModelConfig)
    loop: LoopConfig = field(default_factory=LoopConfig)
    context: ContextConfig = field(default_factory=ContextConfig)
    persistence: PersistenceConfig = field(default_factory=PersistenceConfig)
    concurrency: ConcurrencyConfig = field(default_factory=ConcurrencyConfig)
    loop_detection: LoopDetectionConfig = field(default_factory=LoopDetectionConfig)
    state: StateConfig = field(default_factory=StateConfig)
    workspace_path: str = ""

    def __post_init__(self) -> None:
        self._sync_context_window_budget()

    def _sync_context_window_budget(self) -> None:
        """令 ``context.model_context_window`` 与 ``model.effective_window`` 一致。"""
        self.context.model_context_window = self.model.effective_window

    @classmethod
    def from_env(cls) -> "AgentConfig":
        """从环境变量构造实例。

        使用 ``AGENT_MODEL``、``AGENT_CONTEXT_WINDOW``（可选）、``AGENT_MAX_TOOL_ROUNDS``、
        ``AGENT_STEP_TIMEOUT``、``AGENT_LLM_REQUEST_TIMEOUT``（单次补全超时秒数，0/none 关闭）、
        ``AGENT_CHECKPOINT_INTERVAL``。

        :returns: 新构建的 ``AgentConfig``。
        """
        cw: Optional[int] = None
        if "AGENT_CONTEXT_WINDOW" in os.environ:
            cw = max(
                MIN_USABLE_CONTEXT_TOKENS,
                _int("AGENT_CONTEXT_WINDOW", DEFAULT_MODEL_CONTEXT_WINDOW),
            )
        return cls(
            model=ModelConfig(
                model=os.getenv("AGENT_MODEL", ""),
                context_window=cw,
            ),
            loop=LoopConfig(
                max_rounds=_int("AGENT_MAX_TOOL_ROUNDS", 24),
                step_timeout=_int("AGENT_STEP_TIMEOUT", 600),
                llm_request_timeout=_optional_positive_float(
                    "AGENT_LLM_REQUEST_TIMEOUT", 120.0
                ),
            ),
            persistence=PersistenceConfig(
                checkpoint_interval=_int("AGENT_CHECKPOINT_INTERVAL", 10),
            ),
        )

    @classmethod
    def from_kwargs(cls, kwargs: dict | None = None) -> "AgentConfig":
        """将约定字段名写入各子配置。

        :param kwargs: 例如 ``model``、``context_window``、``max_tool_rounds``、``llm_transient_retries``、
            ``tool_decision_max_retries``、``bash_retries`` / ``bash_timeout_retries``、``tiktoken_encoding``；
            ``None`` 视为空映射。

        :returns: 新构建的 ``AgentConfig``。未识别的键忽略；数值字段会裁剪到允许范围。
        """
        raw = kwargs or {}
        if not isinstance(raw, dict) or not raw:
            return cls()

        cfg = cls()

        def _as_int(v: object, default: int) -> int:
            try:
                return int(v)  # type: ignore[arg-type]
            except Exception:
                return default

        def _as_bool(v: object, default: bool = False) -> bool:
            if isinstance(v, bool):
                return v
            if isinstance(v, (int, float)):
                return bool(v)
            s = str(v).strip().lower()
            if s in {"1", "true", "yes", "y", "on"}:
                return True
            if s in {"0", "false", "no", "n", "off"}:
                return False
            return default

        def _as_list_str(v: object) -> list[str]:
            if v is None:
                return []
            if isinstance(v, list):
                return [str(x) for x in v if str(x).strip()]
            if isinstance(v, tuple):
                return [str(x) for x in v if str(x).strip()]
            s = str(v).strip()
            return [s] if s else []

        if "max_tool_rounds" in raw:
            cfg.loop.max_rounds = max(
                1, _as_int(raw.get("max_tool_rounds"), cfg.loop.max_rounds)
            )
        if "step_timeout" in raw:
            cfg.loop.step_timeout = max(
                5, _as_int(raw.get("step_timeout"), cfg.loop.step_timeout)
            )
        if "llm_request_timeout" in raw:
            v = raw.get("llm_request_timeout")
            if v is None or str(v).strip().lower() in ("none", "", "0", "false"):
                cfg.loop.llm_request_timeout = None
            else:
                try:
                    f = float(v)  # type: ignore[arg-type]
                    cfg.loop.llm_request_timeout = f if f > 0 else None
                except (TypeError, ValueError):
                    pass

        if "llm_transient_retries" in raw:
            cfg.loop.llm_transient_retries = max(
                0,
                _as_int(
                    raw.get("llm_transient_retries"), cfg.loop.llm_transient_retries
                ),
            )
        if "tool_decision_max_retries" in raw:
            cfg.loop.tool_decision_max_retries = max(
                0,
                _as_int(
                    raw.get("tool_decision_max_retries"),
                    cfg.loop.tool_decision_max_retries,
                ),
            )
        if "bash_retries" in raw or "bash_timeout_retries" in raw:
            v = raw.get("bash_retries", raw.get("bash_timeout_retries"))
            cfg.loop.bash_retries = max(0, _as_int(v, cfg.loop.bash_retries))

        if "preload_workspace_paths" in raw:
            cfg.context.preload_workspace_paths = _as_list_str(
                raw.get("preload_workspace_paths")
            )
        if "thread_key_state_paths" in raw:
            cfg.context.thread_key_state_paths = _as_list_str(
                raw.get("thread_key_state_paths")
            )

        if "workspace_read_chunk_chars" in raw:
            cap = _as_int(
                raw.get("workspace_read_chunk_chars"),
                cfg.context.workspace_read_chunk_cap,
            )
            cfg.context.workspace_read_chunk_cap = max(1024, min(96_000, cap))

        if "tool_result_thread_budget_chars" in raw:
            bud = _as_int(
                raw.get("tool_result_thread_budget_chars"),
                cfg.context.tool_result_thread_budget,
            )
            cfg.context.tool_result_thread_budget = max(4096, min(256_000, bud))

        if "system_prompt_max_identity_chars" in raw:
            mx = _as_int(
                raw.get("system_prompt_max_identity_chars"),
                cfg.context.system_prompt_max_identity_chars,
            )
            cfg.context.system_prompt_max_identity_chars = max(2000, min(200_000, mx))

        if "profile_max_chars" in raw or "profile_truncate_chars" in raw:
            v = raw.get("profile_max_chars", raw.get("profile_truncate_chars"))
            mx = _as_int(v, cfg.context.profile_max_chars)
            cfg.context.profile_max_chars = max(512, min(200_000, mx))

        if "enable_llm_history" in raw:
            cfg.persistence.enable_llm_history = _as_bool(
                raw.get("enable_llm_history"), cfg.persistence.enable_llm_history
            )
        if "llm_history_max_entries" in raw:
            cfg.persistence.llm_history_max_entries = max(
                0,
                _as_int(
                    raw.get("llm_history_max_entries"),
                    cfg.persistence.llm_history_max_entries,
                ),
            )

        if "model" in raw or "llm_model" in raw:
            m = raw.get("model", raw.get("llm_model"))
            if m is not None:
                cfg.model.model = str(m).strip()

        if "context_window" in raw or "agent_context_window" in raw:
            v = raw.get("context_window", raw.get("agent_context_window"))
            cw = _as_int(v, cfg.model.declared_context_window)
            cfg.model.context_window = max(MIN_USABLE_CONTEXT_TOKENS, cw)

        if "tiktoken_encoding" in raw:
            enc = str(raw.get("tiktoken_encoding") or "").strip()
            if enc:
                cfg.context.tiktoken_encoding = enc

        cfg._sync_context_window_budget()
        return cfg

    def to_dict(self) -> dict:
        """将子配置序列化为可 JSON 化的嵌套字典。

        :returns: 含 ``model``、``loop``、``context``、``persistence``、``concurrency``、 ``loop_detection`` 键；不含 ``workspace_path`` 与 ``state``。
        """
        import dataclasses

        result = {}
        for name in [
            "model",
            "loop",
            "context",
            "persistence",
            "concurrency",
            "loop_detection",
        ]:
            result[name] = dataclasses.asdict(getattr(self, name))
        return result


DEFAULT_CONFIG = AgentConfig()
