# Validate

## Script (automated checks)

Replace the path with your workspace:

```bash
$PYTHON_PATH .agentsociety/bin/ags.py create-agent --file /path/to/workspace/custom/agents/my_agent.py
$PYTHON_PATH .agentsociety/bin/ags.py create-agent --file ... --json
```

## Manual checklist

Before merge/release, walk through **`checklists/compatibility.md`** (signatures, inheritance, `mcp_description`, paths)—not duplicated here.

## After it passes

1. Fix anything reported by the script or checklist  
2. **Scan Custom Modules**  
3. Run **Test Custom Modules** if you need runtime smoke tests  

## Common issues

| Symptom | What to do |
|---------|------------|
| No agent class found | Direct base name must be `AgentBase` or `PersonAgent` in AST; if you use an alias, ensure the module imports and MRO still includes `AgentBase`. If the class only subclasses an intermediate base, refactor so `AgentBase`/`PersonAgent` appears in the direct bases **or** rely on Scan-only checks and fix runtime issues manually |
| Missing `async` | All four required methods must be `async def` (the VS Code scanner does not check this) |
| Abstract class | Implement every abstract method from `AgentBase` |
| Import errors | Dependencies, `PYTHONPATH`, circular imports |
| Generic module blurb | Override `@classmethod def mcp_description(cls) -> str`; `AgentBase` already provides a fallback description |
| Scan passes but agent breaks at runtime | Scanner only checks attribute names exist; run this script plus instantiating the class in a small test |
