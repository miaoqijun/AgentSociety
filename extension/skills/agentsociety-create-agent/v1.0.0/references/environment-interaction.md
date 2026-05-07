# Environment Interaction Patterns

## ask_env Method

```python
async def ask_env(
    self,
    ctx: dict,
    message: str,
    readonly: bool,
    template_mode: bool = False
) -> tuple[dict, str]
```

Returns `(updated_context, response_string)`.

## Common Patterns

### Query State

```python
_, observation = await self.ask_env(
    {}, 
    "What is happening?", 
    readonly=True
)
```

### Execute Action

```python
ctx, response = await self.ask_env(
    {"variables": {
        "agent_id": self.id,
        "action": "move",
        "target": "home"
    }},
    "Execute {action} for agent {agent_id} to {target}",
    readonly=False,
    template_mode=True
)
```

### Get Agent-Specific Data

```python
ctx, response = await self.ask_env(
    {"variables": {"agent_id": self.id}},
    "Get state for agent {agent_id}",
    readonly=True,
    template_mode=True
)
```

## Context Overlay

Agent identity is automatically merged from `env_codegen_ctx_overlay()`:
- `id`, `agent_id`, `person_id`

You don't need to pass these explicitly:

```python
# These are equivalent:
ctx, response = await self.ask_env({}, "My state", readonly=True)
ctx, response = await self.ask_env({"id": self.id}, "My state", readonly=True)
```

## Template Variables

Use `{variable_name}` syntax with `template_mode=True`:

```python
# Multiple variables
ctx, response = await self.ask_env(
    {"variables": {
        "donor": self.id,
        "recipient": neighbor_id,
        "action": "cooperate"
    }},
    "Execute donation: donor={donor}, recipient={recipient}, action={action}",
    readonly=False,
    template_mode=True
)
```

## Error Handling

When `ask_env` fails, behavior should be **predictable**: log, degrade to a default, or **re-raise** for upper layers—avoid bare `except` that hides everything. If you catch exceptions, keep the scope narrow (e.g. timeout or specific types only).

```python
try:
    _, result = await self.ask_env({}, "Query", readonly=True)
except TimeoutError:
    self.logger.warning("env query timed out")
    result = ""
```

## Readonly vs Read-Write

| Mode | `readonly` | Use Case |
|------|------------|----------|
| Query | `True` | Get information without side effects |
| Action | `False` | Execute actions that change state |

## Response Structure

The response string format depends on the environment module. Common patterns:

```python
# Observation response
updated_ctx, observation_text = await self.ask_env(
    {"id": self.id},
    "<observe>",
    readonly=True
)

# Action response
updated_ctx, result_text = await self.ask_env(
    {"id": self.id, "action": "move", "target": "cafe"},
    "Move to {target}",
    readonly=False,
    template_mode=True
)
```

The `updated_ctx` may contain structured data from the environment:

```python
ctx, response = await self.ask_env({}, "<observe>", readonly=True)
if "observations" in ctx:
    # Parse structured observation data
    neighbors = ctx["observations"].get("get_neighbors", {})
```
