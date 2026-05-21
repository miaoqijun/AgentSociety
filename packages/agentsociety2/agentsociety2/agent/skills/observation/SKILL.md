---
name: observation
description: Fetch the current world observation for this tick via codegen observe. Use before cognition, memory, intention, or planning when fresh perception is needed.
---

# Observation

Fetch the current world observation for this tick and persist it as workspace artifacts.

This skill only observes. It does not reason, plan, or perform environment actions other than `<observe>`.

## Outputs

| File                         | Use                                      |
| ---------------------------- | ---------------------------------------- |
| `state/observation.txt`      | Human-readable current observation       |
| `state/observation_ctx.json` | Structured context from `codegen`, optional |
| `state/memory.jsonl`         | Optional durable memory line             |

## Core rules

- Use at most one `<observe>` call per tick.
- Do not observe again after a successful or in-progress environment action in the same tick.
- Always write `state/observation.txt` on `success`, even if the observation is short.
- Write `state/observation_ctx.json` only when `ctx` contains useful structured data.
- Append to `state/memory.jsonl` only for salient, non-duplicate information.
- After writing artifacts, stop with `done`.

## Workflow

1. Read Agent Identity to get `id`.
2. Call `codegen` with instruction `<observe>` and context `{"id": <your_agent_id>}`.
3. If `status` is `in_progress`, stop with `done`; do not write partial observation unless stdout is useful.
4. If `status` is `success`, write stdout to `state/observation.txt`.
5. If returned `ctx` is useful, write it as JSON to `state/observation_ctx.json`.
6. Optionally append one observation memory line if it is worth recalling and not a duplicate.
7. Stop with `done`.

## Error handling

If `codegen` fails:

- Write a short failure note to `state/observation.txt`.
- Do not invent an observation.
- Stop with `done`.

## Memory rule

Only remember information likely to matter beyond the current tick, such as location changes, discovered resources, hazards, social commitments, or task-relevant facts.

For details, use:

- `references/output_contract.md`
- `references/memory_rules.md`
- `references/examples.md`
