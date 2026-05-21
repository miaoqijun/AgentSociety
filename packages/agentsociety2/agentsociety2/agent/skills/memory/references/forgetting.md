# Forgetting

Forgetting is implemented in `scripts/memory_maintenance.py`.

Do not restate or reimplement the math in `SKILL.md`.

## Intended behavior

The maintenance script may:

- estimate retention strength
- boost repeated or important memories
- mark weak memories with `_faded`
- prune entries when the memory file grows too large

## Suggested configuration

Environment variables may include:

| Variable | Purpose |
| --- | --- |
| `AGENT_MEMORY_STRENGTH` | Base retention strength |
| `AGENT_MEMORY_ACTR_DECAY` | ACT-R-style decay rate |
| `AGENT_MEMORY_RETRIEVAL_THRESHOLD` | Minimum retention for keeping memory active |
| `AGENT_MEMORY_MAX_ENTRIES` | Maximum number of memory lines to keep |

## Maintenance call

Use periodically:

```json
{"memory_file":"state/memory.jsonl","current_tick":100}
```

## Skill boundary

The memory skill only writes new memory entries.

Maintenance owns fading, scoring, and pruning.
