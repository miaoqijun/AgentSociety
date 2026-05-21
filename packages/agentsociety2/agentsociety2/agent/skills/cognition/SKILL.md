---
name: cognition
description: Update internal emotion and intention from observation, needs, memory, and recent plan state. Use after observation and before planning/action.
---

# Cognition

Convert the current observation and internal context into updated emotional state and a current intention.

This skill thinks and chooses goals. It does not execute environment actions.

## Inputs

| File                         | Use                                             |
| ---------------------------- | ----------------------------------------------- |
| `state/observation.txt`      | Current world context and available affordances |
| `state/observation_ctx.json` | Structured observation, optional                |
| `state/needs.json`           | Authoritative need values when present          |
| `state/memory.jsonl`         | Recent and relevant past facts                  |
| `state/plan_state.json`      | Current multi-step plan status, optional        |
| Agent profile/state          | Stable traits, preferences, role, and identity  |

## Outputs

| File                   | Use                                                       |
| ---------------------- | --------------------------------------------------------- |
| `state/emotion.json`   | Current emotion plus a copied or inferred need assessment |
| `state/intention.json` | Current goal for planning/action                          |

`state/needs.json` remains the source of truth for needs when it exists. `emotion.needs` is a snapshot used for reasoning and debugging, not a second independent needs store.

## Core rules

- Produce cognition artifacts only; do not call environment actions.
- Ground emotion and intention in the latest observation and relevant memory.
- Critical needs override ordinary goals.
- Preserve a valid ongoing intention if it is still relevant and not blocked.
- Replace the intention only when a stronger need, new opportunity, failure, or conflict justifies it.
- Keep outputs short and machine-readable.

## Priority

When needs conflict, use this order:

1. Safety
2. Energy
3. Satiety
4. Social or role obligations
5. Long-term goals
6. Curiosity or optional exploration

If `safety`, `energy`, or `satiety` is below `0.2`, set an intention to address it when possible.

## Workflow

1. Read `state/observation.txt`.
2. Read `state/observation_ctx.json` if present.
3. Read recent memory lines if useful.
4. Read existing `state/plan_state.json` if present.
5. Read `state/needs.json` if present.
6. Merge need values into `emotion.needs`; do not invent conflicting values.
7. Assess emotion and intention priority from needs, observation, memory, and plan state.
8. Decide whether to keep, revise, or replace the current intention.
9. Write `state/emotion.json`.
10. Write `state/intention.json`.
11. Stop with `done`.

## emotion.json

```json
{
  "tick": 42,
  "mood": "concerned",
  "needs": {
    "safety": 0.8,
    "energy": 0.35,
    "satiety": 0.15
  },
  "drivers": ["satiety is critically low", "food is available nearby"]
}
```

## intention.json

```json
{
  "tick": 42,
  "goal": "eat available food",
  "reason": "satiety is critically low and food is available",
  "priority": "critical",
  "source": "need"
}
```

## Constraints

- Do not write `state/plan_state.json`.
- Do not append memory here; use the memory skill.
- Do not write `state/needs.json` unless the runtime explicitly assigns need maintenance to cognition.
- If `state/needs.json` exists, treat it as authoritative and copy or merge it into `emotion.needs`.
- Do not invent unavailable facts.
- Avoid long explanations in JSON fields.
- Keep `goal` actionable but not an environment command.

Self-check (optional): `python scripts/validate_cognition.py state`

For details, use:

- `references/cognition_policy.md`
- `references/intention_schema.json`
- `references/emotion_schema.json`
- `references/examples.md`
