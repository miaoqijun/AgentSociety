"""PersonAgent：skills-first 工具代理。

核心特性：
- 独立工作区：每个 agent 的文件与日志隔离
- 独立会话线程：维护短上下文，必要时 LLM 压缩
- 渐进式 skill 发现：先看 catalog，再按需激活
- 工具循环：产出 ToolDecision → 执行 → 回写结果，直到 done
"""

from __future__ import annotations

import asyncio
import re
import shlex
from collections.abc import Mapping
from datetime import datetime
from fnmatch import fnmatch
from typing import Any, Optional

from agentsociety2.agent.base import AgentBase
from agentsociety2.agent.context import (
    AgentMemory,
    StructuredSummary,
    load_rolling_summary_from_workspace,
    run_thread_compaction,
    save_thread_compact_state,
)
from agentsociety2.agent.context_config import get_config_for_agent
from agentsociety2.agent.skills import SkillRegistry, get_skill_registry
from agentsociety2.agent.skills.runtime import AgentSkillRuntime
from agentsociety2.agent.tool import (
    BLOCKED_TOKENS,
    ToolDecision,
    async_retry_on_transient,
    jr_dumps,
    jr_parse,
    json_dumps_tool_result_for_thread,
    pagination_from_args,
    slice_text_page,
    trunc_str,
)
from agentsociety2.agent.tool.loop_detection import (
    LoopDetectionService,
    LoopDetectionConfig,
)
from agentsociety2.env import (
    PersonStepConstraints,
    RouterBase,
    merge_person_step_constraints,
)
from agentsociety2.logger import get_logger
from agentsociety2.storage import ReplayWriter

logger = get_logger()


class PersonAgent(AgentBase):
    """Person 场景下的 skills-first 工具代理。

    设计目标是让每个 Person 拥有独立线程、独立工作区和独立技能可见性，
    在每个 step 内通过工具循环完成“观察-推理-行动”。
    """

    @classmethod
    def mcp_description(cls) -> str:
        """返回 MCP 候选列表中的简短描述。"""
        return (
            "PersonAgent: Minimal skills-first agent. "
            "Uses progressive skill loading and isolated agent workspace."
        )

    _TOOL_SPECS: tuple[tuple[str, str, str], ...] = (
        (
            "activate_skill",
            "skill_name, arguments",
            "Load skill instructions (optional args)",
        ),
        (
            "read_skill",
            "skill_name, path, offset?, limit?",
            "Read skill file (paginate with offset/limit)",
        ),
        ("execute_skill", "skill_name, args", "Run a skill's subprocess script"),
        ("bash", "command, timeout_sec", "Shell command in workspace"),
        ("codegen", "instruction, ctx", "Send instruction to the environment"),
        (
            "workspace_read",
            "path, offset?, limit?",
            "Read workspace file (paginate with offset/limit)",
        ),
        ("workspace_write", "path, content", "Write file"),
        ("workspace_list", "path", "List files"),
        ("glob", "glob, path", "Find files by pattern"),
        ("grep", "pattern, glob, path", "Search file contents"),
        ("enable_skill", "skill_name", "Reveal a hidden skill"),
        ("disable_skill", "skill_name", "Hide a skill"),
        (
            "batch",
            "operations",
            "Execute multiple operations in one call",
        ),
        ("done", "(done=true, summary)", "Finish this step"),
    )

    @classmethod
    def _render_tool_table(cls) -> str:
        lines = ["| Tool | Arguments | Purpose |", "|------|-----------|----------|"]
        for name, arguments, purpose in cls._TOOL_SPECS:
            lines.append(f"| {name} | {arguments} | {purpose} |")
        return "\n".join(lines)

    def __init__(
        self,
        id: int,
        profile: Any,
        name: Optional[str] = None,
        replay_writer: Optional[ReplayWriter] = None,
        init_state: Optional[dict[str, Any]] = None,
        **capability_kwargs: Any,
    ):
        """初始化 PersonAgent。

        :param id: Agent 唯一标识。
        :param profile: 画像对象（dict 或可序列化对象）。
        :param name: 可选显示名。
        :param replay_writer: 可选回放写入器。
        :param init_state: 可选初始状态（会写入 workspace，默认不覆盖已存在文件）。
        :param capability_kwargs: 行为/能力参数（节选）：

            - ``max_tool_rounds``：单步最大工具轮数（默认 24）
            - ``preload_workspace_paths``：预读文件列表（注入 system prompt 的 workspace 快照）
            - ``thread_key_state_paths``：thread 压缩时附带的 KEY_STATE_JSON 文件路径列表
            - ``catalog_working_set_json``：用于 skill 的 ``paths`` 匹配信号文件（如 ``working_set.json``）
            - ``system_prompt_max_identity_chars``：Agent Identity JSON 总长度上限（默认 10000）
            - ``workspace_read_chunk_chars``：``workspace_read`` / ``read_skill`` 单段最大字符数（默认 32768，上限 96000）
            - ``tool_result_thread_budget_chars``：单条 TOOL_RESULT_JSON 序列化预算（默认 65536）
            - ``profile_truncate_chars``：profile 超过该长度时截断再进 Identity（默认 8000）
            - ``bash_timeout_retries``：bash 超时后的额外重试次数（默认 1，即最多 2 次执行）
            - ``llm_transient_retries``：thread 压缩等直连 ``acompletion`` 遇瞬时错误时的最大重试次数（默认 2）
            - ``tool_decision_max_retries``：传给 ``acompletion_with_pydantic_validation`` 的 max_retries（默认 10）
            - ``model`` / ``llm_model``：LiteLLM 路由模型名（用于 token_counter 与 tiktoken 回退）
            - ``tiktoken_encoding``：强制指定 tiktoken 编码名（可选）
        """
        super().__init__(id=id, profile=profile, name=name, replay_writer=replay_writer)
        self._agent_state: dict[str, Any] = self._coerce_llm_dict(init_state)
        self._capability_kwargs: dict[str, Any] = dict(capability_kwargs)

        base_registry = get_skill_registry()
        self._skill_registry = SkillRegistry()
        self._skill_registry.copy_from(base_registry)
        self._skill_runtime = AgentSkillRuntime(
            agent_id=id, registry=self._skill_registry
        )
        self._selectable_skill_names: set[str] = set()
        self._skill_visibility_overrides: dict[str, bool] = {}
        self._activated_skills: set[str] = set()
        self._active_skill_scope: str = ""

        self._step_count = 0
        self._last_selected_skills: set[str] = set()
        self._max_tool_rounds = max(
            1, int(self._capability_kwargs.get("max_tool_rounds", 24))
        )
        self._bash_timeout_retries = max(
            0, int(self._capability_kwargs.get("bash_timeout_retries", 1))
        )
        self._llm_transient_retries = max(
            0, int(self._capability_kwargs.get("llm_transient_retries", 2))
        )
        self._tool_decision_max_retries = max(
            0, int(self._capability_kwargs.get("tool_decision_max_retries", 10))
        )

        # ── 统一的上下文配置管理 ──
        self._ctx_config = get_config_for_agent(
            capability_kwargs=self._capability_kwargs,
        )

        # 上下文缓存：避免重复读取相同文件
        self._workspace_cache: dict[str, str] = {}
        self._cache_valid_paths: set[str] = set()
        # 当前 step 的上下文快照（在 step 开始时构建）
        self._step_context: dict[str, Any] = {}
        # workspace 状态版本：每次可能改动工作区后递增，避免模型使用过期上下文
        self._workspace_state_version: int = 0
        # 环境工具经 Router 改写后的世界描述，在 init 时拉取并注入 system prompt
        self._world_description: str = ""
        # 本步 get_system_prompt 用：_prepare_prompt_sidecars 写入（长 prose 走 LLM 压缩）
        self._world_description_for_prompt: str = ""
        self._workspace_snapshot_for_prompt: dict[str, Any] = {}
        self._profile_for_prompt: Any = None

        # ── 上下文管理改进 ──
        # 持久化记忆（类似 CLAUDE.md）
        self._memory: Optional[AgentMemory] = None
        # 结构化摘要
        self._structured_summary: Optional[StructuredSummary] = None
        # 上下文利用率追踪
        self._last_utilization: float = 0.0
        self._compact_count: int = 0
        # 跨压缩轮次的滚动摘要（增量合并，持久化见 thread_compact_state.json）
        self._rolling_thread_summary: str = ""

        # ── 系统提示词缓存 ──
        self._prompt_cache: str | None = None
        self._prompt_cache_version: int = 0
        self._cached_skills: set[str] = set()
        self._cached_ws_version: int = 0

        # ── 循环检测 ──
        self._loop_detector = LoopDetectionService(LoopDetectionConfig())

    def _all_visible_skill_names(self) -> set[str]:
        """返回当前 agent 可见技能名集合副本。"""
        return set(self._selectable_skill_names)

    def _invalidate_prompt_cache(self) -> None:
        """失效系统提示词缓存。"""
        self._prompt_cache = None
        self._prompt_cache_version += 1

    def _need_rebuild_prompt(self) -> bool:
        """判断是否需要重建系统提示词。"""
        if self._prompt_cache is None:
            return True
        if self._activated_skills != self._cached_skills:
            return True
        if self._workspace_state_version != self._cached_ws_version:
            return True
        return False

    def _workspace_preload_paths(self) -> list[str]:
        """获取预加载的 workspace 文件路径列表。

        从 capability_kwargs['preload_workspace_paths'] 读取。

        :return: 路径字符串列表。
        """
        raw = self._capability_kwargs.get("preload_workspace_paths")
        if isinstance(raw, (list, tuple)):
            return [str(x).strip() for x in raw if str(x).strip()]
        return []

    def _thread_key_state_paths(self) -> list[str]:
        """获取 thread 压缩时写入 KEY_STATE_JSON 的文件路径列表。

        从 capability_kwargs['thread_key_state_paths'] 读取。

        :return: 路径字符串列表。
        """
        raw = self._capability_kwargs.get("thread_key_state_paths")
        if isinstance(raw, (list, tuple)):
            return [str(x).strip() for x in raw if str(x).strip()]
        return []

    def _build_step_context(self) -> dict[str, Any]:
        """构建当前 step 的上下文快照。

        预读 capability_kwargs['preload_workspace_paths'] 列出的路径，
        同时更新缓存供后续操作使用。单个文件读取失败不会中断整体构建。
        """
        context: dict[str, Any] = {}

        for path in self._workspace_preload_paths():
            try:
                if self._skill_runtime.workspace_exists(path):
                    content = self._skill_runtime.workspace_read(path)
                    if content:
                        if path.endswith(".json"):
                            parsed = jr_parse(content)
                            context[path] = parsed if isinstance(parsed, dict) else {}
                        else:
                            context[path] = content
                        self._workspace_cache[path] = content
                        self._cache_valid_paths.add(path)
            except Exception as e:
                logger.warning(f"Failed to preload {path}: {e}")

        self._step_context = context
        return context

    def _invalidate_workspace_cache(self, path: str) -> None:
        """失效指定路径的缓存。

        :param path: 文件路径。
        """
        self._cache_valid_paths.discard(path)
        self._step_context.pop(path, None)

    def _get_cached_workspace_content(self, path: str) -> Optional[str]:
        """从缓存获取文件内容。

        :param path: 文件路径。
        :return: 缓存内容，未命中返回 None。
        """
        if path in self._cache_valid_paths:
            return self._workspace_cache.get(path)
        return None

    def _invalidate_all_workspace_cache(self) -> None:
        """清空全部 workspace 缓存。"""
        self._cache_valid_paths.clear()
        self._workspace_cache.clear()
        self._step_context = {}

    def _bump_workspace_state_version(self) -> int:
        """递增 workspace 状态版本号并返回新值。"""
        self._workspace_state_version += 1
        return self._workspace_state_version

    def _workspace_read_chunk_cap(self) -> int:
        """获取单次文件读取的字符上限。"""
        raw = self._capability_kwargs.get("workspace_read_chunk_chars")
        if raw is None:
            return self._ctx_config.workspace_read_chunk_cap
        return max(4096, min(int(raw), 96_000))

    def _tool_result_thread_budget_chars(self) -> int:
        """获取单条工具结果的字符预算。"""
        raw = self._capability_kwargs.get("tool_result_thread_budget_chars")
        if raw is None:
            return self._ctx_config.tool_result_thread_budget
        return max(16_384, min(int(raw), 200_000))

    @staticmethod
    def _coerce_llm_dict(raw: Any) -> dict[str, Any]:
        """把「应为 dict」的字段归一成 dict。

        用于 ToolDecision.arguments、codegen.ctx、execute_skill.args 等。

        :param raw: 原始值。
        :return: dict。
        """
        if raw is None:
            return {}
        if isinstance(raw, Mapping):
            return dict(raw)
        if isinstance(raw, str):
            s = raw.strip()
            if not s:
                return {}
            parsed = jr_parse(s)
            return dict(parsed) if isinstance(parsed, dict) else {}
        return {}

    @staticmethod
    def _sanitize_profile_for_prompt(profile: Any) -> Any:
        """过滤 profile 中的潜在指令注入。

        :param profile: 原始 profile。
        :return: 安全的 profile。
        """
        if isinstance(profile, str):
            # 移除可能的指令注入标记
            profile = re.sub(
                r"^\s*(SYSTEM|INSTRUCTION|ACT|PROMPT|IGNORE)\s*:",
                "",
                profile,
                flags=re.IGNORECASE | re.MULTILINE,
            )
            return profile
        if isinstance(profile, dict):
            return {
                k: PersonAgent._sanitize_profile_for_prompt(v)
                for k, v in profile.items()
            }
        if isinstance(profile, list):
            return [PersonAgent._sanitize_profile_for_prompt(item) for item in profile]
        return profile

    def _agent_identity_json_for_prompt(self) -> str:
        """生成用于 system prompt 的智能体身份 JSON。

        profile 过长时硬切并标记省略。
        """
        max_total = max(
            2000,
            int(self._capability_kwargs.get("system_prompt_max_identity_chars", 10000)),
        )
        raw_profile = (
            self._profile_for_prompt
            if self._profile_for_prompt is not None
            else self.get_profile()
        )
        # 安全过滤
        safe_profile = self._sanitize_profile_for_prompt(raw_profile)
        agent_identity: dict[str, Any] = {
            "id": self.id,
            "name": self._name,
            "profile": safe_profile,
        }
        s = jr_dumps(agent_identity)
        if len(s) <= max_total:
            return s
        agent_identity["profile"] = "<omitted: profile too large>"
        return jr_dumps(agent_identity)

    # ── System Prompt ──────────────────────────────────────────────────────────

    def get_system_prompt(self, tick: int, t: datetime) -> str:
        """构建本步 system prompt。

        注入 world description、agent identity、工具协议、skill catalog、已激活技能列表。
        使用缓存机制避免重复构建。

        :param tick: 当前仿真步时间跨度（秒）。
        :param t: 当前仿真时间。
        :return: system prompt 文本。
        """
        # 检查是否可以使用缓存
        if not self._need_rebuild_prompt() and self._prompt_cache is not None:
            return self._prompt_cache

        base = super().get_system_prompt(tick, t)

        wd = (self._world_description_for_prompt or self._world_description).strip()
        world_block = ""
        if wd:
            world_block = (
                "\n\n# World Description\n"
                "Environment-specific modules, tools, and action conventions:\n\n"
                f"{wd}\n"
            )

        visible_names = sorted(self._all_visible_skill_names())
        catalog_names: list[str] = []
        for n in visible_names:
            info = self._skill_registry.get_skill_info(n, load_content=False)
            if info is None:
                continue
            if getattr(info, "disable_model_invocation", False):
                continue
            patterns = list(getattr(info, "paths", []) or [])
            if patterns and not self._catalog_paths_match(patterns):
                continue
            catalog_names.append(n)
        catalog = self._skill_runtime.skill_list(catalog_names)

        skill_section = (
            f"\n\n# Agent Identity\n"
            f"{self._agent_identity_json_for_prompt()}\n"
            "\n# This simulation step\n"
            "The persona and behavioral guidelines above set motivation and realism. "
            "Within this step you must act only through the tool JSON protocol below: "
            "each assistant turn is exactly one tool call (`batch` still counts as one `tool_name`).\n"
        )

        # 注入 workspace 结构说明（Cursor风格动态发现）
        skill_section += f"\n{self._skill_runtime.build_workspace_structure_prompt()}\n"

        ctx_view = (
            self._workspace_snapshot_for_prompt
            if self._workspace_snapshot_for_prompt
            else self._step_context
        )
        if ctx_view:
            skill_section += (
                f"\n# Workspace State (pre-loaded)\n"
                "Below is a snapshot of common workspace files for faster context.\n"
                "Important: after any write/execute/codegen action, snapshot content may become stale; "
                "use `workspace_read` to fetch latest source of truth when correctness matters.\n"
                f"```json\n{jr_dumps(ctx_view, indent=1)}\n```\n"
            )

        skill_section += (
            "\n# Tool protocol (output shape)\n"
            "Respond ONLY with valid JSON: {tool_name, arguments, done, summary}. "
            "`arguments` must be a JSON object (use {} if no parameters).\n"
            "For execute_skill use arguments.args as a JSON object; for codegen use arguments.ctx as a JSON object "
            "(prefer objects over stringified JSON; the runtime parses strings with json_repair).\n"
            "For activate_skill set arguments.skill_name; optional arguments.arguments (string or list) feeds "
            "SKILL.md placeholders like $ARGUMENTS / $0.\n\n"
            "# Skills\n"
            "The catalog lists name + short description only (progressive disclosure). "
            "Use `activate_skill` to load full SKILL.md, then follow it.\n"
            "If TOOL_RESULT_JSON reports blocked/visibility/dependency errors, adjust the next tool call.\n\n"
            "# Execution Rules\n"
            "- Do not invent tools or fields. `tool_name` must match the Tools table exactly.\n"
            "- Never set tool_name to a catalog skill name. Use activate_skill with arguments.skill_name.\n"
            "- To drive the **shared simulation environment** (observe, submit, status), use `codegen` with a clear "
            "instruction; the runtime merges your numeric id into ctx.\n"
            "- Prefer skill-driven execution: activate -> read/execute -> workspace operations -> done.\n"
            "- Long files: use `workspace_read` or `read_skill` with `arguments.offset` (0-based char index in decoded "
            "text) and optional `arguments.limit`; if `has_more` is true, call again with `offset=next_offset`.\n"
            "- Keep `summary` concise and factual.\n"
            "- Use `batch` only when allowed by the active skill's allowed-tools (if any).\n\n"
        )
        pc = self._merged_person_step_constraints()
        if pc:
            skill_section += (
                "# Environment step constraints\n"
                "This step has environment-imposed limits: only skills listed in the catalog above exist for you. "
                "If an active skill declares allowed-tools, do not call tools outside that list.\n"
            )
            if pc.pin_allowed_tools_to_skill:
                skill_section += (
                    f"Allowed-tools scope is pinned to `{pc.pin_allowed_tools_to_skill}` at step start; "
                    "follow that skill's SKILL.md for codegen vs workspace.\n"
                )
        skill_section += (
            "# Tools\n"
            f"{self._render_tool_table()}\n\n"
            f"# Skill Catalog\n{jr_dumps(catalog, indent=1)}\n\n"
            f"# Activated Skills\n{jr_dumps(sorted(self._activated_skills))}"
        )

        result = base + world_block + skill_section

        # 更新缓存
        self._prompt_cache = result
        self._cached_skills = set(self._activated_skills)
        self._cached_ws_version = self._workspace_state_version

        return result

    # ── Thread Management ─────────────────────────────────────────────────────

    def _append_tool_result_to_thread(
        self,
        thread_messages: list[dict[str, str]],
        tick: int,
        t: datetime,
        result_obj: dict[str, Any],
    ) -> None:
        """将工具结果写入 thread（同时写磁盘与内存窗口）。

        :param thread_messages: thread 消息列表。
        :param tick: 当前仿真步的时间尺度（秒）。
        :param t: 当前仿真时间。
        :param result_obj: 工具执行结果字典。
        """
        enriched = dict(result_obj)
        enriched.setdefault("workspace_state_version", self._workspace_state_version)
        payload = json_dumps_tool_result_for_thread(
            enriched, budget=self._tool_result_thread_budget_chars()
        )
        content = "TOOL_RESULT_JSON:\n" + payload
        self._skill_runtime.append_thread_message("user", content, tick=tick, t=t)
        thread_messages.append({"role": "user", "content": content})
        if len(thread_messages) > self._ctx_config.thread_max_messages:
            thread_messages = thread_messages[-self._ctx_config.thread_max_messages :]

    def _prepare_prompt_sidecars(self) -> None:
        """准备 prompt 侧车数据。

        对 world_description、workspace_snapshot、profile 做硬切处理，
        这些是非关键数据，无需 LLM 压缩。
        """
        wd = self._world_description.strip()
        self._world_description_for_prompt = (
            trunc_str(wd, self._ctx_config.world_desc_max_chars)
            if len(wd) > self._ctx_config.world_desc_max_chars
            else wd
        )

        self._workspace_snapshot_for_prompt = {}
        for path, v in self._step_context.items():
            if (
                isinstance(v, str)
                and len(v) > self._ctx_config.workspace_snapshot_str_cap
            ):
                self._workspace_snapshot_for_prompt[path] = trunc_str(
                    v, self._ctx_config.workspace_snapshot_str_cap
                )
            else:
                self._workspace_snapshot_for_prompt[path] = v

        prof = self.get_profile()
        plim = int(
            self._capability_kwargs.get(
                "profile_truncate_chars", self._ctx_config.profile_max_chars
            )
        )
        if isinstance(prof, str):
            self._profile_for_prompt = (
                trunc_str(prof, plim) if len(prof) > plim else None
            )
        elif prof is not None:
            dumped = jr_dumps(prof)
            self._profile_for_prompt = (
                trunc_str(dumped, plim) if len(dumped) > plim else None
            )

    def _catalog_paths_match(self, patterns: list[str]) -> bool:
        """检查当前工作集是否匹配任一模式。

        用于 skill 的 paths 过滤。若无工作集信号，返回 True 以避免意外隐藏 skill。

        :param patterns: 路径模式列表。
        :return: 是否匹配。
        """
        if not patterns:
            return True

        signal = self._capability_kwargs.get("catalog_working_set_json")
        if not signal or not str(signal).strip():
            return True
        signal = str(signal).strip()

        candidates: list[str] = []
        obs_raw = self._step_context.get(signal)
        if obs_raw is None and self._skill_runtime.workspace_exists(signal):
            raw_text = self._skill_runtime.workspace_read(signal)
            if raw_text.strip():
                parsed = jr_parse(raw_text)
                obs_raw = parsed if isinstance(parsed, dict) else {}
        obs = obs_raw if isinstance(obs_raw, dict) else {}
        for key in ("path", "paths", "file", "files", "working_dir", "cwd"):
            v = obs.get(key)
            if isinstance(v, str) and v.strip():
                candidates.append(v.strip())
            elif isinstance(v, list):
                candidates.extend(str(x).strip() for x in v if str(x).strip())

        if not candidates:
            return True

        for c in candidates:
            for p in patterns:
                if fnmatch(c, p):
                    return True
        return False

    def _is_model_invocable_skill(self, skill_name: str) -> bool:
        """检查 skill 是否可被模型自动调用。

        :param skill_name: skill 名称。
        :return: 是否可自动调用。
        """
        info = self._skill_registry.get_skill_info(skill_name, load_content=False)
        if info is None:
            return False
        return not bool(getattr(info, "disable_model_invocation", False))

    @staticmethod
    def _normalize_allowed_tools(raw: list[str]) -> set[str]:
        """将 skill frontmatter 的 allowed-tools 归一到 PersonAgent 的 tool_name 集合。

        :param raw: 原始 allowed-tools 列表。
        :return: 标准化后的 tool_name 集合。
        """
        if not raw:
            return set()

        mapping = {
            "read": "workspace_read",
            "write": "workspace_write",
            "workspace_read": "workspace_read",
            "workspace_write": "workspace_write",
            "workspace_list": "workspace_list",
            "activate_skill": "activate_skill",
            "read_skill": "read_skill",
            "execute_skill": "execute_skill",
            "bash": "bash",
            "grep": "grep",
            "glob": "glob",
            "codegen": "codegen",
            "batch": "batch",
            "enable_skill": "enable_skill",
            "disable_skill": "disable_skill",
            "done": "done",
        }
        out: set[str] = set()
        for item in raw:
            s = str(item).strip()
            if not s:
                continue
            base = s.split("(", 1)[0].strip().lower()
            if base in mapping:
                out.add(mapping[base])
        return out

    def _allowed_tools_for_active_scope(self) -> set[str] | None:
        """获取当前 scope 的 allowed-tools。

        :return: allowed-tools 集合，None 表示不限制。
        """
        name = self._active_skill_scope.strip()
        if not name:
            return None
        info = self._skill_registry.get_skill_info(name, load_content=False)
        if info is None:
            return None
        raw_list = getattr(info, "allowed_tools", []) or []
        if not raw_list:
            return None
        return self._normalize_allowed_tools(raw_list)

    def _check_allowed_tools_for_action(self, action: str) -> dict[str, Any] | None:
        """统一处理 allowed-tools 拦截。

        Args:
            action: 工具名称。

        Returns:
            None 表示允许，否则返回错误对象。
        """
        guarded_actions = {
            "workspace_read",
            "workspace_write",
            "workspace_list",
            "bash",
            "glob",
            "grep",
            "codegen",
            "batch",
        }
        if action not in guarded_actions:
            return None
        allowed = self._allowed_tools_for_active_scope()
        if allowed is None or action in allowed:
            return None
        return {
            "action": action,
            "ok": False,
            "error": f"blocked by allowed-tools of active skill: {self._active_skill_scope}",
        }

    @staticmethod
    def _split_skill_arguments(raw: Any) -> tuple[str, list[str]]:
        """解析 activate_skill 的 arguments 为原始串与分词数组。

        :param raw: 原始 arguments（None、list 或 str）。
        :return: 元组 (原始串, 分词数组)。
        """
        if raw is None:
            return "", []
        if isinstance(raw, list):
            parts = [str(x).strip() for x in raw if str(x).strip()]
            return " ".join(parts), parts
        s = str(raw).strip()
        if not s:
            return "", []
        parts = [x for x in shlex.split(s) if x]
        return s, parts

    @staticmethod
    def _inject_skill_arguments(
        content: str, arguments_raw: str, arguments_parts: list[str]
    ) -> str:
        """将 $ARGUMENTS/$ARGUMENTS[N]/$N 占位符渲染到 skill 内容。

        :param content: skill 原始内容。
        :param arguments_raw: 原始参数字符串。
        :param arguments_parts: 分词后的参数数组。
        :return: 渲染后的内容。
        """
        rendered = content.replace("$ARGUMENTS", arguments_raw)

        def repl_indexed(m: re.Match[str]) -> str:
            idx = int(m.group(1))
            return arguments_parts[idx] if 0 <= idx < len(arguments_parts) else ""

        rendered = re.sub(r"\$ARGUMENTS\[(\d+)\]", repl_indexed, rendered)
        rendered = re.sub(r"\$(\d+)", repl_indexed, rendered)

        has_argument_placeholder = ("$ARGUMENTS" in content) or bool(
            re.search(r"\$(\d+)|\$ARGUMENTS\[\d+\]", content)
        )
        if arguments_raw and not has_argument_placeholder:
            rendered += f"\n\nARGUMENTS: {arguments_raw}"
        return rendered

    async def _inject_skill_command_outputs(self, content: str) -> str:
        """注入 !`cmd` 动态上下文。

        命令失败则激活失败。

        :param content: 包含 !`cmd` 占位符的 skill 内容。
        :return: 渲染后的内容。
        """
        pattern = re.compile(r"!\`([^`\n]+)\`")
        rendered = content
        offset = 0
        for m in list(pattern.finditer(content)):
            cmd = m.group(1).strip()
            if not cmd:
                raise ValueError("empty dynamic command")
            out = await self._run_bash_in_workspace(command=cmd, timeout_sec=20)
            if not out.get("ok"):
                raise ValueError(
                    f"dynamic command failed: {cmd}; {out.get('stderr', '')}"
                )
            replacement = str(out.get("stdout", "")).strip()
            start = m.start() + offset
            end = m.end() + offset
            rendered = rendered[:start] + replacement + rendered[end:]
            offset += len(replacement) - (m.end() - m.start())
        return rendered

    # ── Skill Dependency ──────────────────────────────────────────────────────

    def _ensure_requires_activated(
        self,
        tick: int,
        t: datetime,
        thread_messages: list[dict[str, str]],
        skill_name: str,
    ) -> dict[str, Any]:
        """确保 skill 的 requires 依赖已激活。

        :param tick: 当前仿真步的时间尺度（秒）。
        :param t: 当前仿真时间。
        :param thread_messages: thread 消息列表。
        :param skill_name: 需要检查依赖的 skill 名称。
        :return: 包含 ok, requires, activated, missing 字段的字典。
        """
        info = self._skill_registry.get_skill_info(skill_name, load_content=False)
        requires = list(getattr(info, "requires", []) or []) if info else []
        if not requires:
            return {"ok": True, "requires": [], "activated": []}

        missing: list[str] = []
        activated: list[str] = []
        for dep in requires:
            dep = str(dep).strip()
            if not dep:
                continue
            if not self._is_model_invocable_skill(dep):
                missing.append(dep)
                continue
            if dep not in self._all_visible_skill_names():
                missing.append(dep)
                continue
            if dep in self._activated_skills:
                continue
            content = self._skill_runtime.skill_activate(dep)
            if content:
                self._activated_skills.add(dep)
                activated.append(dep)

        if activated:
            self._persist_agent_config()
            self._append_tool_result_to_thread(
                thread_messages=thread_messages,
                tick=tick,
                t=t,
                result_obj={
                    "action": "auto_activate_requires",
                    "skill_name": skill_name,
                    "ok": True,
                    "requires": requires,
                    "activated": activated,
                },
            )

        if missing:
            return {
                "ok": False,
                "requires": requires,
                "activated": activated,
                "missing": missing,
            }
        return {"ok": True, "requires": requires, "activated": activated}

    # ── Command Execution ─────────────────────────────────────────────────────

    async def _run_bash_in_workspace(
        self, command: str, timeout_sec: int
    ) -> dict[str, Any]:
        """在 agent workspace 执行 bash 命令并施加安全限制。

        :param command: bash 命令（在 workspace 根目录执行）。
        :param timeout_sec: 超时秒数。
        :returns: ``{ok, exit_code, stdout, stderr}``。

        .. note::
           这里的护栏是“轻量”的：主要避免越界路径与明显危险 token。
        """
        command = command.strip()
        if not command:
            return {
                "ok": False,
                "exit_code": -1,
                "stdout": "",
                "stderr": "empty command",
            }
        # 基于“默认信任本机”的轻量护栏：
        # - 禁止绝对路径，避免直接读写系统文件
        # - 禁止 ../ 访问上级目录，避免越出 agent workspace 语义
        if re.search(r"(^|[\s'\"();|&])\/", command):
            return {
                "ok": False,
                "exit_code": -1,
                "stdout": "",
                "stderr": "blocked: absolute path",
            }
        if "../" in command or "/.." in command or "..\\" in command:
            return {
                "ok": False,
                "exit_code": -1,
                "stdout": "",
                "stderr": "blocked: parent traversal",
            }
        cmd_lower = command.lower()
        for token in BLOCKED_TOKENS:
            if token in cmd_lower:
                return {
                    "ok": False,
                    "exit_code": -1,
                    "stdout": "",
                    "stderr": f"blocked: contains '{token}'",
                }
        work_dir = self._skill_runtime.workspace_root()
        attempts = self._bash_timeout_retries + 1
        for attempt in range(attempts):
            proc = await asyncio.create_subprocess_exec(
                "bash",
                "-c",
                command,
                cwd=str(work_dir),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                stdout_b, stderr_b = await asyncio.wait_for(
                    proc.communicate(), timeout=timeout_sec
                )
                return {
                    "ok": int(proc.returncode or 0) == 0,
                    "exit_code": int(proc.returncode or 0),
                    "stdout": (stdout_b or b"").decode("utf-8", errors="replace"),
                    "stderr": (stderr_b or b"").decode("utf-8", errors="replace"),
                }
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                if attempt + 1 < attempts:
                    logger.warning(
                        f"Agent {self.id}: bash timeout; retry {attempt + 1}/{self._bash_timeout_retries}"
                    )
                    await asyncio.sleep(1.0)
                    continue
                return {"ok": False, "exit_code": -1, "stdout": "", "stderr": "timeout"}

    async def _run_codegen(
        self, instruction: str, ctx: dict[str, Any], template_mode: bool
    ) -> dict[str, Any]:
        """调用环境路由器执行 codegen 指令。

        :param instruction: 指令文本。
        :param ctx: 上下文对象（会与 agent identity overlay 合并）。
        :param template_mode: 是否启用模板模式（由 RouterBase 决定如何解释指令）。
        :returns: ``{ok, stdout, stderr, ctx?}``。
        """
        if self._env is None:
            return {"ok": False, "stdout": "", "stderr": "environment not initialized"}
        if not instruction.strip():
            return {"ok": False, "stdout": "", "stderr": "empty instruction"}
        merged_ctx = {**ctx, **self.env_codegen_ctx_overlay()}
        updated_ctx, answer = await self._env.ask(
            ctx=merged_ctx,
            instruction=instruction,
            readonly=False,
            template_mode=template_mode,
        )
        return {"ok": True, "stdout": answer, "stderr": "", "ctx": updated_ctx}

    def _glob_in_workspace(self, pattern: str, root: str) -> dict[str, Any]:
        """在 workspace 内做 glob 检索（带路径越界保护）。

        :param pattern: glob 模式。
        :param root: 相对根目录。
        :return: 包含 ok, count, matches 的字典。
        """
        work_dir = self._skill_runtime.workspace_root()
        root_path = (work_dir / (root or ".")).resolve()
        if root_path != work_dir and work_dir not in root_path.parents:
            raise ValueError("Path escapes agent workspace")
        if not root_path.exists():
            return {"ok": True, "count": 0, "matches": []}
        matches = [
            str(p.relative_to(work_dir))
            for p in root_path.glob(pattern or "**/*")
            if p.is_file()
        ]
        return {"ok": True, "count": len(matches), "matches": sorted(matches)}

    def _grep_in_workspace(
        self, pattern: str, root: str, file_glob: str
    ) -> dict[str, Any]:
        """在 workspace 内做内容检索。

        限制扫描文件数、匹配数、单文件大小。

        :param pattern: 正则匹配模式。
        :param root: 相对根目录。
        :param file_glob: 文件名 glob 模式。
        :return: 包含 ok, count, matches, truncated 的字典。
        """
        work_dir = self._skill_runtime.workspace_root()
        root_path = (work_dir / (root or ".")).resolve()
        if root_path != work_dir and work_dir not in root_path.parents:
            raise ValueError("Path escapes agent workspace")
        max_files = 2000
        max_matches = 1000
        max_file_bytes = 2 * 1024 * 1024
        try:
            rx = re.compile(pattern)
        except re.error as e:
            raise ValueError(f"Invalid regex pattern: {pattern}") from e
        walker = root_path.rglob(file_glob) if file_glob else root_path.rglob("*")
        matches: list[dict[str, Any]] = []
        scanned_files = 0
        for p in walker:
            if not p.is_file():
                continue
            scanned_files += 1
            if scanned_files > max_files:
                break
            if p.stat().st_size > max_file_bytes:
                continue
            text = p.read_text(encoding="utf-8", errors="ignore")
            for i, line in enumerate(text.splitlines(), start=1):
                if rx.search(line):
                    matches.append(
                        {"path": str(p.relative_to(work_dir)), "line": i, "text": line}
                    )
                    if len(matches) >= max_matches:
                        return {
                            "ok": True,
                            "count": len(matches),
                            "matches": matches,
                            "truncated": True,
                        }
        return {
            "ok": True,
            "count": len(matches),
            "matches": matches,
            "truncated": False,
        }

    # ── Skill Visibility ──────────────────────────────────────────────────────

    def _merged_person_step_constraints(self) -> Optional[PersonStepConstraints]:
        """合并当前路由器上各环境模块对本步的 Person 约束。"""
        if self._env is None:
            return None
        return merge_person_step_constraints(
            getattr(self._env, "env_modules", []) or []
        )

    def _refresh_selectable_skills(self) -> None:
        """根据 enabled/override 条件刷新可见技能集合。

        所有启用的 skill 默认可见，除非被 override 显式禁用。
        """
        c = self._merged_person_step_constraints()
        hidden = c.hide_skills if c else set()
        enabled = self._skill_registry.list_enabled()
        visible = []
        for s in enabled:
            override = self._skill_visibility_overrides.get(s.name)
            if override is False:
                continue
            if s.name in hidden:
                continue
            visible.append(s)
        self._selectable_skill_names = {s.name for s in visible}

    def _persist_agent_config(self) -> None:
        """持久化 agent 配置到 agent_config.json。"""
        self._skill_runtime.workspace_write(
            "agent_config.json",
            jr_dumps(
                {
                    "capabilities": self._capability_kwargs,
                    "state": self._agent_state,
                    "skill_overrides": self._skill_visibility_overrides,
                    "activated_skills": sorted(self._activated_skills),
                },
                indent=2,
            ),
        )

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def init(self, env: RouterBase):
        """初始化运行时目录，加载持久配置并扫描 custom/env skills。

        流程：
        1. 调用父类 init
        2. 确保 agent 工作目录存在
        3. 从 init_state 初始化 workspace
        4. 加载持久化的 agent_config.json
        5. 扫描环境模块提供的 skills
        6. 刷新可见技能列表
        7. 激活环境模块声明的默认技能
        8. 获取世界描述

        Args:
            env: 环境路由器实例。
        """
        await super().init(env=env)
        self._skill_runtime.ensure_agent_work_dir(self._env)
        self._skill_runtime.ensure_standard_workspace_dirs()

        # init_state 用于“出生时”的初始内在状态设定。
        # 仅在对应文件不存在时写入，避免覆盖实验过程中已经演化出的状态。
        self._seed_workspace_from_init_state()

        existing_cfg = self._skill_runtime.read_json("agent_config.json", {})
        if isinstance(existing_cfg, dict):
            raw = existing_cfg.get("skill_overrides", {})
            if isinstance(raw, dict):
                self._skill_visibility_overrides = {
                    str(k): bool(v) for k, v in raw.items()
                }
            active_raw = existing_cfg.get("activated_skills", [])
            if isinstance(active_raw, list):
                self._activated_skills = {
                    str(x).strip() for x in active_raw if str(x).strip()
                }
        self._persist_agent_config()

        # 扫描环境模块提供的 skills
        for module in env.env_modules:
            skills_dirs = module.get_agent_skills_dirs()
            for skills_dir in skills_dirs:
                added = self._skill_registry.scan_env_skills(
                    skills_dir, type(module).__name__
                )
                if added:
                    logger.info(
                        f"Agent {self.id}: loaded skills from {skills_dir}: {added}"
                    )

        self._refresh_selectable_skills()

        # 激活环境模块声明的默认技能
        for module in env.env_modules:
            skill_name = module.get_default_skill()
            if skill_name and skill_name in self._all_visible_skill_names():
                self._activated_skills.add(skill_name)
                self._invalidate_prompt_cache()
                logger.info(f"Agent {self.id}: activated default skill '{skill_name}'")
            elif skill_name:
                logger.warning(
                    f"Agent {self.id}: default skill '{skill_name}' not found in visible skills"
                )
        self._persist_agent_config()

        if self._env is not None:
            self._world_description = await self._env.get_world_description()

        # 初始化持久化记忆
        try:
            self._memory = AgentMemory(self._skill_runtime.workspace_root())
        except Exception as e:
            logger.warning(f"Agent {self.id}: failed to init AgentMemory: {e}")
        self._rolling_thread_summary = load_rolling_summary_from_workspace(
            self._skill_runtime.read_json
        )

    def _collect_thread_key_state(self) -> dict[str, Any]:
        key_state: dict[str, Any] = {}
        for p in self._thread_key_state_paths():
            cached = self._get_cached_workspace_content(p)
            if cached is None and self._skill_runtime.workspace_exists(p):
                cached = self._skill_runtime.workspace_read(p)
                self._workspace_cache[p] = cached
                self._cache_valid_paths.add(p)
            if cached:
                if p.endswith(".json"):
                    parsed = jr_parse(cached)
                    if parsed:
                        key_state[p] = parsed
                elif len(cached) > self._ctx_config.key_state_file_limit:
                    key_state[p] = trunc_str(
                        cached, self._ctx_config.key_state_file_limit
                    )
                else:
                    key_state[p] = cached
        return key_state

    def _seed_workspace_from_init_state(self) -> None:
        """从 init_state 初始化 workspace。

        写入 init_state.json 和 workspace_seed 中定义的文件。
        仅在文件不存在时写入（除非 init_state_force 为 True）。
        """
        state = self._agent_state if isinstance(self._agent_state, dict) else {}
        if not state:
            return

        force = bool(state.get("init_state_force", False))

        if force or not self._skill_runtime.workspace_exists("init_state.json"):
            self._skill_runtime.workspace_write(
                "init_state.json", jr_dumps(state, indent=2)
            )

        seed = state.get("workspace_seed", {})
        if not isinstance(seed, dict) or not seed:
            return

        for rel_path, value in seed.items():
            rel_path = str(rel_path).strip()
            if not rel_path:
                continue
            if (not force) and self._skill_runtime.workspace_exists(rel_path):
                continue
            if isinstance(value, (dict, list)):
                content = jr_dumps(value, indent=2)
            else:
                content = str(value)
            self._skill_runtime.workspace_write(rel_path, content)

    # ── Context Compaction (sliding summary) ─────────────────────────────────

    async def _compact_thread_if_needed(
        self,
        thread_messages: list[dict[str, str]],
        tick: int,
        t: datetime,
        focus_instruction: str = "",
    ) -> list[dict[str, str]]:
        """分层压缩逻辑见 :mod:`agentsociety2.agent.context` 中 ``run_thread_compaction``。"""

        async def _run_compact_llm(msgs: list[dict[str, str]]):
            if self._llm_transient_retries > 0:
                return await async_retry_on_transient(
                    lambda: self.acompletion(msgs, stream=False),
                    max_retries=self._llm_transient_retries,
                    log_prefix=f"Agent {self.id}: compact ",
                )
            return await self.acompletion(msgs, stream=False)

        tok_kw = self._capability_kwargs.get("tiktoken_encoding")
        tik_enc = (
            str(tok_kw).strip()
            if isinstance(tok_kw, str) and str(tok_kw).strip()
            else None
        )
        litellm_model = str(
            self._capability_kwargs.get("model")
            or self._capability_kwargs.get("llm_model")
            or ""
        )
        prev_cc = self._compact_count
        r = await run_thread_compaction(
            thread_messages,
            agent_id=self.id,
            cfg=self._ctx_config,
            litellm_model=litellm_model,
            tiktoken_encoding=tik_enc,
            focus_instruction=focus_instruction,
            active_skill_scope=self._active_skill_scope,
            rolling_thread_summary=self._rolling_thread_summary,
            workspace_state_version=self._workspace_state_version,
            compact_count=self._compact_count,
            run_summary_llm=_run_compact_llm,
            collect_key_state=self._collect_thread_key_state,
            memory_prompt=self._memory.to_prompt_context() if self._memory else "",
        )
        self._last_utilization = r.last_utilization
        self._rolling_thread_summary = r.rolling_thread_summary
        if r.structured_summary is not None:
            self._structured_summary = r.structured_summary
        self._compact_count = r.compact_count
        if r.compact_count > prev_cc:
            save_thread_compact_state(
                self._skill_runtime.workspace_write,
                rolling_summary=r.rolling_thread_summary,
                tier=r.tier or "unknown",
                compact_count=r.compact_count,
            )
        return r.messages

    def clear_session(self, keep_memory: bool = True) -> None:
        """重置会话，类似 Claude Code 的 /clear。

        :param keep_memory: 是否保留持久化记忆。
        """
        # 清空 thread 消息文件
        if self._skill_runtime._agent_work_dir is not None:
            thread_file = (
                self._skill_runtime._agent_work_dir / "logs" / "thread_messages.jsonl"
            )
            if thread_file.exists():
                thread_file.unlink()
            compact_state = (
                self._skill_runtime._agent_work_dir
                / "logs"
                / "thread_compact_state.json"
            )
            if compact_state.exists():
                compact_state.unlink()

        # 清空 workspace 缓存
        self._invalidate_all_workspace_cache()

        # 重置状态
        self._activated_skills.clear()
        self._active_skill_scope = ""
        self._structured_summary = None
        self._compact_count = 0
        self._rolling_thread_summary = ""

        if not keep_memory and self._memory:
            self._memory.clear()

        logger.info(f"Agent {self.id}: session cleared (keep_memory={keep_memory})")

    def handoff_to_memory(self) -> None:
        """将当前状态写入持久化记忆，类似 Claude Code 的 session handoff。"""
        if not self._memory:
            return

        # 更新当前任务
        if self._structured_summary:
            self._memory.set_current_task(self._structured_summary.primary_goal)

            # 记录已完成的动作
            for action in self._structured_summary.completed_actions:
                self._memory.complete_task(action)

            # 记录错误
            for error in self._structured_summary.errors_encountered:
                self._memory.add_error(error)

        logger.info(f"Agent {self.id}: handed off state to memory")

    # ── Batch Tool Handler ─────────────────────────────────────────────────────

    async def _handle_batch_tool(
        self,
        operations: list[dict[str, Any]],
        tick: int,
        t: datetime,
        thread_messages: list[dict[str, str]],
    ) -> dict[str, Any]:
        """批量执行多个操作，减少 LLM 调用次数。

        :param operations: 操作列表，每个操作包含 tool_name 和 arguments。
        :param tick: 当前 tick。
        :param t: 当前时间。
        :param thread_messages: thread 消息列表。
        :return: 包含所有操作结果的字典。
        """
        results: list[dict[str, Any]] = []

        for op in operations:
            tool_name = op.get("tool_name", "")
            args = op.get("arguments", {})
            blocked_obj = self._check_allowed_tools_for_action(str(tool_name).strip())
            if blocked_obj is not None:
                results.append(
                    {
                        "tool_name": tool_name,
                        "ok": False,
                        "error": blocked_obj.get("error", "blocked"),
                    }
                )
                continue

            if tool_name == "workspace_read":
                # 支持批量读取
                paths = args.get("paths", [])
                if not paths:
                    path = args.get("path", "")
                    if path:
                        paths = [path]

                cap = self._workspace_read_chunk_cap()
                off, lim = pagination_from_args(args, cap)

                read_results: dict[str, Any] = {}
                for p in paths:
                    p = str(p).strip()
                    if not p:
                        continue
                    cached = self._get_cached_workspace_content(p)
                    if cached is not None:
                        page = slice_text_page(cached, off, lim)
                        read_results[p] = {"ok": True, "cached": True, **page}
                    elif self._skill_runtime.workspace_exists(p):
                        content = self._skill_runtime.workspace_read(p)
                        self._workspace_cache[p] = content
                        self._cache_valid_paths.add(p)
                        page = slice_text_page(content, off, lim)
                        read_results[p] = {"ok": True, "cached": False, **page}
                    else:
                        read_results[p] = {"ok": False, "error": "file not found"}

                results.append(
                    {
                        "tool_name": "workspace_read",
                        "ok": all(r.get("ok", False) for r in read_results.values()),
                        "files": read_results,
                        "count": len(read_results),
                    }
                )

            elif tool_name == "workspace_write":
                # 支持批量写入
                writes = args.get("writes", {})
                if not writes:
                    path = args.get("path", "")
                    content = args.get("content", "")
                    if path:
                        writes = {path: content}

                written_paths: list[str] = []
                write_errors: list[str] = []
                for p, content in writes.items():
                    p = str(p).strip()
                    if not p:
                        continue
                    try:
                        self._skill_runtime.workspace_write(p, str(content))
                        written_paths.append(p)
                        # 失效缓存
                        self._invalidate_workspace_cache(p)
                        self._bump_workspace_state_version()
                    except Exception as e:
                        write_errors.append(f"{p}: {str(e)}")

                results.append(
                    {
                        "tool_name": "workspace_write",
                        "ok": len(write_errors) == 0,
                        "written_paths": written_paths,
                        "errors": write_errors if write_errors else None,
                        "count": len(written_paths),
                    }
                )

            elif tool_name == "workspace_list":
                paths = args.get("paths", [])
                if not paths:
                    path = args.get("path", ".")
                    paths = [path]

                list_results: dict[str, Any] = {}
                for p in paths:
                    p = str(p).strip() or "."
                    try:
                        files = self._skill_runtime.workspace_list(p)
                        list_results[p] = {
                            "ok": True,
                            "files": files[:100],
                            "count": len(files),
                        }
                    except Exception as e:
                        list_results[p] = {"ok": False, "error": str(e)}

                results.append(
                    {
                        "tool_name": "workspace_list",
                        "ok": all(r.get("ok", False) for r in list_results.values()),
                        "directories": list_results,
                    }
                )

            elif tool_name == "glob":
                patterns = args.get("patterns", [])
                if not patterns:
                    pattern = args.get("pattern", "**/*")
                    patterns = [pattern]
                root = str(args.get("path", "."))

                glob_results: dict[str, Any] = {}
                for pattern in patterns:
                    pattern = str(pattern).strip() or "**/*"
                    try:
                        parsed = self._glob_in_workspace(pattern=pattern, root=root)
                        glob_results[pattern] = {
                            "ok": True,
                            "count": parsed.get("count", 0),
                            "matches": parsed.get("matches", [])[:100],
                        }
                    except Exception as e:
                        glob_results[pattern] = {"ok": False, "error": str(e)}

                results.append(
                    {
                        "tool_name": "glob",
                        "ok": all(r.get("ok", False) for r in glob_results.values()),
                        "patterns": glob_results,
                    }
                )

            elif tool_name == "grep":
                patterns = args.get("patterns", [])
                if not patterns:
                    pattern = args.get("pattern", "")
                    if pattern:
                        patterns = [pattern]
                root = str(args.get("path", "."))
                file_glob = str(args.get("glob", ""))

                grep_results: dict[str, Any] = {}
                for pattern in patterns:
                    pattern = str(pattern).strip()
                    if not pattern:
                        continue
                    try:
                        parsed = self._grep_in_workspace(
                            pattern=pattern, root=root, file_glob=file_glob
                        )
                        grep_results[pattern] = {
                            "ok": True,
                            "count": parsed.get("count", 0),
                            "matches": parsed.get("matches", [])[:100],
                        }
                    except Exception as e:
                        grep_results[pattern] = {"ok": False, "error": str(e)}

                results.append(
                    {
                        "tool_name": "grep",
                        "ok": all(r.get("ok", False) for r in grep_results.values()),
                        "patterns": grep_results,
                    }
                )

            else:
                results.append(
                    {
                        "tool_name": tool_name,
                        "ok": False,
                        "error": f"unsupported tool in batch: {tool_name}. Supported: workspace_read, workspace_write, workspace_list, glob, grep",
                    }
                )

        return {
            "action": "batch",
            "ok": all(r.get("ok", False) for r in results),
            "results": results,
            "total_operations": len(results),
            "workspace_state_version": self._workspace_state_version,
        }

    # ── Tool Loop ─────────────────────────────────────────────────────────────

    async def _tool_loop(
        self,
        tick: int,
        t: datetime,
    ) -> tuple[list[str], list[dict[str, Any]]]:
        """执行单个 step 的工具循环。

        :param tick: 当前仿真步的时间尺度（秒）。
        :param t: 当前仿真时间。
        :return: 元组 (logs, tool_history)。
        """
        logs: list[str] = []
        history: list[dict[str, Any]] = []
        thread_messages = self._skill_runtime.read_recent_thread_messages(limit=40)

        # 每步重置循环检测器
        self._loop_detector.reset()

        for i in range(self._max_tool_rounds):
            # 滑动摘要：当 thread 过长时压缩旧消息
            thread_messages = await self._compact_thread_if_needed(
                thread_messages, tick, t
            )

            prompt = (
                "Begin your step. Review the skill catalog, activate relevant skills, "
                "and complete your objectives."
                if i == 0
                else "Continue. Call the next best tool based on the latest "
                "TOOL_RESULT_JSON, or set done=true if finished."
            )
            try:
                messages = list(thread_messages)
                messages.append({"role": "user", "content": prompt})
                decision = await self.acompletion_with_pydantic_validation(
                    model_type=ToolDecision,
                    messages=messages,
                    tick=tick,
                    t=t,
                    max_retries=self._tool_decision_max_retries,
                )
                decision_json = jr_dumps(decision.model_dump())
                self._skill_runtime.append_thread_message(
                    "user", prompt, tick=tick, t=t
                )
                self._skill_runtime.append_thread_message(
                    "assistant", decision_json, tick=tick, t=t
                )
                thread_messages.append({"role": "user", "content": prompt})
                thread_messages.append({"role": "assistant", "content": decision_json})
                if len(thread_messages) > self._ctx_config.thread_max_messages:
                    thread_messages = thread_messages[
                        -self._ctx_config.thread_max_messages :
                    ]
            except Exception as e:
                logs.append(f"tool_loop_error:{e}")
                break

            action = decision.tool_name.strip()
            args = self._coerce_llm_dict(decision.arguments)
            skill_name = str(args.get("skill_name", "")).strip()

            # ── 循环检测 ──
            loop_result = self._loop_detector.check_tool_loop(action, args)
            if loop_result.is_loop:
                logger.warning(
                    f"Agent {self.id}: loop detected - {loop_result.details}"
                )
                logs.append(f"loop_detected:{loop_result.loop_type}")
                result_obj = {
                    "action": action,
                    "ok": False,
                    "error": f"Loop detected: {loop_result.details}. Call 'done' or try a different approach.",
                }
                history.append(result_obj)
                self._append_tool_result_to_thread(thread_messages, tick, t, result_obj)
                break

            # 仅当显式选择 done 工具时立即结束。done=true 与具体工具并列时表示
            # 「执行本工具后本仿真步结束」，不得在派发工具之前 break（否则工具不会执行）。
            if action == "done":
                logs.append(f"done:{decision.summary or 'step_complete'}")
                break

            # ── disable_skill ──
            if action == "disable_skill":
                if not skill_name:
                    result_obj = {
                        "action": action,
                        "ok": False,
                        "error": "empty skill_name",
                    }
                    history.append(result_obj)
                    self._append_tool_result_to_thread(
                        thread_messages, tick, t, result_obj
                    )
                    logs.append("disable_skill:empty")
                    continue
                c = self._merged_person_step_constraints()
                if c and skill_name in c.forbid_disabling_skills:
                    result_obj = {
                        "action": action,
                        "skill_name": skill_name,
                        "ok": False,
                        "error": "cannot disable skill: blocked by environment step constraints",
                    }
                    history.append(result_obj)
                    self._append_tool_result_to_thread(
                        thread_messages, tick, t, result_obj
                    )
                    logs.append(
                        f"disable_skill:{skill_name}:blocked_by_env_constraints"
                    )
                    continue
                self._skill_visibility_overrides[skill_name] = False
                self._activated_skills.discard(skill_name)
                if self._active_skill_scope == skill_name:
                    self._active_skill_scope = ""
                self._persist_agent_config()
                self._refresh_selectable_skills()
                result_obj = {"action": action, "skill_name": skill_name, "ok": True}
                history.append(result_obj)
                self._skill_runtime.append_tool_log(
                    {"tick": tick, "time": t.isoformat(), **result_obj}
                )
                self._append_tool_result_to_thread(thread_messages, tick, t, result_obj)
                logs.append(f"disable_skill:{skill_name}:ok")
                continue

            # ── enable_skill ──
            if action == "enable_skill":
                if not skill_name:
                    result_obj = {
                        "action": action,
                        "ok": False,
                        "error": "empty skill_name",
                    }
                    history.append(result_obj)
                    self._append_tool_result_to_thread(
                        thread_messages, tick, t, result_obj
                    )
                    logs.append("enable_skill:empty")
                    continue
                if self._skill_visibility_overrides.get(skill_name) is False:
                    del self._skill_visibility_overrides[skill_name]
                self._persist_agent_config()
                self._refresh_selectable_skills()
                if skill_name in self._all_visible_skill_names():
                    result_obj = {
                        "action": action,
                        "skill_name": skill_name,
                        "ok": True,
                        "note": "enabled (override cleared)",
                    }
                    history.append(result_obj)
                    self._skill_runtime.append_tool_log(
                        {"tick": tick, "time": t.isoformat(), **result_obj}
                    )
                    self._append_tool_result_to_thread(
                        thread_messages, tick, t, result_obj
                    )
                    logs.append(f"enable_skill:{skill_name}:ok")
                else:
                    result_obj = {
                        "action": action,
                        "skill_name": skill_name,
                        "ok": False,
                        "error": "skill not found in registry",
                    }
                    history.append(result_obj)
                    self._skill_runtime.append_tool_log(
                        {"tick": tick, "time": t.isoformat(), **result_obj}
                    )
                    self._append_tool_result_to_thread(
                        thread_messages, tick, t, result_obj
                    )
                    logs.append(f"enable_skill:{skill_name}:miss")
                continue

            # ── skill visibility gate ──
            if action in {"activate_skill", "read_skill", "execute_skill"} and (
                not skill_name or skill_name not in self._all_visible_skill_names()
            ):
                result_obj = {
                    "action": action,
                    "skill_name": skill_name,
                    "ok": False,
                    "error": "skill not visible for this agent",
                }
                history.append(result_obj)
                self._append_tool_result_to_thread(thread_messages, tick, t, result_obj)
                logs.append(f"{action}:{skill_name}:rejected")
                continue

            # ── allowed-tools gate ──
            blocked_obj = self._check_allowed_tools_for_action(action)
            if blocked_obj is not None:
                history.append(blocked_obj)
                self._append_tool_result_to_thread(
                    thread_messages, tick, t, blocked_obj
                )
                logs.append(f"{action}:blocked_allowed_tools")
                continue

            # ── activate_skill ──
            if action == "activate_skill":
                dep_status = self._ensure_requires_activated(
                    tick=tick,
                    t=t,
                    thread_messages=thread_messages,
                    skill_name=skill_name,
                )
                if not dep_status.get("ok"):
                    result_obj = {
                        "action": action,
                        "skill_name": skill_name,
                        "ok": False,
                        "error": "missing required skills",
                        "missing": dep_status.get("missing", []),
                    }
                    history.append(result_obj)
                    self._append_tool_result_to_thread(
                        thread_messages, tick, t, result_obj
                    )
                    logs.append(f"activate:{skill_name}:blocked_requires")
                    continue

                activation_raw, activation_parts = self._split_skill_arguments(
                    args.get("arguments", "")
                )
                base_content = self._skill_runtime.skill_activate(skill_name)
                ok = bool(base_content)
                content = ""
                if ok:
                    try:
                        content = self._inject_skill_arguments(
                            base_content, activation_raw, activation_parts
                        )
                        content = await self._inject_skill_command_outputs(content)
                    except Exception as e:
                        result_obj = {
                            "action": action,
                            "skill_name": skill_name,
                            "ok": False,
                            "error": f"skill_render_failed: {e}",
                        }
                        history.append(result_obj)
                        self._append_tool_result_to_thread(
                            thread_messages, tick, t, result_obj
                        )
                        logs.append(f"activate:{skill_name}:render_failed")
                        continue
                    self._activated_skills.add(skill_name)
                    self._active_skill_scope = skill_name
                    self._invalidate_prompt_cache()
                    self._persist_agent_config()
                result_obj = {
                    "action": action,
                    "skill_name": skill_name,
                    "ok": ok,
                    "content": content,
                }
                history.append(result_obj)
                self._skill_runtime.append_tool_log(
                    {
                        "tick": tick,
                        "time": t.isoformat(),
                        "action": action,
                        "skill_name": skill_name,
                        "ok": ok,
                        "size": len(content),
                    }
                )
                self._append_tool_result_to_thread(thread_messages, tick, t, result_obj)
                logs.append(f"activate:{skill_name}:{'ok' if ok else 'miss'}")
                if decision.done:
                    logs.append(f"done:{decision.summary or 'step_complete'}")
                    break
                continue

            # ── read_skill ──
            if action == "read_skill":
                read_path = str(args.get("path", ""))
                content = self._skill_runtime.skill_read(skill_name, read_path)
                ok = bool(content)
                if ok:
                    self._active_skill_scope = skill_name
                cap = self._workspace_read_chunk_cap()
                off, lim = pagination_from_args(args, cap)
                page = (
                    slice_text_page(content, off, lim)
                    if ok
                    else {
                        "content": "",
                        "total_chars": 0,
                        "offset": 0,
                        "limit_applied": lim,
                        "returned_chars": 0,
                        "next_offset": None,
                        "has_more": False,
                    }
                )
                result_obj = {
                    "action": action,
                    "skill_name": skill_name,
                    "path": read_path,
                    "ok": ok,
                    **page,
                }
                history.append(result_obj)
                self._skill_runtime.append_tool_log(
                    {
                        "tick": tick,
                        "time": t.isoformat(),
                        "action": action,
                        "skill_name": skill_name,
                        "path": read_path,
                        "ok": ok,
                        "size": len(content),
                    }
                )
                self._append_tool_result_to_thread(thread_messages, tick, t, result_obj)
                logs.append(f"read:{skill_name}:{read_path}:{'ok' if ok else 'miss'}")
                continue

            # ── execute_skill ──
            if action == "execute_skill":
                dep_status = self._ensure_requires_activated(
                    tick=tick,
                    t=t,
                    thread_messages=thread_messages,
                    skill_name=skill_name,
                )
                if not dep_status.get("ok"):
                    result_obj = {
                        "action": action,
                        "skill_name": skill_name,
                        "ok": False,
                        "error": "missing required skills",
                        "missing": dep_status.get("missing", []),
                    }
                    history.append(result_obj)
                    self._append_tool_result_to_thread(
                        thread_messages, tick, t, result_obj
                    )
                    logs.append(f"execute:{skill_name}:blocked_requires")
                    continue

                payload = self._coerce_llm_dict(args.get("args", {}))
                payload.setdefault("tick", tick)
                payload.setdefault("time", t.isoformat())
                out = await self.execute(skill_name, payload)
                ok = bool(out.get("ok"))
                # skill 执行可能修改多个文件：统一失效缓存并更新版本
                self._invalidate_all_workspace_cache()
                self._bump_workspace_state_version()
                if ok:
                    self._active_skill_scope = skill_name
                stdout_s = str(out.get("stdout", ""))
                stderr_s = str(out.get("stderr", ""))
                result_obj = {
                    "action": action,
                    "skill_name": skill_name,
                    "ok": ok,
                    "exit_code": out.get("exit_code"),
                    "error_type": out.get("error_type"),
                    "artifacts": out.get("artifacts", []),
                    "stdout": trunc_str(stdout_s, self._ctx_config.stdout_max_chars),
                    "stderr": trunc_str(stderr_s, self._ctx_config.stderr_max_chars),
                    "workspace_state_version": self._workspace_state_version,
                }
                history.append(result_obj)
                self._skill_runtime.append_tool_log(
                    {
                        "tick": tick,
                        "time": t.isoformat(),
                        "action": action,
                        "skill_name": skill_name,
                        "ok": ok,
                        "exit_code": out.get("exit_code"),
                        "error_type": out.get("error_type"),
                        "artifacts": out.get("artifacts", []),
                    }
                )
                self._append_tool_result_to_thread(thread_messages, tick, t, result_obj)
                logs.append(f"execute:{skill_name}:{'ok' if ok else 'fail'}")
                if decision.done:
                    logs.append(f"done:{decision.summary or 'step_complete'}")
                    break
                continue

            # ── workspace_read ──
            if action == "workspace_read":
                ws_read_path = str(args.get("path", ""))
                cap = self._workspace_read_chunk_cap()
                off, lim = pagination_from_args(args, cap)
                try:
                    if not self._skill_runtime.workspace_exists(ws_read_path):
                        result_obj = {
                            "action": action,
                            "path": ws_read_path,
                            "ok": False,
                            "error": "file not found",
                        }
                    else:
                        cached = self._get_cached_workspace_content(ws_read_path)
                        if cached is not None:
                            content = cached
                            cached_hit = True
                        else:
                            content = self._skill_runtime.workspace_read(ws_read_path)
                            self._workspace_cache[ws_read_path] = content
                            self._cache_valid_paths.add(ws_read_path)
                            cached_hit = False
                        page = slice_text_page(content, off, lim)
                        result_obj = {
                            "action": action,
                            "path": ws_read_path,
                            "ok": True,
                            "cached": cached_hit,
                            **page,
                        }
                except Exception as e:
                    result_obj = {
                        "action": action,
                        "path": ws_read_path,
                        "ok": False,
                        "error": str(e),
                    }
                history.append(result_obj)
                self._skill_runtime.append_tool_log(
                    {"tick": tick, "time": t.isoformat(), **result_obj}
                )
                self._append_tool_result_to_thread(thread_messages, tick, t, result_obj)
                logs.append(
                    f"workspace_read:{ws_read_path}:{'ok' if result_obj.get('ok') else 'fail'}"
                )
                continue

            # ── workspace_write ──
            if action == "workspace_write":
                path = str(args.get("path", ""))
                content = str(args.get("content", ""))
                try:
                    self._skill_runtime.workspace_write(path, content)
                    # 失效缓存，确保下次读取时获取最新内容
                    self._invalidate_workspace_cache(path)
                    self._bump_workspace_state_version()
                    result_obj = {
                        "action": action,
                        "path": path,
                        "ok": True,
                        "size": len(content),
                    }
                except Exception as e:
                    result_obj = {
                        "action": action,
                        "path": path,
                        "ok": False,
                        "error": str(e),
                    }
                history.append(result_obj)
                self._skill_runtime.append_tool_log(
                    {"tick": tick, "time": t.isoformat(), **result_obj}
                )
                self._append_tool_result_to_thread(thread_messages, tick, t, result_obj)
                logs.append(
                    f"workspace_write:{path}:{'ok' if result_obj.get('ok') else 'fail'}"
                )
                continue

            # ── workspace_list ──
            if action == "workspace_list":
                path = str(args.get("path", ".") or ".")
                try:
                    files = self._skill_runtime.workspace_list(path)
                    result_obj = {
                        "action": action,
                        "path": path,
                        "ok": True,
                        "count": len(files),
                        "files": files[:200],
                    }
                except Exception as e:
                    result_obj = {
                        "action": action,
                        "path": path,
                        "ok": False,
                        "error": str(e),
                    }
                history.append(result_obj)
                self._skill_runtime.append_tool_log(
                    {"tick": tick, "time": t.isoformat(), **result_obj}
                )
                self._append_tool_result_to_thread(thread_messages, tick, t, result_obj)
                if result_obj.get("ok"):
                    logs.append(f"workspace_list:{path}:{result_obj.get('count', 0)}")
                else:
                    logs.append(f"workspace_list:{path}:fail")
                continue

            # ── batch ──
            if action == "batch":
                operations = args.get("operations", [])
                if not isinstance(operations, list) or not operations:
                    result_obj = {
                        "action": action,
                        "ok": False,
                        "error": "empty or invalid operations list",
                    }
                    history.append(result_obj)
                    self._append_tool_result_to_thread(
                        thread_messages, tick, t, result_obj
                    )
                    logs.append("batch:empty")
                    continue

                result_obj = await self._handle_batch_tool(
                    operations=operations,
                    tick=tick,
                    t=t,
                    thread_messages=thread_messages,
                )
                history.append(result_obj)
                self._skill_runtime.append_tool_log(
                    {"tick": tick, "time": t.isoformat(), **result_obj}
                )
                self._append_tool_result_to_thread(thread_messages, tick, t, result_obj)
                logs.append(
                    f"batch:{result_obj.get('total_operations', 0)}:{'ok' if result_obj.get('ok') else 'partial'}"
                )
                continue

            # ── bash ──
            if action == "bash":
                command = str(args.get("command", "")).strip()
                timeout_sec = int(args.get("timeout_sec", 20))
                timeout_sec = max(1, min(120, timeout_sec))
                out = await self._run_bash_in_workspace(
                    command=command, timeout_sec=timeout_sec
                )
                ok = bool(out.get("ok"))
                bo = str(out.get("stdout", ""))
                be = str(out.get("stderr", ""))
                result_obj = {
                    "action": action,
                    "ok": ok,
                    "exit_code": out.get("exit_code"),
                    "stdout": trunc_str(bo, self._ctx_config.stdout_max_chars),
                    "stderr": trunc_str(be, self._ctx_config.stderr_max_chars),
                }
                history.append(result_obj)
                self._skill_runtime.append_tool_log(
                    {"tick": tick, "time": t.isoformat(), **result_obj}
                )
                self._append_tool_result_to_thread(thread_messages, tick, t, result_obj)
                logs.append(f"bash:{'ok' if ok else 'fail'}")
                continue

            # ── glob ──
            if action == "glob":
                try:
                    parsed = self._glob_in_workspace(
                        pattern=str(args.get("glob", "**/*")),
                        root=str(args.get("path", ".")),
                    )
                    result_obj = {
                        "action": action,
                        "ok": True,
                        "count": parsed.get("count", 0),
                        "matches": parsed.get("matches", [])[:100],
                    }
                except Exception as e:
                    result_obj = {"action": action, "ok": False, "error": str(e)}
                history.append(result_obj)
                self._skill_runtime.append_tool_log(
                    {"tick": tick, "time": t.isoformat(), **result_obj}
                )
                self._append_tool_result_to_thread(thread_messages, tick, t, result_obj)
                logs.append(f"glob:{'ok' if result_obj.get('ok') else 'fail'}")
                continue

            # ── grep ──
            if action == "grep":
                try:
                    parsed = self._grep_in_workspace(
                        pattern=str(args.get("pattern", "")),
                        root=str(args.get("path", ".")),
                        file_glob=str(args.get("glob", "")),
                    )
                    result_obj = {
                        "action": action,
                        "ok": True,
                        "count": parsed.get("count", 0),
                        "matches": parsed.get("matches", [])[:100],
                    }
                except Exception as e:
                    result_obj = {"action": action, "ok": False, "error": str(e)}
                history.append(result_obj)
                self._skill_runtime.append_tool_log(
                    {"tick": tick, "time": t.isoformat(), **result_obj}
                )
                self._append_tool_result_to_thread(thread_messages, tick, t, result_obj)
                logs.append(f"grep:{'ok' if result_obj.get('ok') else 'fail'}")
                continue

            # ── codegen ──
            if action == "codegen":
                instruction = str(args.get("instruction", ""))
                ctx = self._coerce_llm_dict(args.get("ctx", {}))
                template_mode = bool(args.get("template_mode", False))
                out = await self._run_codegen(
                    instruction=instruction,
                    ctx=ctx,
                    template_mode=template_mode,
                )
                ok = bool(out.get("ok"))
                self._invalidate_all_workspace_cache()
                self._bump_workspace_state_version()
                co = str(out.get("stdout", ""))
                ce = str(out.get("stderr", ""))
                result_obj = {
                    "action": action,
                    "ok": ok,
                    "stdout": trunc_str(co, self._ctx_config.stdout_max_chars),
                    "stderr": trunc_str(ce, self._ctx_config.stderr_max_chars),
                    "workspace_state_version": self._workspace_state_version,
                }
                if out.get("ctx") is not None:
                    result_obj["ctx"] = out["ctx"]
                history.append(result_obj)
                self._skill_runtime.append_tool_log(
                    {"tick": tick, "time": t.isoformat(), **result_obj}
                )
                self._append_tool_result_to_thread(thread_messages, tick, t, result_obj)
                logs.append(f"codegen:{'ok' if ok else 'fail'}")
                if decision.done:
                    logs.append(f"done:{decision.summary or 'step_complete'}")
                    break
                continue

            # ── unsupported action：通知 LLM ──
            valid_tools = (
                "activate_skill, read_skill, execute_skill, bash, codegen, batch, "
                "workspace_read, workspace_write, workspace_list, glob, grep, "
                "enable_skill, disable_skill, done"
            )
            hint = ""
            sk = action.strip()
            if sk and self._skill_registry.get_skill_info(sk, load_content=False):
                hint = (
                    f' Use activate_skill with arguments containing skill_name="{sk}" '
                    f'(not tool_name="{sk}").'
                )
            result_obj = {
                "action": action,
                "ok": False,
                "error": f"unsupported tool: '{action}'. Valid tools: {valid_tools}.{hint}",
            }
            history.append(result_obj)
            self._skill_runtime.append_tool_log(
                {"tick": tick, "time": t.isoformat(), **result_obj}
            )
            self._append_tool_result_to_thread(thread_messages, tick, t, result_obj)
            logs.append(f"unsupported:{action}")
            if decision.done:
                logs.append(f"done:{decision.summary or 'step_complete'}")
                break

        return logs, history

    # ── Public API ────────────────────────────────────────────────────────────

    async def execute(self, skill_name: str, args: dict[str, Any]) -> dict[str, Any]:
        """执行技能（转发到 runtime/registry）。

        :param skill_name: 技能名称。
        :param args: 技能参数。
        :returns: 执行结果字典。
        """
        return await self._skill_runtime.execute(skill_name=skill_name, args=args)

    async def step(self, tick: int, t: datetime) -> str:
        """执行一个仿真步并持久化会话状态与回放记录。

        流程：
        1. 步数递增，重置技能作用域
        2. 刷新可见技能列表
        3. 构建上下文快照（预读取文件）
        4. 执行工具循环
        5. 持久化会话状态和回放记录

        :param tick: 当前仿真步时间跨度（秒）。
        :param t: 当前仿真时间。
        :returns: 工具执行日志拼接字符串；如无操作返回 ``"no-action"``。
        """
        self._step_count += 1
        # 每步重新进入自由工具选择，避免上一步 skill 的 allowed-tools 作用域跨步泄漏。
        self._active_skill_scope = ""
        self._refresh_selectable_skills()
        pc = self._merged_person_step_constraints()
        if pc and pc.pin_allowed_tools_to_skill:
            pin = pc.pin_allowed_tools_to_skill.strip()
            if pin and pin in self._all_visible_skill_names():
                self._active_skill_scope = pin
        self._last_selected_skills = set(self._selectable_skill_names)

        # 构建上下文快照：预读取常用文件，注入到 system prompt
        self._build_step_context()
        self._prepare_prompt_sidecars()

        logs, tool_history = await self._tool_loop(tick=tick, t=t)

        # 使用 tool loop 结束后的最终技能状态
        self._skill_runtime.persist_session_state(
            tick=tick,
            t=t,
            selected_skills=self._selectable_skill_names,
            activated_skills=self._activated_skills,
        )
        self._skill_runtime.append_step_replay(
            tick=tick,
            t=t,
            selected_skills=self._selectable_skill_names,
            tool_history=tool_history,
        )

        # 将当前状态写入持久化记忆
        self.handoff_to_memory()

        if not logs:
            return "no-action"
        return " | ".join(logs)

    async def ask(self, message: str, readonly: bool = True) -> str:
        """通过环境路由器问答（须已 :meth:`init`）。

        :param message: 问题文本。
        :param readonly: 是否只读（只读时应避免改变环境状态）。
        :returns: 环境/系统返回的答案文本。
        :raises RuntimeError: 未初始化环境时抛出。
        """
        if self._env is None:
            raise RuntimeError("PersonAgent.ask requires an initialized environment")
        _, answer = await self.ask_env({"id": self.id}, message, readonly=readonly)
        return answer

    async def dump(self) -> dict:
        """导出最小运行状态快照（用于外部持久化/调试）。

        :returns: 可序列化字典。
        """
        return {
            "id": self.id,
            "name": self._name,
            "profile": self.get_profile(),
            "step_count": self._step_count,
            "last_selected_skills": sorted(self._last_selected_skills),
        }

    async def load(self, dump_data: dict):
        """从 :meth:`dump` 结果恢复轻量运行状态。

        :param dump_data: dump 数据。
        """
        self._step_count = int(dump_data.get("step_count", 0))
        self._last_selected_skills = set(dump_data.get("last_selected_skills", []))
