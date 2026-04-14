from __future__ import annotations

"""Agent 技能运行时（workspace + skill 执行）。

该模块提供 :class:`~agentsociety2.agent.skills.runtime.AgentSkillRuntime`，用于把 PersonAgent 的
“工作目录隔离、文件读写、thread/tool 日志、skill 激活与执行”等细节集中在一个组件内，
避免 agent 主体过度膨胀。
"""

import logging
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Any, Awaitable, Callable, Optional

import json_repair

from agentsociety2.agent.skills import SkillRegistry
from agentsociety2.agent.tool import jr_dumps

logger = logging.getLogger(__name__)


class AgentSkillRuntime:
    """独立的 Skill 运行时组件。

    PersonAgent 仅通过组合使用该组件，避免把 skill/workspace 执行细节堆在 agent 主体里。

    Attributes:
        _agent_id: Agent ID。
        _registry: Skill 注册表。
        _agent_work_dir: Agent 工作目录。
        _state_config: 状态文件配置（可选）。
    """

    def __init__(
        self,
        agent_id: int,
        registry: SkillRegistry,
        state_config: Any = None,
    ) -> None:
        """初始化运行时。

        :param agent_id: Agent ID。
        :param registry: Skill 注册表。
        :param state_config: 状态文件配置（StateConfig 实例）。
        """
        self._agent_id = agent_id
        self._registry = registry
        self._agent_work_dir: Path | None = None
        self._state_config = state_config

    def ensure_agent_work_dir(self, env_obj: Any) -> Path:
        """确保 agent 工作目录已初始化并返回其路径。

        :param env_obj: 通常为 env_router；若其包含 ``run_dir`` 属性则以其为基准目录，
            否则退化为当前工作目录。
        :returns: agent 工作目录路径（形如 ``<run_dir>/agents/agent_0001``）。
        """
        if self._agent_work_dir is not None:
            return self._agent_work_dir

        # 优先从 env_router 获取 run_dir
        run_dir = getattr(env_obj, "run_dir", None)
        if run_dir is not None:
            base_path = Path(run_dir)
        else:
            base_path = Path.cwd()

        self._agent_work_dir = (
            base_path / "agents" / f"agent_{self._agent_id:04d}"
        ).resolve()
        self._agent_work_dir.mkdir(parents=True, exist_ok=True)
        return self._agent_work_dir

    def ensure_standard_workspace_dirs(self) -> None:
        """确保 workspace 标准目录结构存在。

        创建以下目录：
        - ``state/`` - Skills 状态文件
        - ``memory/`` - 长期记忆
        - ``input/`` - 外部输入
        - ``logs/`` - 日志
        """
        if self._agent_work_dir is None:
            raise RuntimeError("Agent workspace is not initialized")

        standard_dirs = ["state", "memory", "input", "logs"]
        for dir_name in standard_dirs:
            dir_path = self._agent_work_dir / dir_name
            try:
                dir_path.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                logger.warning(
                    f"Agent {self._agent_id}: failed to create workspace dir '{dir_name}': {e}"
                )

    def _resolve_workspace_path(self, relative_path: str) -> Path:
        """将相对路径解析到 workspace 内并做越界保护。"""
        if self._agent_work_dir is None:
            raise RuntimeError("Agent workspace is not initialized")
        work_dir = self._agent_work_dir
        target = (work_dir / relative_path).resolve()
        if target != work_dir and work_dir not in target.parents:
            raise ValueError(f"Path escapes agent workspace: {relative_path}")
        return target

    def workspace_root(self) -> Path:
        """:returns: workspace 根目录路径。"""
        if self._agent_work_dir is None:
            raise RuntimeError("Agent workspace is not initialized")
        return self._agent_work_dir

    def workspace_read(self, relative_path: str) -> str:
        """读取 workspace 内文件内容。

        :param relative_path: 相对 workspace 的路径。
        :returns: 文件文本内容；若文件不存在则返回空字符串。
        """
        target = self._resolve_workspace_path(relative_path)
        if not target.exists() or not target.is_file():
            return ""
        return target.read_text(encoding="utf-8")

    def workspace_write(self, relative_path: str, content: str) -> str:
        """写入 workspace 内文件（UTF-8）。

        :param relative_path: 相对 workspace 的路径。
        :param content: 写入内容。
        :returns: 实际写入的绝对路径字符串。
        """
        target = self._resolve_workspace_path(relative_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return str(target)

    def workspace_exists(self, relative_path: str) -> bool:
        """:returns: workspace 内路径是否存在。"""
        target = self._resolve_workspace_path(relative_path)
        return target.exists()

    def workspace_delete(self, relative_path: str) -> bool:
        """删除 workspace 内文件（仅文件，目录不删除）。"""
        target = self._resolve_workspace_path(relative_path)
        if not target.exists() or target.is_dir():
            return False
        target.unlink()
        return True

    def workspace_list(self, relative_path: str = ".") -> list[str]:
        """列出 workspace 内文件（递归）。

        :param relative_path: 相对 workspace 的根路径。
        :returns: 文件相对路径列表（相对 workspace 根）。
        """
        work_dir = self.workspace_root()  # raises RuntimeError if not initialized
        root = self._resolve_workspace_path(relative_path)
        if not root.exists():
            return []
        if root.is_file():
            return [str(root.relative_to(work_dir))]
        return sorted(
            str(p.relative_to(work_dir)) for p in root.rglob("*") if p.is_file()
        )

    def skill_list(self, names: list[str]) -> list[dict[str, Any]]:
        return self._registry.list_selection_metadata(names=names, only_enabled=True)

    def skill_activate(self, name: str) -> str:
        return self._registry.activate(name)

    def skill_read(self, name: str, relative_path: str) -> str:
        return self._registry.read(name, relative_path)

    async def execute(
        self,
        skill_name: str,
        args: dict[str, Any],
        codegen_executor: (
            Callable[[dict[str, Any]], Awaitable[dict[str, Any]]] | None
        ) = None,
    ) -> dict[str, Any]:
        """执行某个 skill（转发到 registry）。

        :param skill_name: skill 名称。
        :param args: 执行参数（由 skill 脚本/协议自行定义）。
        :param codegen_executor: 可选。用于把 skill 内部的 codegen 调度回 env 的执行器。
        :returns: 执行结果字典（由 :class:`~agentsociety2.agent.skills.SkillRegistry` 约定）。
        :raises RuntimeError: workspace 未初始化时抛出。
        """
        if self._agent_work_dir is None:
            raise RuntimeError("Agent workspace is not initialized")
        work_dir = self._agent_work_dir
        return await self._registry.execute(
            skill_name=skill_name,
            args=args,
            agent_work_dir=work_dir,
            codegen_executor=codegen_executor,
        )

    def persist_session_state(
        self,
        tick: int,
        t: datetime,
        selected_skills: set[str],
        activated_skills: set[str] | None = None,
    ) -> None:
        """落地当前会话状态到 workspace，并追加到历史记录。

        :param tick: 当前 tick。
        :param t: 当前仿真时间。
        :param selected_skills: 本步可见/可选技能集合。
        :param activated_skills: 可选。已激活技能集合。
        """
        state = {
            "agent_id": self._agent_id,
            "tick": tick,
            "time": t.isoformat(),
            "selected_skills": sorted(selected_skills),
            "activated_skills": sorted(activated_skills or set()),
        }
        self.workspace_write(
            "logs/session_state.json",
            jr_dumps(state),
        )
        self.append_session_state_event(state)

    def append_session_state_event(self, state: dict[str, Any]) -> None:
        """追加 session_state 事件到 ``logs/session_state_history.jsonl``。"""
        if self._agent_work_dir is None:
            raise RuntimeError("Agent workspace is not initialized")
        path = self._agent_work_dir / "logs" / "session_state_history.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(jr_dumps(state, indent=None) + "\n")

    def append_tool_log(self, entry: dict[str, Any]) -> None:
        """追加单条工具调用日志（jsonl）。"""
        if self._agent_work_dir is None:
            raise RuntimeError("Agent workspace is not initialized")
        log_path = self._agent_work_dir / "logs" / "tool_calls.jsonl"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as f:
            f.write(jr_dumps(entry, indent=None) + "\n")

    def append_step_replay(
        self,
        tick: int,
        t: datetime,
        selected_skills: set[str],
        tool_history: list[dict[str, Any]],
    ) -> None:
        """追加 step 回放记录（jsonl）。"""
        if self._agent_work_dir is None:
            raise RuntimeError("Agent workspace is not initialized")
        replay_path = self._agent_work_dir / "logs" / "step_replay.jsonl"
        replay_path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "tick": tick,
            "time": t.isoformat(),
            "selected_skills": sorted(selected_skills),
            "tool_history": tool_history,
        }
        with replay_path.open("a", encoding="utf-8") as f:
            f.write(jr_dumps(record, indent=None) + "\n")

    def read_json(self, relative_path: str, default: Any) -> Any:
        """读取工作目录中的 JSON 文件；空内容返回 default。"""
        raw = self.workspace_read(relative_path)
        if not raw:
            return default
        return json_repair.loads(raw)

    def read_recent_tool_logs(self, limit: int = 20) -> list[dict[str, Any]]:
        """读取最近 N 条工具调用日志。"""
        if self._agent_work_dir is None:
            raise RuntimeError("Agent workspace is not initialized")
        path = self._agent_work_dir / "logs" / "tool_calls.jsonl"
        if not path.exists():
            return []
        if limit > 0:
            recent_lines: deque[str] = deque(maxlen=limit)
            with path.open("r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        recent_lines.append(line)
            source = list(recent_lines)
        else:
            with path.open("r", encoding="utf-8") as f:
                source = [line for line in f if line.strip()]
        return [json_repair.loads(line) for line in source]

    def append_thread_message(
        self,
        role: str,
        content: str,
        tick: int,
        t: datetime,
        *,
        tool_result_full: Optional[dict[str, Any]] = None,
    ) -> None:
        """追加 thread 消息到 ``logs/thread_messages.jsonl``。

        ``content`` 为喂给 LLM 的文本；若提供 ``tool_result_full``，则同条记录落盘完整工具结果
        （读取 thread 时仍只用 ``content`` 构造 messages）。
        """
        if self._agent_work_dir is None:
            raise RuntimeError("Agent workspace is not initialized")
        path = self._agent_work_dir / "logs" / "thread_messages.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        entry: dict[str, Any] = {
            "tick": tick,
            "time": t.isoformat(),
            "role": role,
            "content": content,
        }
        if tool_result_full is not None:
            entry["tool_result_full"] = tool_result_full
        with path.open("a", encoding="utf-8") as f:
            f.write(jr_dumps(entry, indent=None) + "\n")

    def read_recent_thread_messages(self, limit: int = 40) -> list[dict[str, str]]:
        """读取最近 N 条 thread 消息并转换为 LLM messages 结构。"""
        if self._agent_work_dir is None:
            raise RuntimeError("Agent workspace is not initialized")
        path = self._agent_work_dir / "logs" / "thread_messages.jsonl"
        if not path.exists():
            return []
        if limit > 0:
            recent_lines: deque[str] = deque(maxlen=limit)
            with path.open("r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        recent_lines.append(line)
            recent = list(recent_lines)
        else:
            with path.open("r", encoding="utf-8") as f:
                recent = [line.rstrip("\n") for line in f if line.strip()]
        messages: list[dict[str, str]] = []
        for line in recent:
            if not line.strip():
                continue
            obj = json_repair.loads(line)
            role = str(obj.get("role", "")).strip()
            content = str(obj.get("content", ""))
            if role in {"user", "assistant"} and content:
                messages.append({"role": role, "content": content})
        return messages

    def build_workspace_structure_prompt(self) -> str:
        """构建 workspace 结构说明（Cursor风格：极简 + 动态发现）。

        不维护复杂的 manifest/registry，只提供目录约定，让 Agent 自己探索。
        状态文件示例从配置或实际文件动态生成。

        :returns: workspace 结构说明文本。
        """
        lines = [
            "## Workspace Structure",
            "",
            'All files are in the workspace root. Use `workspace_list(".")` to see what exists.',
            "",
            "### Directory Convention",
            "- `state/` - Skill state files (dynamically discovered)",
            "- `memory/` - Long-term memory (memory.jsonl)",
            "- `input/` - External input from environment",
            "- `logs/` - Execution logs (thread_messages.jsonl, tool_calls.jsonl, etc.)",
            "",
            "### Quick Discovery",
            '- `workspace_list("state/")` - See all skill state files',
            '- `workspace_read("memory/memory.jsonl")` - Read last N memories',
            "",
            "Let the agent discover what it needs dynamically.",
        ]

        # 动态添加当前存在的 state 文件
        if self._agent_work_dir is not None:
            state_dir = self._agent_work_dir / "state"
            if state_dir.exists() and state_dir.is_dir():
                state_files = sorted(
                    f.name
                    for f in state_dir.iterdir()
                    if f.is_file() and (f.suffix == ".json" or f.suffix == ".txt")
                )
                if state_files:
                    lines.append("")
                    lines.append("### Current State Files")
                    for filename in state_files:
                        lines.append(f"- `state/{filename}`")
                        lines.append(f"- `state/{filename}`")

        return "\n".join(lines)

    # ==================== AGENT_CONTEXT.md Support ====================

    def read_agent_context(self) -> dict[str, Any]:
        """读取 AGENT_CONTEXT.md 文件内容。

        该文件是agent的自我声明文件，包含当前任务、重要上下文等信息。
        使用YAML frontmatter格式，便于程序解析。

        :returns: 解析后的上下文字典，包含metadata和content两部分。
        """
        content = self.workspace_read("AGENT_CONTEXT.md")
        if not content:
            return {"metadata": {}, "content": ""}

        return self._parse_context_md(content)

    def _parse_context_md(self, content: str) -> dict[str, Any]:
        """解析 AGENT_CONTEXT.md 文件（YAML frontmatter + markdown）。

        :param content: 文件原始内容。
        :returns: {"metadata": {...}, "content": "markdown内容"}
        """
        metadata: dict[str, Any] = {}
        body = content

        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                try:
                    from ruamel.yaml import YAML

                    yaml = YAML(typ="safe")
                    metadata = yaml.load(parts[1]) or {}
                except Exception:
                    pass
                body = parts[2].strip()

        return {"metadata": metadata, "content": body}

    def update_agent_context(self, updates: dict[str, Any]) -> None:
        """更新 AGENT_CONTEXT.md（合并而非覆盖）。

        :param updates: 要更新的metadata字段。
        """
        existing = self.read_agent_context()
        existing["metadata"].update(updates)
        self._write_agent_context(existing["metadata"], existing["content"])

    def set_agent_context_content(self, content: str) -> None:
        """设置 AGENT_CONTEXT.md 的内容部分（保留metadata）。

        :param content: 新的markdown内容。
        """
        existing = self.read_agent_context()
        self._write_agent_context(existing["metadata"], content)

    def _write_agent_context(self, metadata: dict[str, Any], content: str) -> None:
        """写入 AGENT_CONTEXT.md 文件。"""
        from ruamel.yaml import YAML
        from io import StringIO

        yaml = YAML()
        yaml.default_flow_style = False

        stream = StringIO()
        stream.write("---\n")
        yaml.dump(metadata, stream)
        stream.write("---\n\n")
        stream.write(content)

        self.workspace_write("AGENT_CONTEXT.md", stream.getvalue())

    def auto_update_agent_context(
        self,
        current_task: str | None = None,
        active_goal: str | None = None,
        priority: str | None = None,
        notes: str | None = None,
    ) -> None:
        """自动更新 AGENT_CONTEXT.md（仿真人行为追踪）。

        根据仿真人当前状态自动维护上下文文件，支持跨会话持久化。

        :param current_task: 当前任务描述。
        :param active_goal: 活跃目标。
        :param priority: 优先级。
        :param notes: 额外备注。
        """
        updates: dict[str, Any] = {}
        if current_task is not None:
            updates["current_task"] = current_task
        if active_goal is not None:
            updates["active_goal"] = active_goal
        if priority is not None:
            updates["priority"] = priority
        if updates:
            updates["last_updated"] = datetime.now().isoformat()
            self.update_agent_context(updates)

        if notes is not None:
            existing = self.read_agent_context()
            existing_content = existing.get("content", "")
            # 追加时间戳备注
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
            new_content = (
                f"{existing_content}\n\n## [{timestamp}]\n{notes}\n"
                if existing_content
                else f"## [{timestamp}]\n{notes}\n"
            )
            self.set_agent_context_content(new_content.strip())

    def sync_state_to_context(self) -> None:
        """将当前状态同步到 AGENT_CONTEXT.md。

        从 state 目录动态发现并读取状态文件，自动更新上下文。
        支持：
        1. 内置状态文件（emotion, intention, needs, plan）
        2. 用户扩展的状态文件（通过 state_config.extra_states 配置）
        3. 自动发现 state/ 目录下的所有 JSON 文件
        """
        if self._agent_work_dir is None:
            return

        updates: dict[str, Any] = {}
        max_len = 100
        if self._state_config is not None:
            max_len = getattr(self._state_config, "summary_max_length", 100)

        # 获取状态文件定义
        state_definitions: dict[str, tuple[str, str]] = {}
        if self._state_config is not None:
            state_definitions = self._state_config.get_all_states()
            auto_discover = getattr(self._state_config, "auto_discover", True)
        else:
            # 默认内置状态
            state_definitions = {
                "emotion": ("emotion.json", "primary"),
                "intention": ("intention.json", "intention"),
                "needs": ("needs.json", "current_need"),
                "plan": ("plan_state.json", "target"),
            }
            auto_discover = True

        # 读取已定义的状态文件
        for state_name, (filename, summary_field) in state_definitions.items():
            state_path = f"state/{filename}"
            data = self.read_json(state_path, {})
            if data:
                value = data.get(summary_field, "")
                if value:
                    updates[state_name] = str(value)[:max_len]

        # 自动发现其他状态文件
        if auto_discover:
            state_dir = self._agent_work_dir / "state"
            if state_dir.exists() and state_dir.is_dir():
                known_files = {
                    f"state/{fn}" for _, (fn, _) in state_definitions.items()
                }
                for state_file in state_dir.glob("*.json"):
                    relative_path = f"state/{state_file.name}"
                    if relative_path not in known_files:
                        data = self.read_json(relative_path, {})
                        if data:
                            # 使用文件名（去掉扩展名）作为键
                            key = state_file.stem
                            # 尝试找第一个非嵌套的字符串值作为摘要
                            for v in data.values():
                                if isinstance(v, str) and v:
                                    updates[key] = v[:max_len]
                                    break

        if updates:
            updates["last_sync"] = datetime.now().isoformat()
            self.update_agent_context(updates)

    def build_workspace_summary(self) -> str:
        """生成 workspace 内容摘要。

        用于在step开始时让agent快速了解workspace状态。
        动态发现 state/ 目录下的所有状态文件。

        :returns: workspace摘要文本。
        """
        if self._agent_work_dir is None:
            return ""

        summary = []

        # 1. AGENT_CONTEXT.md
        context = self.read_agent_context()
        if context.get("metadata"):
            task = context["metadata"].get("current_task", "")
            if task:
                summary.append(f"**Current Task**: {task}")

        # 2. 获取状态文件定义
        state_definitions: dict[str, tuple[str, str]] = {}
        if self._state_config is not None:
            state_definitions = self._state_config.get_all_states()

        # 3. State文件摘要（动态发现）
        state_dir = self._agent_work_dir / "state"
        if state_dir.exists():
            state_files = list(state_dir.glob("*.json"))
            if state_files:
                summary.append(f"**state/**: {len(state_files)} files")

                # 先处理已定义的状态文件
                processed = set()
                for state_name, (filename, summary_field) in state_definitions.items():
                    path = state_dir / filename
                    if path.exists():
                        processed.add(filename)
                        try:
                            data = json_repair.loads(path.read_text())
                            value = data.get(summary_field, "")
                            if value:
                                display_name = state_name.replace("_", " ").title()
                                summary.append(f"  - {display_name}: {str(value)[:50]}")
                        except Exception:
                            pass

                # 再处理其他状态文件
                for state_file in state_files:
                    if state_file.name not in processed:
                        try:
                            data = json_repair.loads(state_file.read_text())
                            # 找第一个字符串值作为摘要
                            for v in data.values():
                                if isinstance(v, str) and v:
                                    key = state_file.stem.replace("_", " ").title()
                                    summary.append(f"  - {key}: {v[:50]}")
                                    break
                        except Exception:
                            pass

        # 4. Memory摘要
        memory_file = self._agent_work_dir / "memory" / "memory.jsonl"
        if memory_file.exists():
            try:
                line_count = sum(1 for _ in memory_file.open())
                summary.append(f"**memory.jsonl**: {line_count} entries")
            except Exception:
                pass

        return "\n".join(summary) if summary else ""

    # ==================== Behavior Tracking (Observability) ====================

    def emit_behavior_event(
        self,
        event_type: str,
        data: dict[str, Any],
        tick: int | None = None,
    ) -> None:
        """发送行为事件到追踪日志。

        用于仿真行为分析和可观测性。

        :param event_type: 事件类型（如 "tool_call", "skill_activate", "decision"）。
        :param data: 事件数据。
        :param tick: 当前 tick（可选）。
        """
        if self._agent_work_dir is None:
            return

        event = {
            "timestamp": datetime.now().isoformat(),
            "agent_id": self._agent_id,
            "event_type": event_type,
            "tick": tick,
            "data": data,
        }

        # 追加到行为追踪日志
        path = self._agent_work_dir / "logs" / "behavior_trace.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(jr_dumps(event, indent=None) + "\n")

    def get_behavior_summary(self, limit: int = 100) -> dict[str, Any]:
        """获取行为摘要统计。

        :param limit: 读取的事件数量上限。
        :return: 行为摘要字典。
        """
        if self._agent_work_dir is None:
            return {}

        path = self._agent_work_dir / "logs" / "behavior_trace.jsonl"
        if not path.exists():
            return {}

        # 读取最近事件
        events: list[dict] = []
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    try:
                        events.append(json_repair.loads(line))
                    except Exception:
                        pass

        if not events:
            return {}

        recent = events[-limit:] if len(events) > limit else events

        # 统计
        tool_counts: dict[str, int] = {}
        skill_activations: dict[str, int] = {}
        errors: list[dict] = []

        for event in recent:
            event_type = event.get("event_type", "")
            data = event.get("data", {})

            if event_type == "tool_call":
                tool = data.get("tool", "unknown")
                tool_counts[tool] = tool_counts.get(tool, 0) + 1
            elif event_type == "skill_activate":
                skill = data.get("skill", "unknown")
                skill_activations[skill] = skill_activations.get(skill, 0) + 1
            elif event_type == "error":
                errors.append(
                    {
                        "tool": data.get("tool", "unknown"),
                        "error": str(data.get("error", ""))[:100],
                    }
                )

        return {
            "total_events": len(recent),
            "tool_usage": tool_counts,
            "skill_activations": skill_activations,
            "recent_errors": errors[-5:],
            "last_tick": recent[-1].get("tick") if recent else None,
        }
