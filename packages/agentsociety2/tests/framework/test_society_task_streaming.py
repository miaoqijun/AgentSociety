"""Phase 2 integration test: record-based ``AgentSociety`` streams agents via Ray Tasks.

Builds an :class:`AgentSociety` with 3 agents (specs only — no agent objects in the
driver), wired to a real Ray env-router actor + an actor-backed ``ServiceProxy``.
Runs 2 steps via the task-streaming ``step()`` (``step_agent_batch`` Ray Tasks) and
asserts:

- (a) all 3 agents' ``AGENT.json`` show ``step_count == 2`` afterward (state
  continuity across processes — each task reconstructs via ``from_workspace``),
- (b) ``AgentSociety`` holds NO agent objects (no ``_agents`` attribute holding
  instances; only specs/ids),
- (c) the env advanced (society ``step_count`` == 2 and time moved forward).

Skipped unless real LLM credentials are present (mirrors
``test_workspace_contract.py`` gating). Ray starts locally; ~2-4 min for 3 agents
× 2 steps.
"""

from __future__ import annotations

import json
import os
from datetime import datetime

import pytest

from agentsociety2.agent.service_proxy import build_service_proxy
from agentsociety2.config import Config
from agentsociety2.env.env_router_actor import get_env_router_actor_class
from agentsociety2.env.env_router_proxy import EnvRouterProxy
from agentsociety2.registry import (
    discover_and_register_builtin_modules,
)
from agentsociety2.society.society import AgentSociety


def _real_llm_configured() -> bool:
    key = os.environ.get("AGENTSOCIETY_LLM_API_KEY", "")
    return bool(key.strip()) and key.strip() != "test-key"


pytestmark = pytest.mark.skipif(
    not _real_llm_configured(), reason="needs real LLM credentials"
)


def _build_specs(n: int = 3) -> list[dict]:
    """Build 3 PersonAgent specs with distinct profiles + a low max_react_turns."""
    profiles = [
        {
            "name": "Alice",
            "age": 28,
            "personality": "friendly, curious, and optimistic",
            "bio": "A software engineer who loves hiking, reading sci-fi, and cooking.",
            "location": "San Francisco",
        },
        {
            "name": "Bob",
            "age": 35,
            "personality": "calm, methodical, and dependable",
            "bio": "A teacher who enjoys chess, gardening, and classical music.",
            "location": "Oakland",
        },
        {
            "name": "Carol",
            "age": 42,
            "personality": "energetic, sociable, and creative",
            "bio": "A graphic designer who paints, cycles, and hosts dinner parties.",
            "location": "Berkeley",
        },
    ]
    specs = []
    for i in range(n):
        p = dict(profiles[i])
        p["id"] = i + 1
        specs.append(
            {
                "id": i + 1,
                "profile": p,
                "config": {
                    "max_react_turns": 3,
                    "enable_memory": True,
                    "enable_todo_list": True,
                },
            }
        )
    return specs


async def test_society_task_streaming(tmp_path):
    """3 agents × 2 steps via Ray Tasks — asserts record-based + state continuity."""
    # Ensure builtin modules (PersonAgent, SimpleSocialSpace) are registered.
    discover_and_register_builtin_modules()

    run_dir = tmp_path / "run"
    run_dir.mkdir(parents=True, exist_ok=True)

    specs = _build_specs(3)
    agent_ids = [s["id"] for s in specs]
    pairs = [(s["id"], s["profile"]["name"]) for s in specs]

    # Init the shared LLM pool (idempotent) — required before build_service_proxy.
    from agentsociety2.config.llm_dispatcher import init_dispatchers

    await init_dispatchers()

    # Build the env router actor (CodeGenRouter over SimpleSocialSpace).
    from agentsociety2.config import get_dispatcher

    env_module_types = ["SimpleSocialSpace"]
    env_kwargs = {"SimpleSocialSpace": {"agent_id_name_pairs": pairs}}
    llm_clients_spec = {
        "coder": get_dispatcher("coder"),
        "default": get_dispatcher("default"),
    }
    actor_cls = get_env_router_actor_class(
        max_concurrency=Config.ENV_ACTOR_MAX_CONCURRENCY
    )
    env_actor = actor_cls.remote(
        env_module_types,
        env_kwargs,
        str(run_dir.resolve()),
        {"final_summary_enabled": False},
        llm_clients_spec,
        None,  # replay_proxy: disabled.
    )
    env_router = EnvRouterProxy(env_actor, run_dir=run_dir.resolve())

    # Compose a ServiceProxy (shared LLM pool + trace; replay off).
    service_proxy = build_service_proxy(
        env_router,
        run_dir=run_dir,
        trace=True,
        replay=False,
    )

    start_t = datetime(2026, 6, 16, 8, 0, 0)

    society = AgentSociety(
        agent_specs=specs,
        agent_class_name="PersonAgent",
        env_router=env_router,
        start_t=start_t,
        run_dir=run_dir,
        service_proxy=service_proxy,
        batch_size=2,  # small batches → 2 tasks for 3 agents (exercises chunking)
        enable_replay=False,
    )

    try:
        await society.init()

        # (b) record-based: NO agent objects held.
        assert not hasattr(society, "_agents"), "society must not hold an _agents list"
        assert not any(
            isinstance(getattr(society, attr, None), list)
            and getattr(society, attr)
            and hasattr(getattr(society, attr)[0], "step")
            for attr in ("_agent_objects", "_agent_instances")
        ), "society must not hold agent instances anywhere"
        # It DOES hold specs + ids (records, not objects).
        assert society.agent_ids == agent_ids
        assert len(society.agent_specs) == 3
        # workspaces were created by create_agents_batch Ray Tasks.
        for aid in agent_ids:
            ws = run_dir / "agents" / f"agent_{aid:04d}"
            assert (ws / "AGENT.json").exists(), (
                f"workspace for agent {aid} not created"
            )
            assert (ws / "config.json").exists()

        # Run 2 steps via task streaming.
        await society.run(num_steps=2, tick=3600)

        # (c) env advanced.
        assert society.step_count == 2
        assert society.current_time == datetime(2026, 6, 16, 10, 0, 0)

        # (a) every agent's AGENT.json shows step_count == 2.
        for aid in agent_ids:
            ws = run_dir / "agents" / f"agent_{aid:04d}"
            meta = json.loads((ws / "AGENT.json").read_text(encoding="utf-8"))
            assert int(meta.get("step_count", 0)) == 2, (
                f"agent {aid} step_count != 2 (got {meta.get('step_count')}); "
                "state continuity broken across Ray Tasks"
            )

    finally:
        await society.close()
