---
name: agentsociety-create-agent
description: Create custom Agent classes for AgentSociety platform. Use when the user wants to create a new agent type (e.g., "I need a student agent"), design agent behaviors, or implement AgentBase/PersonAgent subclasses.
---

# Create Agent

Guide for creating custom Agent classes under `custom/agents/`.

## Workflow

1. Collect requirements → `stages/intake.md`
2. Design architecture → `stages/design.md`
3. Generate code → `stages/generate.md`
4. Validate → `stages/validate.md`
5. Run "Scan Custom Modules" command

## Base Class Selection

| Class | Use Case | Features |
|-------|----------|----------|
| `AgentBase` | Simple behaviors, games, benchmarks | Minimal, manual state |
| `PersonAgent` | Complex behaviors, skills, tools | Workspace, skills, checkpoint, WAL |

## Required Methods

```python
async def ask(self, message: str, readonly: bool = True) -> str
async def step(self, tick: int, t: datetime) -> str
async def dump(self) -> dict
async def load(self, dump_data: dict)
```

## Key Questions

- What role/behaviors does the agent have?
- What internal states need tracking? (memory, mood, fatigue...)
- How does it interact with the environment?
- What profile fields define this agent type?

## Environment Interaction

```python
# Query
_, observation = await self.ask_env({}, "Current state?", readonly=True)

# Action
_, result = await self.ask_env(
    {"variables": {"action": "move"}},
    "Execute {action}",
    readonly=False, template_mode=True
)
```

## Workspace Structure

| Type | Structure | When to Use |
|------|-----------|-------------|
| None | No workspace | Game/benchmark agents |
| Simple | `state.json` | Simple state persistence |
| Full | `state/`, `memory/`, `logs/` | Complex agents, PersonAgent |

## Validation

```bash
python scripts/validate.py --file custom/agents/my_agent.py
```

## References

- `references/agent-base-interface.md` - Full API reference
- `references/environment-interaction.md` - Environment patterns
- `artifacts/templates.md` - Code templates (AgentBase, PersonAgent)
