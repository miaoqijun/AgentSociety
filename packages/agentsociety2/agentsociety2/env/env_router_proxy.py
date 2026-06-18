"""Ray-only proxy for the env router.

Society, agents, and helpers talk to this proxy exactly as they talk to the
in-process ``CodeGenRouter`` (same method names: ``ask``, ``init``, ``step``,
``close``, ``dump``, ``load``, ``set_current_time``, ``set_replay_writer``).
The proxy forwards each call to a Ray actor that owns the real router in a
separate process, so env codegen execution (and its former ``_execute_lock``
serialization) no longer blocks the agent event loop.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any


class EnvRouterProxy:
    """Agent/society-facing handle delegating to a Ray env-router actor."""

    def __init__(self, actor_handle: Any, *, run_dir: Any = None) -> None:
        self._actor = actor_handle
        self.run_dir = run_dir

    def set_current_time(self, t: datetime) -> None:
        """Forward the society clock to the actor (fire-and-forget).

        See :meth:`RouterBase.set_current_time` — this pushes the society's
        current time so env modules observe it during the agent phase.
        """
        self._actor.set_current_time.remote(t)

    def set_replay_writer(self, writer: Any) -> None:
        """Forward a replay writer/proxy to the actor (fire-and-forget).

        The env actor normally receives its replay proxy at construction (so env
        modules and agents share the same replay directory). This method lets a
        caller additionally/alternatively inject a writer after construction; it
        is forwarded to the actor via ``set_replay_writer``. A ``ReplayProxy`` is
        serializable, so it travels across the Ray boundary cleanly.
        """
        self._actor.set_replay_writer.remote(writer)

    async def ask(
        self,
        ctx: dict,
        instruction: str,
        readonly: bool = False,
        template_mode: bool = False,
        trace_id: str | None = None,
        parent_span_id: str | None = None,
    ):
        """Forward an env ask to the actor and await the (ctx, answer) result."""
        return await self._actor.ask.remote(
            ctx, instruction, readonly, template_mode, trace_id, parent_span_id
        )

    async def get_world_description(self) -> str:
        return await self._actor.get_world_description.remote()

    async def init(self, start_datetime: datetime) -> None:
        return await self._actor.init.remote(start_datetime)

    async def step(self, tick: int, t: datetime) -> None:
        return await self._actor.step.remote(tick, t)

    async def close(self) -> None:
        return await self._actor.close.remote()
