# Code Templates

## Template 1: Simple Agent

```python
"""
{AgentName}: {Description}
"""

from agentsociety2.agent.base import AgentBase
from datetime import datetime
from pathlib import Path
from typing import Any


class {AgentName}(AgentBase):
    """{Description}"""

    def __init__(self, id: int, profile: Any, name: str = None):
        super().__init__(id, profile, name)
        self._custom_state: dict[str, Any] = {}
        self._work_dir: Path | None = None

    @classmethod
    def mcp_description(cls) -> str:
        return """{AgentName}: {Short Description}

**Profile Fields:** {field_list}
"""

    async def init(self, env) -> None:
        await super().init(env)
        run_dir = getattr(env, "run_dir", None)
        if run_dir:
            self._work_dir = Path(run_dir) / "agents" / f"agent_{self._id:04d}"
            self._work_dir.mkdir(parents=True, exist_ok=True)

    async def ask(self, message: str, readonly: bool = True) -> str:
        profile = self.get_profile()
        prompt = f"You are {profile.get('name')}. Question: {message}"
        response = await self.acompletion([{"role": "user", "content": prompt}])
        return response.choices[0].message.content or ""

    async def step(self, tick: int, t: datetime) -> str:
        try:
            _, obs = await self.ask_env({}, "Current state?", readonly=True)
        except Exception as e:
            obs = f"Error: {e}"
        return f"Agent {self.name} observed: {obs}"

    async def dump(self) -> dict:
        return {"id": self._id, "name": self._name, "profile": self.get_profile()}

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
        return """{AgentName}: {Short Description}

**Profile Fields:** name, personality, {custom_fields}
**Internal States:** memories, mood
"""

    async def init(self, env) -> None:
        await super().init(env)
        run_dir = getattr(env, "run_dir", None)
        if run_dir:
            self._work_dir = Path(run_dir) / "agents" / f"agent_{self._id:04d}"
            self._work_dir.mkdir(parents=True, exist_ok=True)
            await self._load_state()

    async def _load_state(self):
        if not self._work_dir:
            return
        state_file = self._work_dir / "state.json"
        if state_file.exists():
            data = json.loads(state_file.read_text())
            self._memories = data.get("memories", [])
            self._mood = data.get("mood", "calm")

    async def _save_state(self):
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
        try:
            _, obs = await self.ask_env({}, "Current state?", readonly=True)
        except Exception as e:
            obs = f"Error: {e}"
        self._memories.append({"content": obs})
        await self._save_state()
        return f"Agent {self.name} ({self._mood}): {obs}"

    async def dump(self) -> dict:
        return {
            "id": self._id, "name": self._name,
            "profile": self.get_profile(),
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
        return """{AgentName}: {Short Description}

**Game:** {game_name}
"""

    async def ask(self, message: str, readonly: bool = True) -> str:
        response = await self.acompletion([{"role": "user", "content": message}])
        return response.choices[0].message.content or ""

    async def step(self, tick: int, t: datetime) -> str:
        # Get game state
        try:
            _, state = await self.ask_env({}, "Get state", readonly=True)
        except Exception as e:
            return f"Error: {e}"
        
        # Make decision
        decision = await self._decide(state)
        
        # Submit
        try:
            _, result = await self.ask_env(
                {"variables": decision},
                "Submit with {variables}",
                readonly=False, template_mode=True
            )
        except Exception as e:
            return f"Submit error: {e}"
        
        return f"{self.name}: {decision}"

    async def _decide(self, state: str) -> dict:
        # Implement decision logic
        return {}

    async def dump(self) -> dict:
        return {"id": self._id, "name": self._name, "history": self._history}

    async def load(self, dump_data: dict):
        self._id = dump_data.get("id", self._id)
        self._name = dump_data.get("name", self._name)
        self._history = dump_data.get("history", [])
```

## Selection Guide

| Need | Template |
|------|----------|
| Basic decision-making | Template 1 |
| Memory/emotion tracking | Template 2 |
| Game participation | Template 3 |
| No state persistence | Template 3 |
