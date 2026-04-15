# AgentBase Interface

Core interfaces from `agentsociety2/agent/base.py`.

## Required Methods

```python
async def ask(self, message: str, readonly: bool = True) -> str
async def step(self, tick: int, t: datetime) -> str
async def dump(self) -> dict
async def load(self, dump_data: dict)
```

## Configuration

```python
from agentsociety2.agent.config import AgentConfig

# Create with defaults
config = AgentConfig()

# From environment variables
config = AgentConfig.from_env()

# Access configuration
config.model.model              # Model name
config.model.context_window     # Context window size
config.loop.max_rounds          # Max tool rounds per step
config.loop.step_timeout        # Step timeout (seconds)
config.persistence.checkpoint_interval  # Checkpoint interval
```

**Note**: Most config values are hardcoded with sensible defaults. Only expose `model`, `context_window`, `max_rounds`, `step_timeout`, and `checkpoint_interval` to users.

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
# Query (readonly)
ctx, response = await self.ask_env(
    {}, 
    "Current environment state?", 
    readonly=True
)

# Execute action
ctx, response = await self.ask_env(
    {"variables": {"location": "Beijing"}},
    "Get weather for {location}",
    readonly=False,
    template_mode=True
)
```

## Optional Methods

```python
# Called at startup
async def init(self, env: RouterBase) -> None

# Module discovery description (highly recommended)
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
- `env: RouterBase` - Environment router (after init)

## State Management

```python
# For skill-specific state
def set_skill_state(self, skill_name: str, state: Any)
def get_skill_state(self, skill_name: str) -> Any

# For workspace operations (PersonAgent only)
def workspace_read(self, path: str) -> str
def workspace_write(self, path: str, content: str) -> None
def workspace_exists(self, path: str) -> bool
```

## Persistence (PersonAgent)

PersonAgent provides built-in persistence:

- **Checkpoint**: Automatic state snapshots at configurable intervals
- **WAL (Write-Ahead Log)**: Records intents before execution for crash recovery
- **Recovery**: Automatic restoration from latest checkpoint on restart

```python
# Checkpoint is saved automatically every N ticks
# Configure via AgentConfig.persistence.checkpoint_interval

# Manual checkpoint (if needed)
await self._checkpoint.save(tick, state_data)
```
