---
name: agentsociety-create-agent
description: Create custom Agent classes for AgentSociety platform. Use when the user wants to create a new agent type (e.g., "I need a student agent"), design agent behaviors, or implement AgentBase/PersonAgent subclasses.
license: Proprietary. LICENSE.txt has complete terms
---

# Create Agent

Add Python modules under **`custom/agents/`** relative to the **workspace root** (the directory that contains `custom/`). The backend scanner loads every `*.py` under that tree **except** paths under an **`examples/`** segment.

- Nested folders are allowed (e.g. `custom/agents/research/lab_agent.py`).
- Prefer **one primary agent class per file** for clarity; the scanner can surface multiple `AgentBase` subclasses in the same file if you define them.

## Steps (open the linked doc when needed)

| # | Focus | Doc |
|---|--------|-----|
| 1 | Gather requirements, clarify open questions | `stages/intake.md` |
| 2 | Base class / workspace / profile / state | `stages/design.md` (can combine with step 1 in one pass) |
| 3 | Implement code from templates | `stages/generate.md` → `artifacts/templates.md` |
| 4 | Self-check and run the validator | `stages/validate.md`, `checklists/compatibility.md` |
| 5 | Register | VS Code: **Scan Custom Modules** (and **Test Custom Modules** if needed) |

## Base class

| Class | When to use |
|-------|-------------|
| `AgentBase` | Simple behavior, games/benchmarks, you manage state yourself |
| `PersonAgent` | Skills, tool loops, workspace, checkpoint/WAL, heavier runtime |

Required and optional methods, LLM/env APIs, config: use **`references/agent-base-interface.md`** as the single detailed source (avoids duplicating it here).

## Environment and profile

- Env call patterns: `references/environment-interaction.md`
- Profile fields: `references/profile-design.md`
- In-repo examples: `references/examples.md`

## Validation

```bash
python scripts/validate.py --file /path/to/workspace/custom/agents/my_agent.py
python scripts/validate.py --file ... --json
```

The script checks: AST shows a **direct** base named **`AgentBase` or `PersonAgent`**, all four required methods are **`async def`**, the module imports, and the class is not abstract. That is **stricter** than **Scan Custom Modules**: the scanner treats any in-file class with `issubclass(cls, AgentBase)` as a candidate and only verifies `hasattr` for the four names (no `async` check). Intermediate bases (`class MyAgent(MyMiddle, AgentBase)`) are fine at runtime but may fail this skill’s AST rule—fix by satisfying the import/MRO note in `stages/validate.md` or adjust the inheritance shape.

`AgentBase` already defines a default `mcp_description`; overriding it is still recommended for real modules.

For the full human checklist see `stages/validate.md` and `checklists/compatibility.md`.
