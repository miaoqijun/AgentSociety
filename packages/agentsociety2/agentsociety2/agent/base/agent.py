"""AgentBase — the generic agent runtime base class.

中文：``AgentBase`` 是所有 agent 的基类，直接拥有 workspace 绑定、skill
runtime、ReAct 工具调度、identity、service slots、抽象契约和构造模型。
English: ``AgentBase`` is the base class for all agents. It directly owns
workspace binding, the skill runtime, ReAct tool dispatch, identity, service
slots, the abstract contract, and the construction model.

Construction model (no meaningful ``__init__``):

- ``AgentBase.__init__(self)`` — arg-less. Initializes empty slots only.
- ``AgentBase.create(workspace_path, profile, config)`` — write initial
  workspace (``config.json`` + ``AGENT.json`` + dirs). No instance.
- ``AgentBase.from_workspace(workspace_path, service_proxy)`` —
  ``agent = cls()``; ``await agent.restore(ws, proxy)``; return.
- ``AgentBase.restore(workspace_path, service_proxy)`` — the real init:
  read config.json + AGENT.json; set ``_id``/``_profile``/``_name``/``_config``;
  call ``_bind_services`` + ``_bind_workspace``; restore visible/activated
  skills + counters.
"""

from __future__ import annotations

import json
import logging
import re
from abc import ABC, abstractmethod
from collections.abc import Mapping
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, Iterator, Optional

from agentsociety2.agent.base.react import ReactDecision, ReactToolResult
from agentsociety2.agent.base.workspace import (
    AGENT_JSON_PATH,
    STANDARD_WORKSPACE_DIRS,
    dump_json,
)
from agentsociety2.agent.base.tool_schema import react_tool_schemas
from agentsociety2.agent.base.todo import TodoStateStore
from agentsociety2.agent.person_prompt import (
    short_text as _short_text,
    xml_block as _xml_block,
)
from agentsociety2.agent.base.registry import get_skill_registry
from agentsociety2.agent.base.runtime import AgentSkillRuntime
from agentsociety2.agent.base.workspace_fs import WorkspaceFS
from agentsociety2.env.router_base import RouterBase
from agentsociety2.logger import get_logger
from agentsociety2.trace import (
    JsonlTraceWriter,
    TraceSpan,
)

if TYPE_CHECKING:
    from agentsociety2.agent.service_proxy import ServiceProxy

__all__ = [
    "AgentBase",
]

logger = get_logger()

# Short clock shorthand (HH:MM) used to normalize TODO ``due`` values.
_SHORT_CLOCK_RE = re.compile(r"^(?P<hour>[01]?\d|2[0-3]):(?P<minute>[0-5]\d)$")


def _brief_memories_summary(memories: Any) -> str:
    """Derive a one-line step result from inline finish memories.

    Step-mode ``finish`` carries only ``memories`` (no ``final`` text); this
    builds a short summary from the first recorded episode so the step result /
    trace stays readable. Returns ``""`` when there is nothing to summarize.

    :param memories: The ``memories`` list from a finish tool call (or None).
    :returns: A short summary string (empty if no usable memory text).
    """
    if not isinstance(memories, list) or not memories:
        return ""
    first = memories[0]
    text = ""
    if isinstance(first, dict):
        text = str(first.get("text") or "").strip()
    elif isinstance(first, str):
        text = first.strip()
    return text[:160]


class AgentBase(ABC):
    """Abstract base class for all agents.

    Directly owns the generic agent runtime (workspace binding, skill
    runtime, ReAct tool dispatch) plus identity, service slots, and the
    abstract contract.  Construction is via ``create`` / ``from_workspace``;
    ``__init__`` is arg-less.

    Subclasses must implement (forced abstracts):

    - :meth:`create`
    - :meth:`from_workspace`
    - :meth:`to_workspace`
    - :meth:`ask`
    - :meth:`step`
    """

    def __init__(self) -> None:
        """Initialize an unbound agent (arg-less).

        Only empty slots are set; no profile parsing, no id required.  The
        real initialization happens in :meth:`restore` (called by
        :meth:`from_workspace`).
        """
        # Identity slots — populated by restore.
        self._id: int | None = None
        self._profile: Any = None
        self._name: Optional[str] = None
        self._config: dict[str, Any] = {}

        # Runtime service slots — injected by _bind_services.
        self._service_proxy: "ServiceProxy | None" = None
        self._dispatcher = None
        self._model_name: str | None = None
        self._env: RouterBase | None = None
        self._logger = get_logger()

        # Memories the model recorded inline in the step-mode `finish` tool call
        # (avoids a separate extraction LLM pass). Set by run_react_loop on
        # finish; consumed by step() -> memory_runtime.after_step. None when the
        # loop finished without a finish tool call or in ask mode.
        self._last_finish_memories: list[dict[str, Any]] | None = None

        # Workspace / trace placeholders.
        self._workspace_root: Path | None = None
        self._workspace_fs: WorkspaceFS | None = None
        self._jsonl_trace_writer: JsonlTraceWriter | None = None

        # Skill placeholders.  _setup_skill_runtime needs an agent id, so it
        # runs inside restore once _id is known.
        self._skill_registry = None
        self.skill_runtime = None
        self._disabled_skill_ids: set[str] = set()
        self._default_activated_skill_ids: set[str] = set()
        self._default_activated_skills_applied: bool = False

        # Generic counters / state — set by restore / subclass restore.
        self._step_count: int = 0
        self._initialized_at: str | None = None
        self._current_time: datetime | None = None

        # Generic ReAct / tool-loop config flags — populated by restore from
        # self._config.  Subclasses (e.g. PersonAgent) may additionally set
        # feature-specific flags (such as _enable_memory) in their own config
        # helper, but these base flags are owned here so the generic react
        # loop and tool dispatcher work for any AgentBase subclass.
        self._max_react_turns: int = 10
        self._enable_todo_list: bool = True
        self._enable_memory: bool = False

    # ------------------------------------------------------------------
    # Service binding
    # ------------------------------------------------------------------

    def _bind_services(self, service_proxy: "ServiceProxy") -> None:
        """Inject runtime shared services (called by ``from_workspace``).

        Binds ``service_proxy`` and its env + default-LLM dispatcher to
        ``self._env`` / ``self._dispatcher`` / ``self._model_name``.

        Args:
            service_proxy: Shared service container (env / llm / trace / replay).
        """
        self._service_proxy = service_proxy
        self._env = service_proxy.env
        default = service_proxy.llm.default
        self._dispatcher = default
        self._model_name = getattr(default, "model_name", None)

    # ------------------------------------------------------------------
    # Construction model
    # ------------------------------------------------------------------

    @classmethod
    def create(cls, workspace_path: Path, profile: dict, config: dict) -> None:
        """Create the initial agent workspace (static, write-once config).

        Writes ``config.json`` (static, never rewritten) + initial ``AGENT.json``
        + the standard empty directories.  Does NOT return an agent instance;
        use :meth:`from_workspace` to reconstruct.

        Args:
            workspace_path: Agent workspace root (created if missing).
            profile: Agent profile dict (must include ``id``).
            config: Static config dict written verbatim to ``config.json``.
        """
        workspace_path = Path(workspace_path)
        workspace_path.mkdir(parents=True, exist_ok=True)
        for rel in STANDARD_WORKSPACE_DIRS:
            (workspace_path / rel).mkdir(parents=True, exist_ok=True)
        (workspace_path / "config.json").write_text(
            dump_json(dict(config or {}), indent=2), encoding="utf-8"
        )
        agent_id = int(profile.get("id", 0))
        name = AgentBase._derive_name(profile, agent_id)
        initial_agent = {
            "schema_version": 1,
            "agent_class": cls.__name__,
            "agent_id": agent_id,
            "id": agent_id,
            "name": name,
            "profile": profile,
            "step_count": 0,
            "current_time": None,
            "tick": None,
            "visible_skills": [],
            "activated_skills": [],
            "disabled_skills": sorted(
                str(s)
                for s in (config or {}).get("disabled_skill_ids", [])
                if str(s).strip()
            ),
            "default_activated_skills": sorted(
                str(s)
                for s in (config or {}).get("default_activated_skill_ids", [])
                if str(s).strip()
            ),
            "initialized_at": None,
        }
        (workspace_path / AGENT_JSON_PATH).write_text(
            dump_json(initial_agent, indent=2), encoding="utf-8"
        )

    @classmethod
    async def from_workspace(
        cls, workspace_path: Path, service_proxy: "ServiceProxy"
    ) -> "AgentBase":
        """Reconstruct a ready agent from its workspace.

        ``agent = cls()`` (arg-less); ``await agent.restore(ws, proxy)``;
        return the agent.

        Args:
            workspace_path: Agent workspace root.
            service_proxy: Shared service container (env / llm / trace / replay).

        Returns:
            Ready agent instance.
        """
        agent = cls()
        await agent.restore(workspace_path, service_proxy)
        return agent

    async def restore(
        self,
        workspace_path: Path,
        service_proxy: "ServiceProxy",
    ) -> None:
        """The real initialization (called by ``from_workspace``).

        Reads ``config.json`` + ``AGENT.json``; sets ``_id``/``_profile``/
        ``_name``/``_config``; calls ``_bind_services`` + ``_bind_workspace``;
        restores visible/activated skills + counters.

        Subclasses override this to ALSO restore person-specific state after
        ``await super().restore(...)``.

        Args:
            workspace_path: Agent workspace root.
            service_proxy: Shared service container.
        """
        workspace_path = Path(workspace_path)
        config = json.loads(
            (workspace_path / "config.json").read_text(encoding="utf-8")
        )
        meta = json.loads(
            (workspace_path / AGENT_JSON_PATH).read_text(encoding="utf-8")
        )
        self._config = dict(config or {})
        self._id = int(meta.get("agent_id", meta.get("id", 0)))
        self._profile = meta.get("profile", {})
        self._name = meta.get("name") or self._derive_name(self._profile, self._id)

        # Generic config-derived skill sets.
        self._disabled_skill_ids = set(self._config.get("disabled_skill_ids") or [])
        self._default_activated_skill_ids = {
            str(sid)
            for sid in (self._config.get("default_activated_skill_ids") or [])
            if str(sid).strip()
        } - self._disabled_skill_ids

        # Services + workspace.
        self._bind_services(service_proxy)
        self._setup_skill_runtime(agent_id=self._id)
        self._bind_workspace(workspace_path)

        # Generic react-loop / tool config flags (own read; subclasses extend).
        self._max_react_turns = max(
            1, int(self._config.get("max_react_turns", 10) or 10)
        )
        self._enable_todo_list = bool(self._config.get("enable_todo_list", True))
        # _enable_memory defaults to False at the base level; PersonAgent
        # overrides it in _apply_person_config.

        # Restore visible/activated skill subset from AGENT.json.
        visible = {str(s) for s in meta.get("visible_skills", []) if str(s).strip()}
        activated = {str(s) for s in meta.get("activated_skills", []) if str(s).strip()}
        self.skill_runtime.set_visible_skills(visible)
        self.skill_runtime.set_activated_skills(activated)

        # Restore counters and time.
        self._step_count = int(meta.get("step_count", 0))
        current_time = meta.get("current_time")
        if current_time:
            try:
                self._current_time = datetime.fromisoformat(str(current_time))
            except ValueError:
                self._current_time = None
        else:
            self._current_time = None
        initialized_at = meta.get("initialized_at")
        self._initialized_at = str(initialized_at) if initialized_at else None
        self._default_activated_skills_applied = bool(activated) or bool(
            self._default_activated_skill_ids
        )

    # ------------------------------------------------------------------
    # Abstract methods (subclasses must implement these three;
    # create / from_workspace have concrete base implementations above)
    # ------------------------------------------------------------------

    @abstractmethod
    async def to_workspace(self, workspace_path: Path) -> None:
        """Write current dynamic state back to the workspace."""
        raise NotImplementedError

    @abstractmethod
    async def ask(
        self,
        message: str,
        readonly: bool = True,
        *,
        t: datetime | None = None,
    ) -> str:
        """Answer an external question through the agent's reasoning flow."""
        raise NotImplementedError

    @abstractmethod
    async def step(self, tick: int, t: datetime) -> str:
        """Run one simulation step."""
        raise NotImplementedError

    # ------------------------------------------------------------------
    # Identity + properties
    # ------------------------------------------------------------------

    @property
    def id(self) -> int:
        """Agent unique identifier."""
        return self._id

    @property
    def name(self) -> str:
        """Agent display name."""
        return self._name

    @property
    def logger(self) -> logging.Logger:
        """Agent-scoped logger."""
        return self._logger

    def env_ask_env_ctx_overlay(self) -> dict[str, Any]:
        """Generate the ask_env / CodeGenRouter.ask context overlay.

        Returns the stable identity keys (id, agent_id, person_id) provided by
        the framework, independent of any skill.

        :returns: dict with id, agent_id, person_id.
        """
        i = self.id
        return {"id": i, "agent_id": i, "person_id": i}

    async def ask_env(
        self,
        ctx: dict,
        message: str,
        readonly: bool,
        template_mode: bool = False,
        trace_id: str | None = None,
        parent_span_id: str | None = None,
    ):
        """Send a request to the environment router.

        Wraps interaction with the simulation environment, supporting template
        mode and context-variable substitution.

        :param ctx: Context dict (may include a ``variables`` key for template mode).
        :param message: Request message.
        :param readonly: Whether this is a read-only request.
        :param template_mode: Whether to enable template mode.
        :param trace_id: OTel trace ID for cross-agent/env correlation.
        :param parent_span_id: OTel parent span ID.
        :returns: Tuple ``(ctx, answer)``.
        """
        assert self._env is not None, "Environment is not initialized"
        merged_ctx = {**ctx, **self.env_ask_env_ctx_overlay()}
        ctx, answer = await self._env.ask(
            merged_ctx,
            message,
            readonly=readonly,
            template_mode=template_mode,
            trace_id=trace_id,
            parent_span_id=parent_span_id,
        )
        return ctx, answer

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def acompletion(
        self,
        messages: list[dict[str, Any]],
        stream: bool = False,
        **kwargs: Any,
    ) -> Any:
        """Single LLM completion via the bound default-role dispatcher.

        Convenience for subclasses that need a one-shot LLM call (the full
        multi-turn tool loop is :meth:`run_react_loop`). Uses the agent's
        bound dispatcher + model.

        Args:
            messages: Chat messages.
            stream: Streaming flag (False by default; the local LLM dispatcher
                does not support streaming).
            **kwargs: Extra litellm kwargs (timeout, tools, ...).

        Returns:
            The LLM response (litellm ``ModelResponse``).
        """
        assert self._dispatcher is not None, "Agent LLM dispatcher is not bound"
        return await self._dispatcher.call(
            model=self._model_name,
            messages=messages,
            stream=stream,
            **kwargs,
        )

    async def close(self):
        """Close the agent and release resources. Subclasses may override."""
        ...

    def get_profile(self) -> Dict[str, Any]:
        """Return the agent profile as a dict.

        :returns: Profile dict (raw dict, model_dump, or ``{"raw": str}``).
        """
        if isinstance(self._profile, dict):
            return self._profile
        elif hasattr(self._profile, "model_dump"):
            return self._profile.model_dump()
        else:
            return {"raw": str(self._profile)}

    # ------------------------------------------------------------------
    # Descriptions
    # ------------------------------------------------------------------

    @classmethod
    def description(cls) -> str:
        """Return a short agent description for module lists."""
        if cls is AgentBase:
            return "Abstract base class for agents."
        doc = (cls.__doc__ or "").strip().splitlines()
        return doc[0].strip() if doc else f"{cls.__name__}: Agent class."

    @classmethod
    def init_description(cls) -> str:
        """Return AI-readable initialization guidance for this agent class."""
        if cls is AgentBase:
            description = f"""{cls.__name__}: Abstract base class for agents.

**Description:** {cls.__doc__ or "No description available"}

**Construction:** Agents are created via ``AgentBase.create(workspace_path, profile, config)``
and reconstructed via ``await AgentBase.from_workspace(workspace_path, service_proxy)``.
The constructor ``__init__`` is arg-less.

**Note:** This is an abstract base class. Do not use it directly.

**Example initialization config:**
```json
{{
  "id": 1,
  "profile": {{
    "name": "Alice",
    "gender": "female",
    "age": 30,
    "education": "University",
    "occupation": "Engineer",
    "marriage_status": "single",
    "persona": "helpful",
    "background_story": "A software engineer who loves coding."
  }},
  "config": {{}}
}}
```
"""
        else:
            description = f"""{cls.__name__}: Agent class.

**Description:** {cls.__doc__ or "No description available"}

**Construction:** Agents are created via ``{cls.__name__}.create(workspace_path, profile, config)``
and reconstructed via ``await {cls.__name__}.from_workspace(workspace_path, service_proxy)``.
The constructor ``__init__`` is arg-less.

**Note:** This subclass has not provided a detailed description. Please refer to the class documentation or source code.
"""
        return description

    # ==================================================================
    # Workspace binding
    # ==================================================================

    def _bind_workspace(self, workspace_path: Path) -> None:
        """Bind runtime objects to an EXISTING workspace (no directory creation).

        Assumes the workspace already exists (created by :meth:`create`).
        Sets up WorkspaceFS + the trace writer, and binds the skill runtime.

        Trace writes go through a local :class:`ShardedAppendSink`
        (``service_proxy.trace`` carries only the output dir) — no per-workspace
        event file, no central trace actor. When no proxy trace is bound, spans
        are still created (the span API works) but not recorded (no-op).

        Args:
            workspace_path: Existing agent workspace root.
        """
        workspace = Path(workspace_path).resolve()
        self._workspace_root = workspace
        self._workspace_fs = WorkspaceFS(workspace)
        sharded = self._maybe_proxy_sharded_writer()
        self._jsonl_trace_writer = JsonlTraceWriter(
            agent_id=self.id,
            sharded_writer=sharded,
        )
        # Bind the skill runtime if present.
        skill_runtime = getattr(self, "skill_runtime", None)
        if skill_runtime is not None:
            skill_runtime.bind_workspace(
                workspace_root=workspace,
                fs=self._workspace_fs,
                trace_writer=self._jsonl_trace_writer,
            )

    def _maybe_proxy_sharded_writer(self):
        """Return a local sharded sink if trace is enabled on the bound proxy.

        Looks at ``self._service_proxy.trace``; if it carries a ``trace_dir``,
        build this agent's own :class:`ShardedAppendSink` (distributed,
        append-only, no central actor). Otherwise return ``None`` (no-op).
        """
        proxy = getattr(self, "_service_proxy", None)
        if proxy is None:
            return None
        trace = getattr(proxy, "trace", None)
        if trace is None:
            return None
        from agentsociety2.trace import build_local_sink

        return build_local_sink(trace)

    @staticmethod
    def _derive_name(profile: Any, agent_id: int) -> str:
        """Derive a display name from profile/id.

        Args:
            profile: Agent profile (dict or object).
            agent_id: Agent id fallback.

        Returns:
            Display name string.
        """
        if isinstance(profile, dict) and profile.get("name"):
            return str(profile["name"])
        if hasattr(profile, "name") and getattr(profile, "name", None):
            return str(profile.name)
        return f"Agent_{agent_id}"

    def workspace_root_path(self) -> Path:
        """Return the agent-owned workspace root.

        Raises:
            RuntimeError: When the workspace is not initialized.
        """
        if self._workspace_root is None:
            raise RuntimeError("Agent workspace is not initialized")
        return self._workspace_root

    @property
    def _workspace(self) -> WorkspaceFS:
        """Return the agent-owned workspace filesystem."""
        if self._workspace_fs is None:
            raise RuntimeError("Agent workspace is not initialized")
        return self._workspace_fs

    @property
    def _trace(self) -> JsonlTraceWriter:
        """Return the agent-owned trace writer."""
        if self._jsonl_trace_writer is None:
            raise RuntimeError("Agent trace writer is not initialized")
        return self._jsonl_trace_writer

    # ------------------------------------------------------------------
    # Trace span helpers
    # ------------------------------------------------------------------

    @property
    def _current_trace_span(self) -> TraceSpan | None:
        """Return the current active trace span, or None."""
        return (
            self._jsonl_trace_writer.current_span if self._jsonl_trace_writer else None
        )

    def _start_trace_span(
        self,
        name: str,
        *,
        trace_id: str | None = None,
        parent_span_id: str | None = None,
        attributes: dict[str, Any] | None = None,
    ) -> TraceSpan:
        """Start an agent-owned trace span."""
        return self._trace.start_span(
            name,
            trace_id=trace_id,
            parent_span_id=parent_span_id,
            attributes=attributes,
        )

    def _end_trace_span(
        self,
        span: TraceSpan,
        *,
        status: str = "ok",
        message: str = "",
        attributes: dict[str, Any] | None = None,
    ) -> None:
        """End an agent-owned trace span."""
        self._trace.end_span(
            span,
            status=status,
            message=message,
            attributes=attributes,
        )

    @contextmanager
    def trace_span(
        self,
        name: str,
        *,
        trace_id: str | None = None,
        parent_span_id: str | None = None,
        attributes: dict[str, Any] | None = None,
        end_attributes: dict[str, Any] | None = None,
    ) -> Iterator[TraceSpan]:
        """Create an agent-owned trace span context."""
        with self._trace.trace_span(
            name,
            trace_id=trace_id,
            parent_span_id=parent_span_id,
            attributes=attributes,
            end_attributes=end_attributes,
        ) as span:
            yield span

    # ------------------------------------------------------------------
    # AGENT.json persistence
    # ------------------------------------------------------------------

    def build_agent_json(
        self,
        *,
        tick: int | None,
        t: Any | None,
    ) -> dict[str, Any]:
        """Build the consolidated self-description file for the agent.

        Subclasses may override to add extra fields (e.g. memory summary).

        Args:
            tick: Current simulation tick, if available.
            t: Current simulation time, if available.

        Returns:
            Serializable AGENT.json dictionary.
        """
        skill_runtime = getattr(self, "skill_runtime", None)
        visible = sorted(skill_runtime.visible_skill_ids()) if skill_runtime else []
        activated = sorted(skill_runtime.activated_skill_ids()) if skill_runtime else []
        return {
            "schema_version": 1,
            "agent_class": type(self).__name__,
            "agent_id": self.id,
            "name": self.name,
            "current_time": t.isoformat() if t is not None else None,
            "tick": tick,
            "step_count": getattr(self, "_step_count", 0),
            "profile": self.get_profile(),
            "workspace": {
                "root": str(self.workspace_root_path()),
                "agent_json_path": AGENT_JSON_PATH,
            },
            "skills": {
                "visible": visible,
                "activated": activated,
            },
            "initialized_at": getattr(self, "_initialized_at", None),
        }

    def persist_agent_json(
        self,
        *,
        tick: int | None = None,
        t: Any | None = None,
    ) -> dict[str, Any]:
        """Persist consolidated agent self-description to AGENT.json.

        Args:
            tick: Current simulation tick, if available.
            t: Current simulation time, if available.

        Returns:
            Data written to AGENT.json.
        """
        data = self.build_agent_json(tick=tick, t=t)
        self._workspace.write_text(
            AGENT_JSON_PATH,
            dump_json(data, indent=2),
        )
        return data

    # ==================================================================
    # Skill runtime
    # ==================================================================

    def _setup_skill_runtime(self, *, agent_id: int) -> None:
        """Initialize the shared skill registry and this agent's runtime.

        Args:
            agent_id: Numeric agent id.
        """
        self._skill_registry = get_skill_registry()
        self.skill_runtime = AgentSkillRuntime(
            agent_id=agent_id,
            registry=self._skill_registry,
        )

    # ------------------------------------------------------------------
    # Discovery + visibility
    # ------------------------------------------------------------------

    def _refresh_visible_skills(self) -> None:
        """Refresh visible skills after registry changes."""
        visible_skill_ids = {
            info.skill_id
            for info in self._skill_registry.list_all()
            if info.skill_id not in self._disabled_skill_ids
        }
        self.skill_runtime.set_visible_skills(visible_skill_ids)

    def discover_skill_sources(self, env: RouterBase) -> dict[str, list[str]]:
        """Discover custom and environment-provided skill sources.

        Args:
            env: Environment router used to locate run directories and modules.

        Returns:
            Mapping from discovery source labels to added skill IDs.
        """
        discovered: dict[str, list[str]] = {}

        roots: list[Path] = []
        run_dir = getattr(env, "run_dir", None)
        if run_dir:
            roots.append(Path(run_dir))
        roots.append(self.workspace_root_path())

        seen: set[Path] = set()
        for root in roots:
            root_abs = root.resolve()
            if root_abs in seen:
                continue
            seen.add(root_abs)
            try:
                added = self._skill_registry.scan_custom(root_abs / "custom" / "skills")
            except Exception as exc:
                logger.warning(
                    "Agent %s: custom skill scan failed at %s: %s",
                    self.id,
                    root_abs,
                    exc,
                )
                added = []
            if added:
                discovered[f"custom:{root_abs}"] = added

        for module in getattr(env, "env_modules", []) or []:
            for skills_dir in module.skill_dirs():
                try:
                    added = self._skill_registry.scan_env(
                        skills_dir,
                        type(module).__name__,
                    )
                except Exception as exc:
                    logger.warning(
                        "Agent %s: env skill scan failed at %s: %s",
                        self.id,
                        skills_dir,
                        exc,
                    )
                    added = []
                if added:
                    discovered[f"env:{type(module).__name__}:{skills_dir}"] = added

        self._refresh_visible_skills()
        if not self._default_activated_skills_applied:
            self.skill_runtime.add_default_activated_skills(
                self._default_activated_skill_ids
            )
            self._default_activated_skills_applied = True
        return discovered

    def _resolve_skill_id_from_args(self, args: Mapping[str, Any]) -> str:
        """Resolve skill_name-first tool arguments to a registry skill id.

        Args:
            args: Tool argument mapping containing ``skill_name``.

        Returns:
            Matching visible skill ID, or an empty string.
        """
        skill_id = self.skill_runtime.resolve_skill_id_by_name(
            str(args.get("skill_name") or "")
        )
        if skill_id:
            return skill_id
        return self.skill_runtime.infer_single_script_skill_id()

    # ------------------------------------------------------------------
    # Lifecycle hooks
    # ------------------------------------------------------------------

    async def run_lifecycle_hooks(
        self,
        hook_type: str,
        *,
        tick: int,
        t: Any,
    ) -> list[dict[str, Any]]:
        """Run lifecycle hooks for currently activated skills.

        Args:
            hook_type: Lifecycle hook name, such as ``pre_step`` or ``post_step``.
            tick: Current simulation tick.
            t: Current simulation time.

        Returns:
            Hook execution summaries.
        """
        payload = {
            "hook_type": hook_type,
            "tick": tick,
            "time": t.isoformat(),
            "agent_id": self.id,
            "step_count": getattr(self, "_step_count", 0),
        }
        summaries: list[dict[str, Any]] = []
        argv = ["--args-json", dump_json(payload)]
        with self.trace_span(
            f"skill.lifecycle_hooks.{hook_type}",
            attributes={
                "operation.type": "skill",
                "hook.type": hook_type,
                "agent.tick": tick,
            },
        ) as span:
            for info in self.skill_runtime.active_hook_skills(hook_type):
                result = await self.skill_runtime.run_skill_hook(
                    info.skill_id,
                    hook_type,
                    argv,
                    timeout_sec=30,
                )
                summary = {
                    "skill_id": info.skill_id,
                    "hook_type": hook_type,
                    "ok": result.ok,
                    "exit_code": result.exit_code,
                    "stdout": _short_text(result.stdout, limit=1000),
                    "stderr": _short_text(result.stderr, limit=1000),
                }
                summaries.append(summary)
                if not result.ok:
                    logger.warning(
                        "Agent %s: lifecycle hook failed: %s %s",
                        self.id,
                        info.skill_id,
                        hook_type,
                    )
            span.attributes.update(
                {
                    "hook.executed_count": len(summaries),
                    "hook.failed_count": sum(1 for item in summaries if not item["ok"]),
                }
            )
        return summaries

    # ==================================================================
    # ReAct tool dispatch
    # ==================================================================

    # ------------------------------------------------------------------
    # Tool execution (trace-span wrapper)
    # ------------------------------------------------------------------

    async def _execute_react_tool(
        self,
        decision: ReactDecision,
        *,
        readonly: bool = False,
    ) -> ReactToolResult:
        """Execute one ReAct tool under a trace span.

        Args:
            decision: Parsed ReAct decision to execute.
            readonly: Whether mutation tools should be blocked.

        Returns:
            Tool execution result.
        """
        action = decision.action
        args = decision.args
        with self.trace_span(
            "react.tool",
            attributes={
                "operation.type": "react",
                "react.action": action,
            },
        ) as span:
            result = await self.dispatch_react_tool(action, args, readonly=readonly)
            update: dict[str, Any] = {
                "result.ok": result.ok,
                "output.summary": {
                    "observation": result.observation,
                },
            }
            if result.data:
                update["tool.data"] = result.data
            span.attributes.update(update)
            return result

    # ------------------------------------------------------------------
    # Core dispatch
    # ------------------------------------------------------------------

    async def dispatch_react_tool(
        self,
        action: str,
        args: dict[str, Any],
        *,
        readonly: bool = False,
    ) -> ReactToolResult:
        """Dispatch one ReAct tool call.

        Handles workspace file tools, skill tools, and ask_env. Person-specific
        tools (memory_*, todo_*) are handled by the subclass before this method
        is reached (or via a subclass override).

        Args:
            action: Tool name.
            args: Tool argument dictionary.
            readonly: Whether mutation tools should be blocked.

        Returns:
            Tool execution result.
        """
        try:
            if readonly and action in {"write", "append"}:
                return ReactToolResult(
                    False,
                    f"{action} is disabled in readonly mode",
                    {"action": action, "readonly": True},
                )
            if action == "read":
                path = str(args.get("path") or "")
                requested_path = path
                path = self._normalize_workspace_read_path(path)
                with self.trace_span(
                    "workspace.read_text",
                    attributes={
                        "operation.type": "workspace",
                        "workspace.path": requested_path,
                        "workspace.normalized_path": path,
                    },
                ) as workspace_span:
                    try:
                        content = self._workspace.read_text(path)
                    except ValueError as read_err:
                        # The path escapes the agent workspace. If it points at
                        # a file bundled inside a visible skill (a common
                        # mistake — e.g. trying to ``read`` a skill's
                        # ``references/*.md``), serve it via read_skill_file
                        # instead of surfacing an opaque escape error.
                        resolved = self._try_read_skill_path(requested_path or path)
                        if resolved is not None:
                            skill_id, rel_path, content = resolved
                            workspace_span.attributes["skill_redirect"] = skill_id
                            workspace_span.attributes["result.size"] = len(content)
                            return ReactToolResult(
                                True,
                                content,
                                {
                                    "skill_id": skill_id,
                                    "path": rel_path,
                                    "redirected_from": requested_path,
                                },
                            )
                        raise read_err
                    workspace_span.attributes["result.size"] = len(content)
                return ReactToolResult(True, content, {"path": path})
            if action == "write":
                path = str(args.get("path") or "")
                if self._is_core_owned_workspace_path(path):
                    return ReactToolResult(
                        True,
                        (
                            f"{path} is managed by the agent runtime and cannot "
                            "be written directly; no workspace write was performed"
                        ),
                        {"path": path, "core_owned": True, "noop": True},
                    )
                content = str(args.get("content") or "")
                with self.trace_span(
                    "workspace.write_text",
                    attributes={
                        "operation.type": "workspace",
                        "workspace.path": path,
                    },
                ) as workspace_span:
                    result = self._workspace.write_text(path, content)
                    workspace_span.attributes["result.bytes"] = result.bytes_written
                target = str(self._workspace.resolve(path))
                return ReactToolResult(True, f"written: {path}", {"path": target})
            if action == "append":
                path = str(args.get("path") or "")
                if self._is_core_owned_workspace_path(path):
                    return ReactToolResult(
                        True,
                        (
                            f"{path} is managed by the agent runtime and cannot "
                            "be appended directly; no workspace append was performed"
                        ),
                        {"path": path, "core_owned": True, "noop": True},
                    )
                content = str(args.get("content") or "")
                with self.trace_span(
                    "workspace.append_text",
                    attributes={
                        "operation.type": "workspace",
                        "workspace.path": path,
                    },
                ) as workspace_span:
                    result = self._workspace.append_text(path, content)
                    workspace_span.attributes["result.bytes"] = result.bytes_written
                return ReactToolResult(result.ok, f"appended: {path}", result.__dict__)
            if action == "list":
                path = str(args.get("path") or ".")
                files = [
                    item.path
                    for item in self._workspace.list(path, limit=10_000)
                    if not item.is_dir
                ]
                return ReactToolResult(True, dump_json(files), {"files": files})
            if action == "grep":
                pattern = str(args.get("pattern") or "")
                path = str(args.get("path") or ".")
                limit = int(args.get("limit") or 100)
                with self.trace_span(
                    "workspace.grep",
                    attributes={
                        "operation.type": "workspace",
                        "workspace.path": path,
                        "grep.pattern": pattern,
                    },
                ) as workspace_span:
                    matches = await self._workspace.grep(pattern, path, limit=limit)
                    workspace_span.attributes["result.count"] = len(matches)
                data = {"matches": [item.__dict__ for item in matches]}
                return ReactToolResult(True, dump_json(data), data)
            if action == "activate_skill":
                requested_skill_name = str(args.get("skill_name") or "")
                activated, skill_id, doc = self.skill_runtime.activate_skill_by_name(
                    requested_skill_name
                )
                if not activated:
                    if skill_id:
                        observation = (
                            "activate_skill failed: "
                            f"skill_name={requested_skill_name!r} resolved to "
                            f"skill_id={skill_id!r}, but its SKILL.md is missing or empty"
                        )
                        error = "skill_doc_unavailable"
                    else:
                        observation = (
                            "activate_skill failed: "
                            f"skill_name={requested_skill_name!r} is not visible, "
                            "does not exist, or is ambiguous; use a skill name from "
                            "the visible skill catalog"
                        )
                        error = "skill_not_resolved"
                    return ReactToolResult(
                        False,
                        observation,
                        {
                            "skill_id": skill_id,
                            "skill_name": requested_skill_name,
                            "activated": False,
                            "error": error,
                        },
                    )
                return ReactToolResult(
                    True,
                    doc,
                    {
                        "skill_id": skill_id,
                        "skill_name": requested_skill_name,
                        "activated": True,
                    },
                )
            if action == "deactivate_skill":
                removed, skill_id = self.skill_runtime.deactivate_skill_by_name(
                    str(args.get("skill_name") or "")
                )
                return ReactToolResult(
                    True,
                    f"deactivated: {skill_id}"
                    if removed
                    else f"not active: {skill_id}",
                    {"skill_id": skill_id, "removed": removed},
                )
            if action == "read_skill_file":
                skill_id = self._resolve_skill_id_from_args(args)
                path = str(args.get("path") or "")
                content = self.skill_runtime.read_skill_file(skill_id, path)
                return ReactToolResult(
                    bool(content),
                    content,
                    {
                        "skill_id": skill_id,
                        "path": path,
                        "content_len": len(content or ""),
                    },
                )
            if action == "execute_skill_script":
                skill_id = self._resolve_skill_id_from_args(args)
                script_path = str(args.get("script_path") or "")
                argv = args.get("argv")
                argv_list = (
                    [str(item) for item in argv] if isinstance(argv, list) else []
                )
                if skill_id.startswith("env:"):
                    instruction = self._build_env_skill_instruction(args, argv_list)
                    env_readonly = bool(args.get("readonly", False))
                    if readonly and not env_readonly:
                        return ReactToolResult(
                            False,
                            "environment skill mutation is disabled in readonly mode",
                            {
                                "skill_id": skill_id,
                                "argv": argv_list,
                                "readonly": True,
                            },
                        )
                    _span = self._current_trace_span
                    _, answer = await self.ask_env(
                        self._build_env_tool_context(args),
                        instruction,
                        readonly=env_readonly,
                        template_mode=True,
                        trace_id=_span.trace_id if _span else None,
                        parent_span_id=_span.span_id if _span else None,
                    )
                    return ReactToolResult(
                        True,
                        str(answer or ""),
                        {
                            "skill_id": skill_id,
                            "argv": argv_list,
                            "instruction": instruction,
                            "redirected_to": "ask_env",
                            "readonly": env_readonly,
                        },
                    )
                result = await self.skill_runtime.run_skill_script(
                    skill_id,
                    script_path,
                    argv_list,
                    timeout_sec=int(args.get("timeout_sec") or 30),
                )
                return ReactToolResult(
                    result.ok,
                    dump_json(result.as_dict()),
                    {
                        "skill_id": skill_id,
                        "script_path": script_path,
                        "argv": argv_list,
                        "exit_code": result.exit_code,
                        "stdout_len": len(result.stdout or ""),
                        "stderr_len": len(result.stderr or ""),
                        **({"stdout": result.stdout} if result.stdout else {}),
                        **({"stderr": result.stderr} if result.stderr else {}),
                    },
                )
            if action == "ask_env":
                ctx = self._build_env_tool_context(args)
                instruction = str(args.get("instruction") or "")
                if not instruction:
                    return ReactToolResult(
                        False,
                        "ask_env requires instruction",
                        {"error": "missing instruction"},
                    )
                # Template/cache mode is always forced on for ask_env so the
                # router reuses cached code for similar instructions instead of
                # regenerating (and paying an LLM round-trip) on every call.
                template = True
                env_readonly = bool(args.get("readonly", False))
                if readonly and not env_readonly:
                    return ReactToolResult(
                        False,
                        "ask_env mutation is disabled in readonly mode",
                        {"instruction": instruction, "readonly": True},
                    )
                _span = self._current_trace_span
                _, answer = await self.ask_env(
                    ctx,
                    instruction,
                    readonly=env_readonly,
                    template_mode=bool(template),
                    trace_id=_span.trace_id if _span else None,
                    parent_span_id=_span.span_id if _span else None,
                )
                return ReactToolResult(
                    True,
                    str(answer or ""),
                    {"instruction": instruction, "template_mode": bool(template)},
                )
            return ReactToolResult(
                False,
                f"unknown action: {action}",
                {"action": action},
            )
        except Exception as exc:
            return ReactToolResult(False, str(exc), {"error": str(exc)})

    # ------------------------------------------------------------------
    # Path helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _is_core_owned_workspace_path(path: str) -> bool:
        """Return whether a workspace path is owned by agent core runtime.

        Args:
            path: Workspace-relative path requested by the LLM tool loop.

        Returns:
            True when generic workspace mutation tools must not edit the path.
        """
        normalized = str(path or "").replace("\\", "/").strip().lstrip("./")
        return (
            normalized == "AGENT.json"
            or normalized == "MEMORY.md"
            or normalized.startswith("memory/")
            or normalized == "state/todos.json"
            or normalized.startswith("state/daily_guidance/")
        )

    def _normalize_workspace_read_path(self, path: str) -> str:
        """Map known agent-workspace absolute paths to this workspace.

        Args:
            path: Model-provided read path.

        Returns:
            Original relative path or a path relative to this agent workspace.
        """
        raw = str(path or "").strip()
        if not raw:
            return raw
        candidate = Path(raw)
        if not candidate.is_absolute():
            return raw
        parts = candidate.parts
        agent_dir = self.workspace_root_path().name
        for idx, part in enumerate(parts):
            if part == agent_dir:
                rel_parts = parts[idx + 1 :]
                if rel_parts:
                    return Path(*rel_parts).as_posix()
        return raw

    def _try_read_skill_path(self, path: str) -> tuple[str, str, str] | None:
        """Resolve an escaping read path to a visible skill file's content.

        Args:
            path: The path the model tried to read (absolute or relative).

        Returns:
            ``(skill_id, relative_path, content)`` if the path maps to a file
            inside a visible skill root, else ``None``.
        """
        resolved = self.skill_runtime.resolve_skill_path(path)
        if resolved is None:
            return None
        skill_id, rel_path = resolved
        content = self.skill_runtime.read_skill_file(skill_id, rel_path)
        if not content:
            return None
        return skill_id, rel_path, content

    def _build_env_tool_context(self, args: dict[str, Any]) -> dict[str, Any]:
        """Build ask_env context from tool arguments.

        Args:
            args: ask_env tool arguments.

        Returns:
            Context dictionary passed to RouterBase.ask.
        """
        raw_ctx = args.get("ctx")
        ctx = dict(raw_ctx) if isinstance(raw_ctx, Mapping) else {}
        raw_variables = args.get("variables")
        if isinstance(raw_variables, Mapping):
            current = ctx.get("variables")
            variables = dict(current) if isinstance(current, Mapping) else {}
            variables.update(dict(raw_variables))
            ctx["variables"] = variables
        return ctx

    def _build_env_skill_instruction(
        self,
        args: Mapping[str, Any],
        argv: list[str],
    ) -> str:
        """Build an ask_env instruction for env skill calls sent to script execution.

        Args:
            args: Original tool arguments.
            argv: Command-like arguments supplied by the model.

        Returns:
            Natural-language instruction for the environment router.
        """
        skill_name = str(args.get("skill_name") or "environment").strip()
        if argv:
            return (
                f"Use the {skill_name} environment skill to perform: {' '.join(argv)}"
            )
        return f"Use the {skill_name} environment skill for the current state."

    # ==================================================================
    # ReAct loop (generic orchestration)
    # ==================================================================
    #
    # The loop is generic: it builds messages via ``self.build_react_messages``
    # (a subclass-provided prompt hook), dispatches the LLM via
    # ``self._dispatcher.call``, executes tools via ``self._execute_react_tool``
    # (which calls ``self.dispatch_react_tool`` polymorphically), and respects
    # ``self._max_react_turns``.  Nothing person-specific is inlined here.

    async def run_react_loop(
        self,
        *,
        tick: int,
        t: datetime,
        observations: list[dict[str, Any]] | None = None,
        question: str | None = None,
        readonly: bool = False,
        skill_hooks: list[dict[str, Any]] | None = None,
    ) -> str:
        """Run the ReAct loop until finish or turn limit.

        Args:
            tick: Current simulation tick.
            t: Current simulation time.
            observations: Initial observation list (appended in-place).
            question: Optional external question (ask mode).
            readonly: Whether mutation tools are blocked.
            skill_hooks: Optional pre_step hook outputs for the prompt.

        Returns:
            Final result string from the loop.
        """
        if observations is None:
            observations = []
        # Reset inline finish memories for this loop invocation; set below when
        # a step-mode `finish` carrying `memories` is observed.
        self._last_finish_memories = None
        with self.trace_span(
            "react.loop",
            attributes={
                "agent.tick": tick,
                "operation.type": "react",
                "react.max_turns": self._max_react_turns,
                "react.readonly": readonly,
                "input.message_chars": len(question or ""),
            },
        ) as loop_span:
            for turn in range(1, self._max_react_turns + 1):
                with self.trace_span(
                    "react.turn",
                    attributes={
                        "agent.tick": tick,
                        "operation.type": "react",
                        "react.turn": turn,
                    },
                ) as turn_span:
                    decisions = await self._call_react_llm(
                        tick=tick,
                        t=t,
                        observations=observations,
                        question=question,
                        readonly=readonly,
                        skill_hooks=skill_hooks,
                    )
                    turn_span.attributes.update(
                        {
                            "react.action": ", ".join(d.action for d in decisions)
                            if decisions
                            else "(none)",
                            "react.tool_count": len(decisions),
                        }
                    )
                    if not decisions:
                        loop_span.attributes.update(
                            {
                                "react.end_reason": "finish",
                                "output.summary": {"final": "done"},
                            }
                        )
                        return "done"

                    finish_d = next(
                        (d for d in decisions if d.action == "finish"), None
                    )
                    if finish_d is not None:
                        # Capture memories the model recorded inline in the
                        # step-mode finish tool, so step() can ingest them
                        # without a separate extraction pass. Absent in ask mode
                        # (finish carries only `answer`) — stays None there.
                        self._last_finish_memories = finish_d.args.get("memories")
                        # Step-mode finish has no `final` text; derive a brief
                        # step result from the recorded memories so the trace /
                        # step summary stays meaningful (ask mode keeps its
                        # explicit `answer`).
                        final = (
                            finish_d.final
                            or _brief_memories_summary(self._last_finish_memories)
                            or finish_d.thought
                            or "done"
                        )
                        loop_span.attributes.update(
                            {
                                "react.end_reason": "finish",
                                "output.summary": {"final": final},
                            }
                        )
                        return final

                    for decision in decisions:
                        result = await self._execute_react_tool(
                            decision,
                            readonly=readonly,
                        )
                        if not result.ok:
                            logger.warning(
                                "Agent %s: ReAct tool failed: action=%s observation=%s",
                                self.id,
                                decision.action,
                                _short_text(result.observation, limit=300),
                            )
                        observations.append(
                            {
                                "turn": turn,
                                "action": decision.action,
                                "ok": result.ok,
                                "observation": result.observation,
                                "data": result.data,
                            }
                        )
                    turn_span.attributes["react.tool_ok"] = all(
                        obs["ok"] for obs in observations if obs.get("turn") == turn
                    )

            summary = "max_react_turns_reached"
            loop_span.attributes.update(
                {
                    "react.end_reason": summary,
                    "output.summary": {"turns": self._max_react_turns},
                }
            )
            return summary

    async def _call_react_llm(
        self,
        *,
        tick: int,
        t: datetime,
        observations: list[dict[str, Any]],
        question: str | None = None,
        readonly: bool = False,
        skill_hooks: list[dict[str, Any]] | None = None,
    ) -> list[ReactDecision]:
        """Call the LLM for the next ReAct decisions.

        Builds messages via the subclass ``build_react_messages`` hook, then
        dispatches to :meth:`_call_react_llm_with_messages`.

        Args:
            tick: Current simulation tick.
            t: Current simulation time.
            observations: Recent observation list.
            question: Optional external question (ask mode).
            readonly: Whether mutation tools are blocked.
            skill_hooks: Optional pre_step hook outputs for the prompt.

        Returns:
            Parsed ReAct decisions for this turn.
        """
        messages = self.build_react_messages(
            tick=tick,
            t=t,
            observations=observations,
            question=question,
            readonly=readonly,
            skill_hooks=skill_hooks,
        )
        return await self._call_react_llm_with_messages(messages, readonly=readonly)

    async def _call_react_llm_with_messages(
        self,
        messages: list[dict[str, str]],
        *,
        readonly: bool = False,
    ) -> list[ReactDecision]:
        """Call the LLM and retry once on invalid tool arguments.

        Args:
            messages: OpenAI-style chat messages.
            readonly: Whether mutation tools are blocked.

        Returns:
            Parsed ReAct decisions (possibly empty).
        """
        with self.trace_span(
            "llm.completion",
            attributes={
                "operation.type": "llm",
                "llm.model": self._model_name or "",
                "input.message_count": len(messages),
            },
        ) as span:
            response = await self._complete_react_once(messages, readonly=readonly)
            decisions, error = self._parse_react_responses(response)
            if error:
                retry_messages = [
                    *messages,
                    {
                        "role": "assistant",
                        "content": "Invalid tool call arguments.",
                    },
                    {
                        "role": "user",
                        "content": _xml_block(
                            "schema_error",
                            error + "\nCall valid tool(s) with valid arguments.",
                        ),
                    },
                ]
                span.attributes["llm.retry"] = True
                response = await self._complete_react_once(
                    retry_messages,
                    readonly=readonly,
                )
                decisions, error = self._parse_react_responses(response)
            if error:
                span.attributes["schema.error"] = error
                logger.warning("Agent %s: invalid ReAct decision: %s", self.id, error)
        return decisions

    async def _complete_react_once(
        self,
        messages: list[dict[str, str]],
        *,
        readonly: bool = False,
    ) -> Any:
        """Run one ReAct LLM completion.

        Args:
            messages: OpenAI-style chat messages.
            readonly: Whether mutation tools are blocked.

        Returns:
            Raw LLM response object.
        """
        assert self._model_name is not None, "LLM is not initialized"
        enable_skill_tools = self.skill_runtime.visible_skill_count() > 0
        response = await self._dispatcher.call(
            model=self._model_name,
            messages=messages,
            stream=False,
            tools=react_tool_schemas(
                enable_todo_list=self._enable_todo_list,
                enable_memory=self._enable_memory,
                disable_skills=not enable_skill_tools,
                readonly=readonly,
                overrides=self._react_tool_overrides(readonly=readonly),
            ),
            tool_choice="auto",
        )
        return response

    def _react_tool_overrides(self, *, readonly: bool) -> dict[str, dict[str, Any]]:
        """Per-agent ReAct tool-schema overrides, keyed by tool name.

        Subclass hook (default: no overrides). Applied by
        :meth:`_complete_react_once` before the readonly filter, so a subclass
        can replace a tool per mode — e.g. PersonAgent swaps ``finish`` for an
        answer-only variant in ask mode and a result+memories variant in step
        mode (the latter records memories inline, removing a separate extraction
        LLM call).

        :param readonly: Whether the loop is in readonly (ask) mode.
        :returns: ``{tool_name: full_tool_schema_dict}`` (empty by default).
        """
        return {}

    def _parse_react_responses(self, response: Any) -> tuple[list[ReactDecision], str]:
        """Parse OpenAI tool calls from one LLM response.

        Args:
            response: Raw LLM response object.

        Returns:
            Tuple of (decisions, error).  When ``error`` is non-empty the
            caller may retry once; ``decisions`` is empty on error.
        """
        if not getattr(response, "choices", None):
            return [], "missing response choices"
        message = getattr(response.choices[0], "message", None)
        if message is None:
            return [], "missing response message"
        tool_calls = getattr(message, "tool_calls", None) or []
        if not tool_calls:
            content = str(getattr(message, "content", "") or "").strip()
            if not content:
                return [], ""
            return [], "Respond with tool calls only. Free text is not accepted."

        decisions: list[ReactDecision] = []
        for tool_call in tool_calls:
            function = getattr(tool_call, "function", None)
            name = str(getattr(function, "name", "") or "").strip()
            raw_args = str(getattr(function, "arguments", "") or "{}")
            try:
                from agentsociety2.agent.json_utils import jr_parse_from_llm

                parsed_args = jr_parse_from_llm(raw_args)
            except Exception:
                try:
                    parsed_args = json.loads(raw_args)
                except Exception as exc:
                    return [], f"invalid tool arguments for {name}: {exc}"
            if not isinstance(parsed_args, Mapping):
                return [], f"tool arguments for {name} must be an object"
            args = dict(parsed_args)
            if name == "finish":
                final = (
                    str(args.get("answer") or "").strip()
                    or str(args.get("final") or "").strip()
                )
                # Step-mode finish carries only `memories` (no answer/final);
                # ask-mode finish carries `answer`. Reject only when neither is
                # present.
                if not final and "memories" not in args:
                    return (
                        [],
                        "finish requires `answer` (ask mode) or `memories` (step mode)",
                    )
                decisions.append(ReactDecision("", name, args, final))
            else:
                decisions.append(ReactDecision("", name, args, ""))

        finish_decisions = [d for d in decisions if d.action == "finish"]
        if finish_decisions:
            return finish_decisions[:1], ""
        return decisions, ""

    def build_react_messages(
        self,
        *,
        tick: int,
        t: datetime,
        observations: list[dict[str, Any]],
        question: str | None = None,
        readonly: bool = False,
        skill_hooks: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, str]]:
        """Build ReAct prompt messages (subclass prompt hook).

        The base implementation raises :class:`NotImplementedError`.
        Subclasses (e.g. PersonAgent) override this to assemble their
        agent-specific prompt and return OpenAI-style chat messages.

        Args:
            tick: Current simulation tick.
            t: Current simulation time.
            observations: Recent observation list.
            question: Optional external question (ask mode).
            readonly: Whether mutation tools are blocked.
            skill_hooks: Optional pre_step hook outputs for the prompt.

        Returns:
            OpenAI-style chat messages.

        Raises:
            NotImplementedError: Always, in the base class.
        """
        raise NotImplementedError(
            "Subclasses must implement build_react_messages to use the "
            "generic ReAct loop."
        )

    # ==================================================================
    # TODO handling (generic)
    # ==================================================================

    def _todo_store(self) -> TodoStateStore:
        """Return the TODO store for this agent workspace.

        Returns:
            TodoStateStore bound to the agent workspace root.
        """
        return TodoStateStore(self.workspace_root_path())

    def _ensure_todo_state(self) -> None:
        """Initialize TODO state when the feature gate is enabled."""
        if self._enable_todo_list:
            self._todo_store().ensure()

    def _build_todo_context(self, t: datetime) -> dict[str, Any]:
        """Build compact prompt context for TODO state.

        Args:
            t: Current simulation time.

        Returns:
            TODO prompt-context dict (empty when the feature is disabled).
        """
        if not self._enable_todo_list:
            return {}
        return self._todo_store().build_prompt_context(t)

    def _current_simulation_time(self) -> datetime | None:
        """Return the best known simulation time for tool normalization.

        Returns:
            Current simulation time, or ``None`` when unavailable.
        """
        if self._current_time is not None:
            return self._current_time
        if self._workspace_fs is None:
            return None
        try:
            data = json.loads(self._workspace.read_text(AGENT_JSON_PATH))
        except Exception:
            return None
        current_time = str(data.get("current_time") or "").strip()
        if not current_time:
            return None
        try:
            return datetime.fromisoformat(current_time)
        except ValueError:
            return None

    def _normalize_todo_due_value(self, value: Any) -> Any:
        """Normalize common TODO due shorthand before strict store validation.

        Args:
            value: Raw ``due`` value from the model.

        Returns:
            Normalized value (ISO string when a ``HH:MM`` shorthand was
            resolved against the current simulation time; otherwise the
            original value).
        """
        if value in (None, ""):
            return value
        text = str(value).strip()
        match = _SHORT_CLOCK_RE.match(text)
        if not match:
            return value
        current = self._current_simulation_time()
        if current is None:
            return value
        hour = int(match.group("hour"))
        minute = int(match.group("minute"))
        return current.replace(
            hour=hour, minute=minute, second=0, microsecond=0
        ).isoformat()

    def _normalize_todo_tool_args(
        self,
        action: str,
        args: dict[str, Any],
    ) -> dict[str, Any]:
        """Normalize TODO tool arguments at the agent boundary.

        Args:
            action: TODO tool action name.
            args: Tool argument dictionary.

        Returns:
            New argument dict with normalized ``due`` values.
        """
        normalized = dict(args)
        if action == "todo_add" and "due" in normalized:
            normalized["due"] = self._normalize_todo_due_value(normalized["due"])
        if action == "todo_update" and isinstance(normalized.get("patch"), Mapping):
            patch = dict(normalized["patch"])
            if "due" in patch:
                patch["due"] = self._normalize_todo_due_value(patch["due"])
            normalized["patch"] = patch
        if action == "todo_defer" and "new_due" in normalized:
            normalized["new_due"] = self._normalize_todo_due_value(
                normalized["new_due"]
            )
        return normalized

    def dispatch_todo_tool(
        self,
        action: str,
        args: dict[str, Any],
    ) -> ReactToolResult:
        """Dispatch built-in TODO tools.

        Args:
            action: TODO tool action name.
            args: Tool argument dictionary.

        Returns:
            Tool execution result.
        """
        if not self._enable_todo_list:
            return ReactToolResult(
                False,
                "todo_list feature is disabled",
                {"error": "todo_list feature is disabled"},
            )
        args = self._normalize_todo_tool_args(action, args)
        store = self._todo_store()
        if action == "todo_list":
            limit_raw = args.get("limit")
            limit = int(limit_raw) if limit_raw is not None else None
            data = store.list(
                status=str(args.get("status") or "").strip() or None,
                limit=limit,
            )
            return ReactToolResult(True, dump_json(data, indent=2), data)
        if action == "todo_add":
            data = store.add(dict(args))
            return ReactToolResult(True, dump_json(data["todo"], indent=2), data)
        if action == "todo_update":
            patch = args.get("patch")
            data = store.update(
                str(args.get("todo_id") or ""),
                dict(patch) if isinstance(patch, Mapping) else {},
            )
            return ReactToolResult(True, dump_json(data["todo"], indent=2), data)
        if action == "todo_start":
            data = store.start(str(args.get("todo_id") or ""))
            return ReactToolResult(True, dump_json(data["todo"], indent=2), data)
        if action == "todo_complete":
            data = store.complete(
                str(args.get("todo_id") or ""),
                outcome=str(args.get("outcome") or ""),
            )
            return ReactToolResult(True, dump_json(data["todo"], indent=2), data)
        if action == "todo_defer":
            data = store.defer(
                str(args.get("todo_id") or ""),
                new_due=str(args["new_due"])
                if args.get("new_due") not in (None, "")
                else None,
                reason=str(args.get("reason") or ""),
            )
            return ReactToolResult(True, dump_json(data["todo"], indent=2), data)
        if action == "todo_clear_completed":
            keep_raw = args.get("keep_recent")
            keep_recent = int(keep_raw) if keep_raw is not None else 2
            data = store.clear_completed(keep_recent=keep_recent)
            summary = {
                "archived": data["archived"],
                "kept_terminal": data["kept_terminal"],
                "remaining": data["remaining"],
            }
            return ReactToolResult(True, dump_json(summary, indent=2), data)
        return ReactToolResult(False, f"unknown action: {action}", {"action": action})
