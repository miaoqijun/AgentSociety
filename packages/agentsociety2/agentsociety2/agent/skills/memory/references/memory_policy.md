# Memory Policy

## Purpose

Memory stores durable facts that may be useful after the current tick is gone.

It should not become a full transcript. The current observation and logs already contain low-level details.

## Salience rules

Prefer storing facts that are:

- durable: likely to remain useful across future ticks
- actionable: changes future decisions or plans
- specific: includes names, places, resources, hazards, commitments, or outcomes
- non-obvious: not merely a repeated routine state

## Importance

Use `high` for:

- long-lived goals or commitments
- major social relationships or promises
- severe hazards or critical failures
- persistent world facts

Use `medium` for:

- useful discoveries
- normal plan changes
- meaningful interactions
- task-relevant outcomes

Use `low` for:

- mildly useful but routine facts
- weak preferences
- minor state changes

Default to `medium`.

## Type selection

Use the most specific type available:

| Type | Use |
| --- | --- |
| `need` | Hunger, fatigue, safety, or other need state changed meaningfully |
| `emotion` | Strong emotional reaction likely to affect behavior |
| `cognition` | Important belief, reflection, or inference |
| `intention` | New goal or goal cancellation |
| `plan` | Plan created, interrupted, resumed, or changed |
| `plan_execution` | Step result, blockage, or progress |
| `react` | Notable reasoning-action-feedback episode |
| `event` | General significant event |
| `observation` | Durable perceived fact |
| `social` | Interaction, relationship, promise, or message |
| `decision` | Choice that constrains future behavior |
| `discovery` | New resource, place, route, object, or opportunity |
| `plan_outcome` | Plan success, failure, or final result |

## Duplicate rule

Before appending, compare with the latest memory line.

Skip if the new summary has the same main subject and same main fact.

Do not append just because wording differs.

## Length rule

Keep `summary` short.

Good:

```json
{"summary":"Alice offered to meet at the library after lunch."}
```

Bad:

```json
{"summary":"I observed Alice, who was nearby, and then she said many things about possibly meeting later at the library, which may be important because..."}
```
