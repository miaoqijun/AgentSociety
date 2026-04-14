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
try:
    _, observation = await self.ask_env(
        {}, 
        "What is happening?", 
        readonly=True
    )
except Exception as e:
    observation = f"Query failed: {e}"
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

## Error Handling

Always wrap environment calls:

```python
try:
    _, result = await self.ask_env({}, "Query", readonly=True)
except Exception as e:
    self.logger.warning(f"Environment error: {e}")
    result = "Unknown"
```
