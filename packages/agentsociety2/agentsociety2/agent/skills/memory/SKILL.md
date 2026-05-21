---
name: memory
description: Append notable events to state/memory.jsonl. Use after meaningful interactions, discoveries, decisions, or state changes. Forgetting runs via maintenance script.
script: scripts/memory_maintenance.py
---

# Memory

Store at most one durable memory from the current tick in `state/memory.jsonl`.

This skill decides what is worth remembering. It does not retrieve memories for reasoning, and it does not reimplement forgetting. Forgetting is handled by `scripts/memory_maintenance.py`.

## When to use

Use after observation, cognition, planning, action, or social interaction when something may matter later.

## Write when

- Meaningful interaction or new social fact
- New discovery, location, resource, hazard, or constraint
- Critical need, emotion, intention, or plan change
- Significant decision, action result, failure, or commitment

## Skip when

- Nothing changed
- The tick is routine or idle
- The fact is already in the latest memory line
- The content is only a restatement of `state/observation.txt`

## Entry format

Append one JSON object per line:

```json
{"tick":42,"time":"2024-01-15T10:30:00","type":"event","summary":"Met Alice at the park; she mentioned a library job.","tags":["social","alice","job"],"importance":"medium"}
```

Required fields:

| Field | Notes |
| --- | --- |
| `tick` | Current tick, if available |
| `time` | ISO timestamp, if available |
| `type` | `need`, `emotion`, `cognition`, `intention`, `plan`, `plan_execution`, `react`, `event`, `observation`, `social`, `decision`, `discovery`, or `plan_outcome` |
| `summary` | 1 factual sentence; 2 only if necessary |
| `tags` | 2-5 keywords, such as names, places, topics, or goals |
| `importance` | `high`, `medium`, or `low`; default is `medium` |

## Workflow

1. Read relevant context, usually `state/observation.txt` and recent state files.
2. Decide whether there is one notable fact to store.
3. If there is nothing worth storing, stop with `done`.
4. Read `state/memory.jsonl` before writing.
5. Check the latest memory line for duplication.
6. Append exactly one JSON line to the existing file content.
7. Write the full updated file back to `state/memory.jsonl`.
8. Stop with `done`.

## Maintenance

Run forgetting periodically through `execute_skill` with:

```json
{"memory_file":"state/memory.jsonl","current_tick":100}
```

Maintenance may set `_retention` and `_faded`, and may prune weak lines.

Tune via environment variables described in `references/forgetting.md`.

## Constraints

- Append; never overwrite previous memory entries.
- Store at most one memory per skill use.
- Do not store long raw observations.
- Do not duplicate the latest memory line.
- Use `importance: high` only for facts that should persist across the simulation.
- Keep summaries concrete, factual, and grounded in current state.

For details, use:

- `references/memory_policy.md`
- `references/forgetting.md`
- `references/examples.md`
