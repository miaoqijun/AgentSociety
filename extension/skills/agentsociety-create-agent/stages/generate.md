# Generate

Write the Agent code.

## Output Location

`custom/agents/<agent_name>.py`

## Generation Steps

1. Select appropriate template from `artifacts/templates.md`
2. Replace placeholders with actual values
3. Implement custom logic in `ask()` and `step()`
4. Add `mcp_description()` with profile fields

## Template Placeholders

| Placeholder | Replace With |
|-------------|--------------|
| `{AgentName}` | Class name (PascalCase) |
| `{Description}` | Brief description |
| `{Short Description}` | One-line summary |
| `{field_list}` | Profile field names |

## Code Quality

- Use async for all required methods
- Handle errors with try/except
- Use `.get(key, default)` for profile access
- Keep dump/load symmetric
