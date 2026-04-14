---
name: agentsociety-create-agent
description: Create custom Agent classes for AgentSociety platform. Use when the user wants to create a new agent type (e.g., "I need a student agent"), design agent behaviors, or implement AgentBase/PersonAgent subclasses.
license: Proprietary. LICENSE.txt has complete terms
---

# Create Agent

Guide for creating custom Agent classes under `custom/agents/`.

## Standard Sequence

1. Collect requirements (`stages/intake.md`)
2. Design architecture (`stages/design.md`)
3. Generate code (`stages/generate.md`)
4. Validate (`stages/validate.md`)
5. Run "Scan Custom Modules" command

## Stage Routing

- Requirements intake: `stages/intake.md`
- Design decisions: `stages/design.md`
- Code generation: `stages/generate.md`
- Validation: `stages/validate.md`

## Shared References

- Compatibility checklist: `checklists/compatibility.md`
- Code templates: `artifacts/templates.md`
- Validation CLI: `scripts/validate.py`

## Key Questions

Ask the user:

- What role/behaviors does the agent have?
- What internal states need tracking? (memory, mood, fatigue...)
- How does it interact with the environment?
- What profile fields define this agent type?

## Base Class Selection

| Class | When to Use |
|-------|-------------|
| `AgentBase` | Simple behaviors, game theory, specific tasks (recommended) |
| `PersonAgent` | Complex behaviors requiring skill discovery and tool loops |

## Required Methods

All agents MUST implement:

```python
async def ask(self, message: str, readonly: bool = True) -> str
async def step(self, tick: int, t: datetime) -> str
async def dump(self) -> dict
async def load(self, dump_data: dict)
```

## Optional Methods

```python
@classmethod
def mcp_description(cls) -> str        # Highly recommended

async def init(self, env) -> None      # Create workspace if needed
```

## Workspace Structure

| Type | Structure | When to Use |
|------|-----------|-------------|
| None | No workspace | Game/benchmark agents |
| Simple | `state.json` | Simple state persistence |
| Full | `state/`, `memory/`, `logs/` | Complex agents |

## Environment Interaction

```python
# Query
_, response = await self.ask_env({}, "Current state?", readonly=True)

# Action with template
_, response = await self.ask_env(
    {"variables": {"agent_id": self.id}},
    "Execute action for {agent_id}",
    readonly=False, template_mode=True
)
```

## Validation

```bash
python scripts/validate.py --file custom/agents/my_agent.py
```

## Runtime Contract

- Generated code must land in `custom/agents/*.py`
- Files in `examples/` are NOT scanned for registration
- After creation, run "Scan Custom Modules" command

## References

- `references/agent-base-interface.md` - Full API reference
- `references/environment-interaction.md` - Environment patterns
- `references/profile-design.md` - Profile design guide
- `references/examples.md` - Existing agent examples
- `artifacts/templates.md` - Complete code templates
