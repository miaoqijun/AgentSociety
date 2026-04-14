# Validate

Run validation and fix issues.

## Validation Script

```bash
python scripts/validate.py --file custom/agents/my_agent.py
```

## Validation Checks

- [ ] Inherits from `AgentBase`
- [ ] Implements `ask()` (async)
- [ ] Implements `step()` (async)
- [ ] Implements `dump()` (async)
- [ ] Implements `load()` (async)
- [ ] Has `mcp_description()` method
- [ ] Can be imported without errors

## After Validation

1. Fix any errors reported
2. Run VSCode command "Scan Custom Modules"
3. Run VSCode command "Test Custom Modules"

## Common Issues

| Issue | Fix |
|-------|-----|
| Missing method | Implement the method |
| Not async | Add `async` keyword |
| No mcp_description | Add `@classmethod def mcp_description(cls)` |
| Import error | Check imports and PYTHON_PATH |
