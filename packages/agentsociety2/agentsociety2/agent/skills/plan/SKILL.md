---
name: plan
description: Execute the current intention via codegen. Use when acting on state/intention.json against the environment.
---

# Plan

Convert the current intention into exactly one concrete environment action for this tick via `codegen`.

This skill is a tick-level action controller. It does not complete the whole goal at once. After one meaningful action, stop.

## Inputs

| File                    | Use                                             |
| ----------------------- | ----------------------------------------------- |
| `state/intention.json`  | Current goal or intention                       |
| `state/observation.txt` | Available actions, context, affordances         |
| `state/needs.json`      | Optional authoritative need levels              |
| `state/emotion.json`    | Optional `needs` snapshot if needs.json missing |
| `state/plan_state.json` | Multi-step progress, System 2 only              |

## Core rules

- Produce at most one meaningful environment action per tick.
- Actions must match available actions in `state/observation.txt`.
- Never invent unavailable actions.
- After `codegen` returns `success` or `in_progress`, stop with `done`.
- Do not observe again in the same tick.
- `done` means the current tick is complete, not necessarily that the intention is complete.

## Priority override

If `safety`, `energy`, or `satiety` is below `0.2`, address the critical need first when possible. Read levels from `state/needs.json` when present; otherwise use `state/emotion.json` → `needs` or need hints in `state/observation.txt`.

Priority:

1. Safety
2. Energy
3. Satiety

If an existing multi-step plan can be resumed later, mark it as `interrupted`, not `failed`.

## Mode selection

Default to System 1.

Use System 1 when the next action is routine, obvious, or urgent.

Use System 2 only when the goal requires multiple ticks, has uncertainty, involves conflict, or needs step tracking.

## System 1

For simple goals:

1. Read intention and observation.
2. Choose one available action.
3. Call `codegen` once.
4. Stop with `done`.

Do not create `state/plan_state.json`.

## System 2

For multi-step goals:

1. Read or create `state/plan_state.json`.
2. Keep the plan within 6 steps.
3. Execute only the current step via `codegen`.
4. Update plan status if needed.
5. Stop after one action.

Advance `current_step` only when the latest observation confirms the previous step is complete.

## Failure handling

If `codegen` fails:

- Retry at most once with a clearly different available action.
- If still blocked, stop with `done` and record the failure.
- After 3 consecutive failures on the same step, mark the plan as `failed`.

Self-check (optional): `python scripts/validate_plan_state.py state/plan_state.json`

For details, use:

- `references/decision_rules.md`
- `references/plan_state_schema.json`
- `references/examples.md`
