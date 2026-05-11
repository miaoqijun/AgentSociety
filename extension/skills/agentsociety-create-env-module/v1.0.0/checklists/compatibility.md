# Compatibility Checklist

The generated env module must satisfy the repository contract:

- File path is `custom/envs/*.py`
- Class is defined in that file directly
- Class inherits `EnvBase`
- Registry key equals `class_name`
- At least one valid `@tool`
- `step()` exists
- `cls()` works without required constructor args
- Observation capability is exposed through readonly `kind="observe"` tools
- `mcp_description()` is callable and informative, with operations phrased in prose (bold function names + parameter descriptions), NOT as Python call literals — see `references/pitfalls.md` P2
- Every `@tool(readonly=False)` returns a dict / Pydantic model with a STRING `status` field whose value is one of `"success" | "fail" | "in_progress" | "error"` — `bool` and `{"success": True}` are CRITICAL bugs (see `references/pitfalls.md` P1)
- Every `@tool(readonly=False)` is idempotent within one step (last-write-wins, set-based dedup, or explicit dedup-key with per-step reset) — see `references/pitfalls.md` P3
- If 2+ write tools share parameter names, the collision risk with the agent-side template cache is acknowledged (rename or document mitigation) — see `references/pitfalls.md` P4
- If the module exposes replay-worthy per-agent state, `_agent_state_columns` and `_write_agent_state()` usage are present and aligned
- If the module exposes replay-worthy global state, `_env_state_columns` and `_write_env_state()` usage are present and aligned
- If the module has mutable in-memory state that must survive save/load, `_dump_state()` and `_load_state()` round-trip that state
- `CodeGenRouter` can mount the module without error (router smoke test)
