# Code Templates

## Template 1: Simple Agent

```python
"""{AgentName}: {Description}"""

from agentsociety2.agent.base import AgentBase
from datetime import datetime
from pathlib import Path
from typing import Any


class {AgentName}(AgentBase):
    """{Description}"""

    def __init__(self, id: int, profile: Any, name: str = None):
        super().__init__(id, profile, name)
        self._state: dict[str, Any] = {}

    @classmethod
    def mcp_description(cls) -> str:
        return "{AgentName}: {Short Description}"

    async def init(self, env) -> None:
        await super().init(env)

    async def ask(self, message: str, readonly: bool = True) -> str:
        response = await self.acompletion([{"role": "user", "content": message}])
        return response.choices[0].message.content or ""

    async def step(self, tick: int, t: datetime) -> str:
        _, obs = await self.ask_env({}, "Current state?", readonly=True)
        return f"Observed: {obs}"

    async def dump(self) -> dict:
        return {"id": self._id, "name": self._name}

    async def load(self, dump_data: dict):
        self._id = dump_data.get("id", self._id)
        self._name = dump_data.get("name", self._name)
```

## Template 2: Memory Agent

```python
"""{AgentName}: Agent with memory and emotion."""

from agentsociety2.agent.base import AgentBase
from datetime import datetime
from pathlib import Path
from typing import Any
import json


class {AgentName}(AgentBase):
    def __init__(self, id: int, profile: Any, name: str = None):
        super().__init__(id, profile, name)
        self._memories: list[dict] = []
        self._mood: str = "calm"
        self._work_dir: Path | None = None

    @classmethod
    def mcp_description(cls) -> str:
        return "{AgentName}: {Short Description}\nStates: memories, mood"

    async def init(self, env) -> None:
        await super().init(env)
        run_dir = getattr(env, "run_dir", None)
        if run_dir:
            self._work_dir = Path(run_dir) / "agents" / f"agent_{self._id:04d}"
            self._work_dir.mkdir(parents=True, exist_ok=True)
            self._load_state()

    def _load_state(self):
        if not self._work_dir:
            return
        state_file = self._work_dir / "state.json"
        if state_file.exists():
            data = json.loads(state_file.read_text())
            self._memories = data.get("memories", [])
            self._mood = data.get("mood", "calm")

    def _save_state(self):
        if not self._work_dir:
            return
        (self._work_dir / "state.json").write_text(json.dumps({
            "memories": self._memories[-100:],
            "mood": self._mood,
        }))

    async def ask(self, message: str, readonly: bool = True) -> str:
        mem_text = "\n".join(m["content"] for m in self._memories[-5:]) or "No memories"
        prompt = f"Profile: {self.get_profile()}\nMood: {self._mood}\nMemories:\n{mem_text}\n\nQ: {message}"
        response = await self.acompletion([{"role": "user", "content": prompt}])
        answer = response.choices[0].message.content or ""
        self._memories.append({"content": f"Q: {message}\nA: {answer[:100]}"})
        return answer

    async def step(self, tick: int, t: datetime) -> str:
        _, obs = await self.ask_env({}, "Current state?", readonly=True)
        self._memories.append({"content": obs})
        self._save_state()
        return f"{self.name} ({self._mood}): {obs}"

    async def dump(self) -> dict:
        return {
            "id": self._id, "name": self._name,
            "memories": self._memories, "mood": self._mood,
        }

    async def load(self, dump_data: dict):
        self._id = dump_data.get("id", self._id)
        self._name = dump_data.get("name", self._name)
        self._memories = dump_data.get("memories", [])
        self._mood = dump_data.get("mood", "calm")
```

## Template 3: Game Agent

```python
"""{AgentName}: Game participant."""

from agentsociety2.agent.base import AgentBase
from datetime import datetime
from typing import Any


class {AgentName}(AgentBase):
    def __init__(self, id: int, profile: Any, name: str = None):
        super().__init__(id, profile, name)
        self._history: list[dict] = []

    @classmethod
    def mcp_description(cls) -> str:
        return "{AgentName}: {Short Description}"

    async def ask(self, message: str, readonly: bool = True) -> str:
        response = await self.acompletion([{"role": "user", "content": message}])
        return response.choices[0].message.content or ""

    async def step(self, tick: int, t: datetime) -> str:
        # Get game state (readonly query — template_mode=True is safe)
        _, state = await self.ask_env(
            {"variables": {"agent_name": self.name}},
            "Please call get_state() using agent_name from ctx['variables'].",
            readonly=True,
            template_mode=True,
        )

        # Make decision
        decision = await self._decide(state)

        # Submit action (stateful write — see references/pitfalls.md P3).
        # template_mode=False unless your env tool is verified idempotent
        # AND argument names don't collide with other write tools.
        _, result = await self.ask_env(
            {"variables": {"agent_name": self.name, "action": decision}},
            "Please call submit_action() using agent_name and action "
            "from ctx['variables'] to submit my decision for this round.",
            readonly=False,
            template_mode=False,
        )

        return f"{self.name}: {decision}"

    async def _decide(self, state: str) -> dict:
        # Implement game-specific logic
        return {}

    async def dump(self) -> dict:
        return {"id": self._id, "name": self._name, "history": self._history}

    async def load(self, dump_data: dict):
        self._id = dump_data.get("id", self._id)
        self._name = dump_data.get("name", self._name)
        self._history = dump_data.get("history", [])
```

## Template 4: PersonAgent (Skill-Based)

For complex agents requiring skill discovery and tool loops:

```python
"""{AgentName}: Complex agent with skills."""

from agentsociety2.agent import PersonAgent
from agentsociety2.agent.config import AgentConfig
from datetime import datetime
from typing import Any


class {AgentName}(PersonAgent):
    """{Description}
    
    Uses skill-based architecture for:
    - observation: Environment perception
    - cognition: Emotional state, needs, intentions
    - plan: Action execution
    """

    @classmethod
    def mcp_description(cls) -> str:
        return """{AgentName}: {Short Description}

Skills: observation, cognition, plan
"""

    async def step(self, tick: int, t: datetime) -> str:
        # PersonAgent handles skill activation and tool loop
        # Override to customize behavior
        return await super().step(tick, t)
```

## Selection Guide

| Need | Template | Key Features |
|------|----------|--------------|
| Basic decision-making | Template 1 | Minimal, no state |
| Memory/emotion tracking | Template 2 | Persistent state, mood |
| Game participation | Template 3 | No persistence, fast |
| Complex behaviors | Template 4 | Skills, tools, persistence |

## Key Differences

| Feature | AgentBase | PersonAgent |
|---------|-----------|-------------|
| Workspace | Manual | Automatic |
| Skills | None | Built-in |
| Persistence | Manual | Checkpoint + WAL |
| Tool Loop | Manual | Automatic |
| LLM Calls | Manual | Managed |
