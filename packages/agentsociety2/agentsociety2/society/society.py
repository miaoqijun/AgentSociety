"""仿真社会编排模块（record-based，无 agent 对象常驻）。

:class:`AgentSociety` 不再持有 agent 对象——agent 是磁盘上的记录，每 tick 通过
Ray Task（:mod:`agentsociety2.agent.runner`）流式处理。这使得内存占用与总 agent 数 N
解耦：driver 只持有 specs（元数据）+ ids + 句柄（env / service_proxy），并行度来自
"大量 Ray Task"而非"主进程内的 N 个对象"。

主要功能：

- **仿真初始化**: 初始化 Ray / LLM dispatcher、service_proxy（已注入则复用）、批式创建 agent
  workspaces（不在主进程实例化 agent）、初始化环境路由器、可选回放写入 agent profile。
- **时间推进**: 通过 ``step()``/``run()`` 每 tick 切批提交 ``step_agent_batch`` Ray Task，
  ``await`` 全部后再推进 env、前进时钟。
- **交互接口**: ``ask()``/``intervene()``/``run_questionnaire()`` 为低频外部查询，在主进程
  内按需 ``from_workspace`` 重建目标 agent（workspace 在本地磁盘，无需 Ray Task）。
- **状态持久化**: ``dump()`` 读各 workspace 的 ``AGENT.json``（轻量），``load()`` 恢复
  society 时间 + env_router（agent 状态已落盘，下次 ``from_workspace`` 即可重建）。
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

from agentsociety2.agent.runner import (
    create_agents_batch,
    questionnaire_agent_batch,
    step_agent_batch,
)
from agentsociety2.env import RouterBase
from agentsociety2.society.helper import AgentSocietyHelper
from agentsociety2.society.questionnaire import (
    AgentQuestionnaireResult,
    Questionnaire,
    QuestionnaireResponse,
)
from agentsociety2.storage import (
    ColumnDef,
    ReplayDatasetSpec,
    TableSchema,
)
from agentsociety2.storage.replay_metadata import (
    AGENT_PROFILE_DATASET_CAPABILITY,
    AGENT_PROFILE_DATASET_ID,
    AGENT_PROFILE_TABLE_NAME,
)
from agentsociety2.logger import get_logger

if TYPE_CHECKING:
    from agentsociety2.agent.base import AgentBase
    from agentsociety2.agent.service_proxy import ServiceProxy

__all__ = ["AgentSociety"]

logger = get_logger()


def _json_safe_profile(profile: Any) -> dict[str, Any]:
    """Convert an arbitrary profile payload into a JSON-safe dict."""
    if not isinstance(profile, dict):
        profile = {"raw": str(profile)}
    try:
        return json.loads(json.dumps(profile, ensure_ascii=False, default=str))
    except Exception:
        return {"raw": str(profile)}


def _chunked(lst: list, n: int):
    """Yield successive chunks of size ``n`` from ``lst``."""
    if n <= 0:
        n = 1
    for i in range(0, len(lst), n):
        yield lst[i : i + n]


def _agent_name_from_spec(spec: dict) -> str:
    """Derive a display name from an agent spec (no reconstruction needed)."""
    profile = spec.get("profile") or {}
    if isinstance(profile, dict):
        name = profile.get("name")
        if isinstance(name, str) and name:
            return name
    return f"Agent_{spec.get('id')}"


class AgentSociety:
    """Record-based 仿真编排器（不持有 agent 对象）。

    AgentSociety 是框架的核心类，负责管理仿真生命周期：

    - 持有 **agent_specs**（元数据：``{"id","profile","config"}``）与 **agent_ids**，
      绝不在主进程常驻 agent 对象。
    - ``step`` 每 tick 切批提交 ``step_agent_batch`` Ray Task，跨 worker 并行；批内顺序执行
      （每个 agent 是 LLM-bound，顺序无妨）。
    - ``ask``/``intervene``/``run_questionnaire``/``dump`` 为低频外部查询，按需在主进程
      ``from_workspace`` 重建目标 agent（workspace 在本地磁盘）。

    Example::

        from datetime import datetime
        from pathlib import Path
        from agentsociety2.society import AgentSociety

        society = AgentSociety(
            agent_specs=[{"id":1,"profile":{...},"config":{...}}, ...],
            agent_class_name="PersonAgent",
            env_router=env_proxy,
            service_proxy=proxy,
            start_t=datetime.now(),
            run_dir=Path("./run"),
            batch_size=256,
        )

        async with society:
            await society.run(num_steps=100, tick=3600)
    """

    def __init__(
        self,
        agent_specs: list[dict],
        agent_class_name: str,
        env_router: RouterBase,
        start_t: datetime,
        run_dir: Optional[Path] = None,
        *,
        service_proxy: Optional["ServiceProxy"] = None,
        batch_size: int = 256,
        enable_replay: bool = True,
    ):
        """创建 record-based 仿真编排器。

        :param agent_specs: agent 元数据列表，每个形如
            ``{"id": int, "profile": dict, "config": dict}``。仅元数据，不在构造时实例化。
        :param agent_class_name: agent 类名（经 registry 解析，如 ``"PersonAgent"``）。
        :param env_router: 环境路由器（in-process 或 ``EnvRouterProxy``）。
        :param start_t: 仿真开始时间。
        :param run_dir: 运行目录（``run_dir/agents`` 为 agent workspaces 根）。
        :param service_proxy: 共享服务句柄（env / llm / trace / replay）。流式任务
            处理必需——runner 任务通过它访问 LLM clients / env actor。提供时 :meth:`init`
            直接复用；``close`` 关闭其中 trace/replay actor。
        :param batch_size: 每 ``step_agent_batch`` Ray Task 处理的 agent 数（默认 256）。
        :param enable_replay: 是否启用回放记录。
        """
        self._agent_specs: list[dict] = list(agent_specs)
        self._agent_class_name: str = agent_class_name
        self._agent_ids: list[int] = [int(s["id"]) for s in self._agent_specs]

        self._env_router = env_router
        self._t = start_t
        self._should_terminate: bool = False
        self._step_count: int = 0

        # Resolve to ABSOLUTE paths. Ray worker processes may run with a cwd
        # inside an uploaded runtime-env package (/tmp/ray/.../_ray_pkg_.../),
        # not the driver's cwd — so a relative run_dir would resolve to a
        # phantom path inside the package and agent workspaces would never land
        # where the driver (and replay/trace) expect them.
        self._run_dir = Path(run_dir).resolve() if run_dir is not None else None
        self._workspace_root: Path = (
            (self._run_dir / "agents").resolve()
            if self._run_dir is not None
            else Path("./agents").resolve()
        )
        self._batch_size = max(1, int(batch_size))
        self._enable_replay = enable_replay

        self._service_proxy: Optional["ServiceProxy"] = service_proxy
        self._owns_service_proxy = service_proxy is not None

        self._replay_writer: Any = None
        self._agent_profiles_persisted = False
        self._agents_created = False
        # Aggregate LLM token usage across all Ray Task batches (instance-level,
        # not module-global). Each batch returns a per-task delta.
        self._token_stats: dict[str, dict[str, int]] = {}

        # Helper is built lazily on first ask/intervene (it reconstructs agents on demand).
        self._helper: Optional[AgentSocietyHelper] = None

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------
    @property
    def current_time(self) -> datetime:
        """返回当前仿真时间。"""
        return self._t

    @property
    def step_count(self) -> int:
        """返回已执行的仿真步数。"""
        return self._step_count

    @property
    def agent_ids(self) -> list[int]:
        """返回所有 agent id（不暴露 agent 对象）。"""
        return list(self._agent_ids)

    @property
    def agent_specs(self) -> list[dict]:
        """返回 agent specs（元数据快照）。"""
        return list(self._agent_specs)

    # ------------------------------------------------------------------
    # Replay: agent profile persistence (record-based)
    # ------------------------------------------------------------------
    async def _persist_agent_profiles_once(self) -> None:
        if self._replay_writer is None or self._agent_profiles_persisted:
            return

        columns = [
            ColumnDef(
                "id",
                "INTEGER",
                nullable=False,
                logical_type="entity_id",
                description="Unique agent identifier.",
            ),
            ColumnDef(
                "name",
                "TEXT",
                nullable=False,
                logical_type="label",
                description="Agent display name.",
            ),
            ColumnDef(
                "profile",
                "JSON",
                nullable=False,
                logical_type="json",
                description="Static agent profile payload captured at simulation init.",
            ),
            ColumnDef(
                "created_at",
                "TIMESTAMP",
                nullable=False,
                logical_type="timestamp",
                description="When the agent profile snapshot was persisted.",
            ),
        ]
        await self._replay_writer.register_table(
            TableSchema(
                name=AGENT_PROFILE_TABLE_NAME,
                columns=columns,
                primary_key=["id"],
                indexes=[["name"]],
            )
        )
        await self._replay_writer.register_dataset(
            ReplayDatasetSpec(
                dataset_id=AGENT_PROFILE_DATASET_ID,
                table_name=AGENT_PROFILE_TABLE_NAME,
                module_name="AgentSociety",
                kind="entity_static",
                title="Agent Profiles",
                description="Static agent profiles persisted once when the simulation initializes.",
                entity_key="id",
                default_order=["id"],
                capabilities=[AGENT_PROFILE_DATASET_CAPABILITY, "entity_static"],
            ),
            columns,
        )

        rows = [
            {
                "id": int(spec["id"]),
                "name": _agent_name_from_spec(spec),
                "profile": _json_safe_profile(spec.get("profile", {})),
                "created_at": self._t,
            }
            for spec in self._agent_specs
        ]
        if rows:
            await self._replay_writer.write_batch(AGENT_PROFILE_TABLE_NAME, rows)
        self._agent_profiles_persisted = True

    # ------------------------------------------------------------------
    # Workspace helpers
    # ------------------------------------------------------------------
    def _workspace_for(self, agent_id: int) -> Path:
        """Return ``<workspace_root>/agent_<id:04d>``."""
        return self._workspace_root / f"agent_{int(agent_id):04d}"

    async def _create_agent_workspaces(self) -> None:
        """Batch-create agent workspaces via ``create_agents_batch`` Ray Tasks.

        Agents are NOT instantiated in the society process — each task writes
        ``config.json`` + initial ``AGENT.json`` for its chunk of specs.
        """
        if self._agents_created or not self._agent_specs:
            self._agents_created = True
            return

        refs = []
        for chunk in _chunked(self._agent_specs, self._batch_size):
            refs.append(
                create_agents_batch.remote(
                    chunk,
                    str(self._workspace_root),
                    self._agent_class_name,
                )
            )
        if refs:
            await asyncio.gather(*[self._await_ref(r) for r in refs])
        self._agents_created = True

    async def _resolve_service_proxy(self) -> "ServiceProxy":
        """Return the bound service proxy, building one if none injected."""
        if self._service_proxy is not None:
            return self._service_proxy
        from agentsociety2.agent.service_proxy import build_service_proxy

        proxy = build_service_proxy(
            self._env_router,
            run_dir=self._run_dir,
            trace=False,
            replay=bool(self._enable_replay and self._run_dir is not None),
        )
        self._service_proxy = proxy
        self._owns_service_proxy = True
        return proxy

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    async def init(self):
        """初始化：Ray / LLM dispatcher → service_proxy → replay → 批式创建 workspaces → env init。"""
        # Initializes Ray and per-process LLM dispatch support (idempotent).
        from agentsociety2.config.llm_dispatcher import init_dispatchers

        await init_dispatchers()

        proxy = await self._resolve_service_proxy()

        # Replay: the single proxy.replay handle (a the distributed ReplayProxy proxy).
        self._replay_writer = getattr(proxy, "replay", None)
        if self._replay_writer is not None:
            await self._persist_agent_profiles_once()
            try:
                self._env_router.set_replay_writer(self._replay_writer)
            except Exception:
                pass

        # Ensure workspace_root exists before tasks write into it.
        self._workspace_root.mkdir(parents=True, exist_ok=True)

        # Batch-create agent workspaces (no agent objects in this process).
        await self._create_agent_workspaces()

        await self._env_router.init(self._t)

    async def close(self):
        """关闭：env router + service_proxy 的 trace/replay 句柄 + LLM dispatcher。"""
        try:
            await self._env_router.close()
        except Exception:
            pass

        # Close the proxy's replay actor (if we own the proxy). Trace needs no
        # central close: it is distributed — each writer process appends
        # directly and its fds are reclaimed on process exit.
        if self._owns_service_proxy and self._service_proxy is not None:
            replay = getattr(self._service_proxy, "replay", None)
            if replay is not None and hasattr(replay, "close"):
                try:
                    await replay.close()
                except Exception:
                    pass

        # LLM shutdown is currently a no-op; local Routers die with the process.
        from agentsociety2.config.llm_dispatcher import shutdown_dispatchers

        await shutdown_dispatchers()

    async def __aenter__(self):
        await self.init()
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        await self.close()

    # ------------------------------------------------------------------
    # Step / Run — the hot path (no agent objects held)
    # ------------------------------------------------------------------
    async def step(self, tick: int):
        """推进一次仿真步：sync clock → 切批 step_agent_batch → env.step → 前进时钟。

        :param tick: 本步时间跨度（秒）。
        """
        if not self._agent_ids:
            # Still advance env + clock for an empty society.
            self._env_router.set_current_time(self._t)
            await self._env_router.step(tick, self._t)
            self._t += timedelta(seconds=tick)
            self._step_count += 1
            return

        proxy = await self._resolve_service_proxy()

        # Push the clock to env BEFORE fan-out so all batches share the same
        # time context (env modules read it during agent tool calls).
        self._env_router.set_current_time(self._t)

        # Chunk ids and submit one Ray Task per chunk.
        refs = []
        for ids in _chunked(self._agent_ids, self._batch_size):
            refs.append(
                step_agent_batch.remote(
                    ids,
                    str(self._workspace_root),
                    self._agent_class_name,
                    tick,
                    self._t,
                    proxy,
                )
            )
        # Await all batches. Each batch returns {"results", "token_stats"};
        # fold the per-task token-usage deltas into this society's instance
        # aggregate (no module-global state).
        if refs:
            from agentsociety2.config.llm_dispatcher import merge_token_stats

            batch_returns = await asyncio.gather(
                *[self._await_ref(r) for r in refs]
            )
            for br in batch_returns:
                if isinstance(br, dict) and br.get("token_stats"):
                    self._token_stats = merge_token_stats(
                        self._token_stats, br["token_stats"]
                    )

        # Env advances AFTER agents.
        await self._env_router.step(tick, self._t)
        self._t += timedelta(seconds=tick)
        self._step_count += 1

    async def run(self, num_steps: int, tick: int):
        """运行多步仿真。

        :param num_steps: 运行步数上限。
        :param tick: 每步时间跨度（秒）。
        """
        for _ in range(num_steps):
            if self._should_terminate:
                break
            await self.step(tick)

    @staticmethod
    async def _await_ref(ref: Any) -> Any:
        """Await a Ray ObjectRef (Ray >=2 supports ``await ref`` in an asyncio loop)."""
        return await ref

    # ------------------------------------------------------------------
    # Queries — low-volume, reconstruct target agents locally
    # ------------------------------------------------------------------
    async def _reconstruct_agent(self, agent_id: int) -> "AgentBase":
        """Reconstruct a single agent in the society process via from_workspace.

        Used by ask/intervene/questionnaire (low-volume external queries). The
        workspace lives on local disk, so no Ray Task is needed.
        """
        from agentsociety2.registry import get_agent_module_class

        cls = get_agent_module_class(self._agent_class_name)
        if cls is None:
            try:
                from agentsociety2 import agent as _agent_mod

                cls = getattr(_agent_mod, self._agent_class_name, None)
            except Exception:
                cls = None
        if cls is None:
            raise ValueError(
                f"Agent class '{self._agent_class_name}' not found in registry."
            )
        proxy = await self._resolve_service_proxy()
        ws = self._workspace_for(int(agent_id))
        return await cls.from_workspace(ws, proxy)

    async def _reconstruct_agents(self, agent_ids: list[int]) -> list["AgentBase"]:
        """Reconstruct a subset of agents (parallel from_workspace calls)."""
        coros = [self._reconstruct_agent(int(aid)) for aid in agent_ids]
        return list(await asyncio.gather(*coros))

    def _get_helper(self) -> AgentSocietyHelper:
        """Lazily build the plan-and-execute helper bound to this society.

        The helper receives the society handle (specs/ids + reconstruction
        callbacks) instead of a pre-built agent list, so it can reconstruct
        only the agents a specific plan needs.
        """
        if self._helper is None:
            self._helper = AgentSocietyHelper(
                env_router=self._env_router,
                society=self,
            )
        return self._helper

    async def ask(self, question: str) -> str:
        """向仿真系统提问（由 helper 协调 agents/env 作答）。

        :param question: 问题文本。
        :returns: 答案文本。
        """
        return await self._get_helper().ask(question)

    async def intervene(self, instruction: str) -> str:
        """对仿真进行干预（由 helper 协调执行）。

        :param instruction: 干预指令文本。
        :returns: 执行结果/反馈文本。
        """
        return await self._get_helper().intervene(instruction)

    async def run_questionnaire(
        self,
        questionnaire: Questionnaire,
        target_agent_ids: list[int] | None = None,
    ) -> QuestionnaireResponse:
        """向目标 agents 发放问卷并返回结构化结果。

        目标 agent 按 id 切批，每批提交一个 ``questionnaire_agent_batch`` Ray Task
        （与 ``step`` 同款分布式批处理）：worker 进程内 ``from_workspace`` 重建本批
        agents、并发跑完整个问卷、``to_workspace`` 落盘，再返回结构化结果。失败的单个
        agent 被隔离（不中断整批），与 ``step_agent_batch`` 的容错语义一致。

        :param questionnaire: 问卷定义。
        :param target_agent_ids: 目标 agent id（默认全部）。
        :returns: 汇总后的问卷响应。
        """
        ids = (
            list(target_agent_ids)
            if target_agent_ids is not None
            else list(self._agent_ids)
        )
        # Validate ids against known specs.
        known = set(self._agent_ids)
        missing = [i for i in ids if int(i) not in known]
        if missing:
            raise ValueError(f"Unknown target_agent_ids: {missing}")

        ordered_ids = [int(i) for i in ids]

        if not ordered_ids:
            return QuestionnaireResponse(
                questionnaire_id=questionnaire.questionnaire_id,
                title=questionnaire.title,
                description=questionnaire.description,
                simulation_time=self._t.isoformat(),
                step_count=self._step_count,
                target_agent_ids=ordered_ids,
                questions=questionnaire.questions,
                responses=[],
            )

        proxy = await self._resolve_service_proxy()

        # Chunk ids and submit one Ray Task per chunk — same fan-out as step().
        refs = []
        for chunk in _chunked(ordered_ids, self._batch_size):
            refs.append(
                questionnaire_agent_batch.remote(
                    chunk,
                    str(self._workspace_root),
                    self._agent_class_name,
                    questionnaire,
                    self._t,
                    self._step_count,
                    proxy,
                )
            )

        from agentsociety2.config.llm_dispatcher import merge_token_stats

        batch_returns = await asyncio.gather(
            *[self._await_ref(r) for r in refs]
        )

        # Merge per-agent results across batches; aggregate token deltas.
        results_by_id: dict[int, dict] = {}
        failed: list[tuple[int, str]] = []
        for br in batch_returns:
            if isinstance(br, dict) and br.get("token_stats"):
                self._token_stats = merge_token_stats(
                    self._token_stats, br["token_stats"]
                )
            for r in br.get("results", []):
                results_by_id[int(r["id"])] = r
                if not r.get("ok"):
                    failed.append((int(r["id"]), str(r.get("error"))))

        responses: list[AgentQuestionnaireResult] = []
        for aid in ordered_ids:
            r = results_by_id.get(aid)
            if r is not None and r.get("ok") and r.get("result") is not None:
                responses.append(
                    AgentQuestionnaireResult.model_validate(r["result"])
                )

        if failed:
            logger.warning(
                "Questionnaire %s: %d/%d agents failed (skipped): %s",
                questionnaire.questionnaire_id,
                len(failed),
                len(ordered_ids),
                failed[:5],
            )

        return QuestionnaireResponse(
            questionnaire_id=questionnaire.questionnaire_id,
            title=questionnaire.title,
            description=questionnaire.description,
            simulation_time=self._t.isoformat(),
            step_count=self._step_count,
            target_agent_ids=ordered_ids,
            questions=questionnaire.questions,
            responses=responses,
        )
