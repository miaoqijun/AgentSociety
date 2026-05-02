from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from agentsociety2.agent.base import AgentBase
from agentsociety2.env import EnvBase, ReActRouter, tool
from agentsociety2.society.society import AgentSociety


class _EmptyEnv(EnvBase):
    @tool(readonly=True, kind="observe")
    def observe_state(self, agent_id: int) -> str:
        return "ok"

    async def step(self, tick: int, t: datetime) -> None:
        self.t = t


class _StubAgent(AgentBase):
    async def ask(self, message: str, readonly: bool = True) -> str:
        return "ok"

    async def step(self, tick: int, t: datetime) -> str:
        return "step"

    async def dump(self) -> dict:
        return {"id": self.id}

    async def load(self, dump_data: dict) -> None:
        return None


@pytest.fixture
def mock_llm_routers():
    fake = MagicMock()
    with (
        patch(
            "agentsociety2.env.router_base.get_llm_router_and_model",
            return_value=(fake, "fake-model"),
        ),
        patch(
            "agentsociety2.agent.base.get_llm_router_and_model",
            return_value=(fake, "fake-model"),
        ),
    ):
        yield


@pytest.mark.asyncio
async def test_society_context_manager_replay_and_step(tmp_path, mock_llm_routers):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    start = datetime(2024, 1, 1, 12, 0, 0)
    router = ReActRouter(env_modules=[_EmptyEnv()])
    agent = _StubAgent(1, {"name": "unit"})
    society = AgentSociety(
        agents=[agent],
        env_router=router,
        start_t=start,
        run_dir=run_dir,
        enable_replay=True,
    )
    async with society:
        assert society.step_count == 0
        await society.step(60)
        assert society.step_count == 1
    db_file = run_dir / "sqlite.db"
    assert db_file.is_file()
