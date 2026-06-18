"""
Custom Agent Example

This example shows how to create a custom agent by inheriting from AgentBase.
Custom agents can then be used with AgentSociety for coordinated experiments.

NOTE (Phase 0 refactor): agents now follow the workspace contract
(create / from_workspace / to_workspace). The demo construction below still
creates agents directly for brevity; in a real run you would use
``Agent.create(...)`` + ``await Agent.from_workspace(ws, service_proxy)``.
"""

import os

# Disable telemetry before any imports
os.environ.setdefault("MEM0_TELEMETRY", "False")
os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")

import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from agentsociety2.agent import AgentBase
from agentsociety2.env import CodeGenRouter
from agentsociety2.contrib.env import SimpleSocialSpace
from agentsociety2.society import AgentSociety


class SpecialistAgent(AgentBase):
    """
    A custom agent that specializes in a particular domain.
    """

    def __init__(
        self,
        id: int,
        profile: dict,
        name: str | None = None,
        *,
        config: dict[str, Any] | None = None,
        **kwargs,
    ):
        super().__init__(id=id, profile=profile, name=name, **kwargs)
        self._specialty = str((config or {}).get("specialty", "general"))
        self._step_count = 0

    # ==================== Workspace 契约 ====================

    @classmethod
    def create(cls, workspace_path: Path, profile: dict, config: dict) -> None:
        workspace_path = Path(workspace_path)
        workspace_path.mkdir(parents=True, exist_ok=True)
        (workspace_path / "config.json").write_text(
            json.dumps(config or {}, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        agent_id = int(profile.get("id", 0))
        (workspace_path / "AGENT.json").write_text(
            json.dumps(
                {
                    "id": agent_id,
                    "name": profile.get("name", f"Agent_{agent_id}"),
                    "profile": profile,
                    "step_count": 0,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    @classmethod
    async def from_workspace(
        cls, workspace_path: Path, service_proxy: Any
    ) -> "SpecialistAgent":
        workspace_path = Path(workspace_path)
        config = json.loads(
            (workspace_path / "config.json").read_text(encoding="utf-8")
        )
        meta = json.loads((workspace_path / "AGENT.json").read_text(encoding="utf-8"))
        agent = cls(
            int(meta.get("id", 0)),
            meta.get("profile", {}),
            meta.get("name"),
            config=config,
        )
        agent._bind_services(service_proxy)
        agent._step_count = int(meta.get("step_count", 0))
        return agent

    async def to_workspace(self, workspace_path: Path) -> None:
        workspace_path = Path(workspace_path)
        (workspace_path / "AGENT.json").write_text(
            json.dumps(
                {
                    "id": self._id,
                    "name": self._name,
                    "profile": self.get_profile(),
                    "step_count": self._step_count,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    async def step(self, tick: int, t: datetime) -> str:
        self._step_count += 1
        return f"SpecialistAgent step {tick}"

    async def ask(self, question: str, readonly: bool = True) -> str:
        """
        Answer a question, adding specialty context.
        """
        enhanced_question = (
            f"You are a specialist in {self._specialty}. "
            f"Answer the following question from this perspective: {question}"
        )
        try:
            response = await self.acompletion(
                [{"role": "user", "content": enhanced_question}]
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            return f"[error] {e!s}"

    async def reflect_on_specialty(self) -> str:
        """
        Custom method for reflecting on the agent's specialty.
        """
        question = (
            f"As a specialist in {self._specialty}, "
            "what do you consider to be the most important aspects of your field?"
        )
        return await self.ask(question, readonly=True)


class RecursiveAgent(AgentBase):
    """
    An agent that uses chain-of-thought reasoning by default.
    """

    def __init__(
        self,
        id: int,
        profile: dict,
        name: str | None = None,
        *,
        config: dict[str, Any] | None = None,
        **kwargs,
    ):
        super().__init__(id=id, profile=profile, name=name, **kwargs)
        self._step_count = 0

    # ==================== Workspace 契约 ====================

    @classmethod
    def create(cls, workspace_path: Path, profile: dict, config: dict) -> None:
        workspace_path = Path(workspace_path)
        workspace_path.mkdir(parents=True, exist_ok=True)
        (workspace_path / "config.json").write_text(
            json.dumps(config or {}, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        agent_id = int(profile.get("id", 0))
        (workspace_path / "AGENT.json").write_text(
            json.dumps(
                {
                    "id": agent_id,
                    "name": profile.get("name", f"Agent_{agent_id}"),
                    "profile": profile,
                    "step_count": 0,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    @classmethod
    async def from_workspace(
        cls, workspace_path: Path, service_proxy: Any
    ) -> "RecursiveAgent":
        workspace_path = Path(workspace_path)
        meta = json.loads((workspace_path / "AGENT.json").read_text(encoding="utf-8"))
        agent = cls(int(meta.get("id", 0)), meta.get("profile", {}), meta.get("name"))
        agent._bind_services(service_proxy)
        agent._step_count = int(meta.get("step_count", 0))
        return agent

    async def to_workspace(self, workspace_path: Path) -> None:
        workspace_path = Path(workspace_path)
        (workspace_path / "AGENT.json").write_text(
            json.dumps(
                {
                    "id": self._id,
                    "name": self._name,
                    "profile": self.get_profile(),
                    "step_count": self._step_count,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    async def step(self, tick: int, t: datetime) -> str:
        self._step_count += 1
        return f"RecursiveAgent step {tick}"

    async def ask(self, question: str, readonly: bool = True, depth: int = 2) -> str:
        """
        Override ask to implement multi-step reasoning.
        """
        if depth <= 0:
            return await self._answer(question)

        # First, ask the agent to break down the question
        breakdown_prompt = (
            f"Break down this question into sub-questions: {question}\n"
            "Respond with a JSON object containing a 'sub_questions' array."
        )

        breakdown = await self._answer(breakdown_prompt)

        # Process sub-questions recursively
        import json_repair

        try:
            parsed = json_repair.loads(breakdown)
            sub_questions = parsed.get("sub_questions", [])
        except Exception:
            sub_questions = []

        if not sub_questions:
            # If parsing failed, just answer normally
            return await self._answer(question)

        # Answer each sub-question
        sub_answers = []
        for sq in sub_questions[:3]:  # Limit to 3 sub-questions
            answer = await self._answer(sq)
            sub_answers.append(f"Q: {sq}\nA: {answer}")

        # Synthesize final answer
        synthesis_prompt = (
            f"Original question: {question}\n\n"
            f"Sub-question analysis:\n{chr(10).join(sub_answers)}\n\n"
            "Based on the above analysis, provide a comprehensive answer to the original question."
        )

        return await self._answer(synthesis_prompt)

    async def _answer(self, question: str) -> str:
        """Single LLM completion for the CoT reasoning steps."""
        try:
            response = await self.acompletion([{"role": "user", "content": question}])
            return response.choices[0].message.content or ""
        except Exception as e:
            return f"[error] {e!s}"


async def main():
    print("=== Custom Agent Examples ===\n")

    # Example 1: Specialist Agent
    print("--- Specialist Agent ---\n")

    climate_specialist = SpecialistAgent(
        id=1,
        profile={"name": "Dr. Climate", "personality": "scientific and concerned"},
        config={"specialty": "climate science and environmental policy"},
    )

    # Create environment with agent info
    social_env = SimpleSocialSpace(
        agent_id_name_pairs=[(climate_specialist.id, climate_specialist.name)]
    )
    env_router = CodeGenRouter(env_modules=[social_env])

    # Create society with specialist agent
    society1 = AgentSociety(
        agents=[climate_specialist],
        env_router=env_router,
        start_t=datetime.now(),
    )
    await society1.init()

    question = "What should cities do to prepare for extreme weather?"
    response = await society1.ask(question)
    print(f"Question: {question}")
    print(f"Specialist Response: {response[:200]}...\n")

    await society1.close()

    # Example 2: Using custom methods directly (requires agent to be initialized)
    print("--- Custom Method: Reflection ---\n")

    specialist2 = SpecialistAgent(
        id=2,
        profile={"name": "Dr. Science", "personality": "curious"},
        config={"specialty": "environmental science"},
    )

    social_env2 = SimpleSocialSpace(
        agent_id_name_pairs=[(specialist2.id, specialist2.name)]
    )
    env_router2 = CodeGenRouter(env_modules=[social_env2])
    society2 = AgentSociety(
        agents=[specialist2],
        env_router=env_router2,
        start_t=datetime.now(),
    )
    await society2.init()

    reflection = await specialist2.reflect_on_specialty()
    print(f"Specialty Reflection: {reflection[:200]}...\n")

    await society2.close()

    # Example 3: Recursive Agent with CoT
    print("--- Recursive (CoT) Agent ---\n")

    thinker = RecursiveAgent(
        id=3,
        profile={"name": "Deep Thinker", "personality": "analytical and methodical"},
    )

    social_env3 = SimpleSocialSpace(agent_id_name_pairs=[(thinker.id, thinker.name)])
    env_router3 = CodeGenRouter(env_modules=[social_env3])

    society3 = AgentSociety(
        agents=[thinker],
        env_router=env_router3,
        start_t=datetime.now(),
    )
    await society3.init()

    question = "How can we reduce urban traffic congestion?"
    response = await thinker.ask(question, readonly=True, depth=2)
    print(f"Question: {question}")
    print(f"CoT Response: {response[:300]}...\n")

    await society3.close()


if __name__ == "__main__":
    asyncio.run(main())
