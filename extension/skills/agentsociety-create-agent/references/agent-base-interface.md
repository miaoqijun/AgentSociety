# AgentBase Interface

Key interfaces from `agentsociety2/agent/base.py`.

## Required Methods

```python
async def ask(self, message: str, readonly: bool = True) -> str
async def step(self, tick: int, t: datetime) -> str
async def dump(self) -> dict
async def load(self, dump_data: dict)
```

## LLM Interaction

```python
# Basic completion
response = await self.acompletion([
    {"role": "user", "content": "What should I do?"}
])
content = response.choices[0].message.content

# With Pydantic validation
from pydantic import BaseModel

class Decision(BaseModel):
    action: str
    confidence: float

decision = await self.acompletion_with_pydantic_validation(
    Decision, messages, tick, t
)
```

## Environment Interaction

```python
# Query
ctx, response = await self.ask_env(
    {}, 
    "Current environment state?", 
    readonly=True
)

# With template variables
ctx, response = await self.ask_env(
    {"variables": {"location": "Beijing"}},
    "Get weather for {location}",
    readonly=True,
    template_mode=True
)
```

## Optional Methods

```python
# Called at startup
async def init(self, env: RouterBase) -> None

# Module discovery description
@classmethod
def mcp_description(cls) -> str

# System prompt for LLM
def get_system_prompt(self, tick: int, t: datetime) -> str

# Profile access
def get_profile(self) -> Dict[str, Any]
```

## Properties

- `id: int` - Unique identifier
- `name: str` - Display name
- `logger: Logger` - Agent logger

## State Management

```python
# For skill-specific state
def set_skill_state(self, skill_name: str, state: Any)
def get_skill_state(self, skill_name: str) -> Any
```
