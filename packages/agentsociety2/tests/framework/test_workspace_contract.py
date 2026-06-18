"""Phase 0 workspace-contract tests for :class:`AgentBase` / :class:`PersonAgent`.

Two layers:

- ``test_workspace_roundtrip_unit`` — hermetic, no LLM, no ``step``. Validates that
  ``create`` → ``from_workspace`` → ``to_workspace`` → fresh ``from_workspace``
  faithfully restores profile / config / skills / counters. Runs in CI without creds.
- ``test_workspace_roundtrip_real_step`` — integration: a real LLM ``step`` between
  two ``from_workspace`` instances, proving cross-instance (≈ new-process) state
  continuity. Skipped unless real LLM credentials are present.
"""

from __future__ import annotations

import os
import types
from datetime import datetime
from pathlib import Path

import pytest

from agentsociety2.agent.person import PersonAgent

PROFILE = {
    "id": 1,
    "name": "Alice",
    "age": 28,
    "personality": "friendly, curious, and optimistic",
    "bio": "A software engineer who loves hiking, reading sci-fi, and cooking.",
    "location": "San Francisco",
}
CONFIG = {"max_react_turns": 3, "enable_memory": True, "enable_todo_list": True}


class _StubLLM:
    model_name = "stub-default-model"


def _stub_proxy(run_dir: Path):
    """Minimal ServiceProxy for hermetic tests (no LLM/env calls)."""
    default = _StubLLM()
    return types.SimpleNamespace(
        env=None,
        llm=types.SimpleNamespace(coder=default, default=default, embedding=None),
        trace=None,
        replay=None,
        run_dir=run_dir,
    )


def _real_llm_configured() -> bool:
    key = os.environ.get("AGENTSOCIETY_LLM_API_KEY", "")
    return bool(key.strip()) and key.strip() != "test-key"


async def test_workspace_roundtrip_unit(tmp_path):
    """create → from → to → fresh from restores all state (no step, no LLM)."""
    run_dir = tmp_path / "run"
    ws = run_dir / "agents" / "agent_0001"
    proxy = _stub_proxy(run_dir)

    # create writes config.json + AGENT.json + state/ + memory/
    PersonAgent.create(ws, PROFILE, CONFIG)
    assert (ws / "config.json").exists()
    assert (ws / "AGENT.json").exists()

    # first load
    a1 = await PersonAgent.from_workspace(ws, proxy)
    assert a1.id == 1
    assert a1.name == "Alice"
    assert a1._step_count == 0
    assert a1._max_react_turns == 3  # config restored
    assert a1.get_profile()["location"] == "San Francisco"

    # simulate work: mutate dynamic state, persist
    a1._step_count = 5
    a1._current_time = datetime(2026, 6, 16, 12, 0, 0)
    a1._initialized_at = "2026-06-16T08:00:00"
    await a1.to_workspace(ws)

    # FRESH instance (≈ new process) must restore persisted dynamic state
    a2 = await PersonAgent.from_workspace(ws, proxy)
    assert a2._step_count == 5, "step_count not restored across instances"
    assert a2._current_time == datetime(2026, 6, 16, 12, 0, 0)
    assert a2._initialized_at == "2026-06-16T08:00:00"
    assert a2.name == "Alice"
    assert a2._max_react_turns == 3  # config still intact (write-once)


@pytest.mark.skipif(not _real_llm_configured(), reason="needs real LLM credentials")
async def test_workspace_roundtrip_real_step(tmp_path):
    """Real LLM step across two from_workspace instances — cross-process continuity."""
    from agentsociety2.env import CodeGenRouter
    from agentsociety2.contrib.env import SimpleSocialSpace
    from agentsociety2.agent.service_proxy import build_service_proxy

    run_dir = tmp_path / "run"
    ws = run_dir / "agents" / "agent_0001"

    PersonAgent.create(ws, PROFILE, CONFIG)

    env_router = CodeGenRouter(
        env_modules=[SimpleSocialSpace(agent_id_name_pairs=[(1, "Alice")])]
    )
    env_router.run_dir = run_dir
    await env_router.init(datetime(2026, 6, 16, 8, 0, 0))
    proxy = build_service_proxy(env_router, run_dir=run_dir, trace=False, replay=False)

    try:
        # instance #1: step then persist
        a1 = await PersonAgent.from_workspace(ws, proxy)
        await a1.step(3600, datetime(2026, 6, 16, 8, 0, 0))
        await a1.to_workspace(ws)
        sc1 = a1._step_count
        assert sc1 >= 1

        # FRESH instance must restore step_count, then step again
        a2 = await PersonAgent.from_workspace(ws, proxy)
        assert a2._step_count == sc1, "step_count not restored across instances"
        await a2.step(3600, datetime(2026, 6, 16, 9, 0, 0))
        await a2.to_workspace(ws)

        # third load verifies step 2 persisted
        a3 = await PersonAgent.from_workspace(ws, proxy)
        assert a3._step_count == 2, f"expected 2, got {a3._step_count}"
    finally:
        await env_router.close()
