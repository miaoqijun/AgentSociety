# Decision Rules

## System 1

Use System 1 when:

- the action is routine
- the next step is obvious
- the goal can likely be advanced with one available action
- there is an urgent need with a known fix

Examples:

- eat available food
- rest when tired
- move to a visible nearby location
- talk to a nearby person
- pick up a visible object

System 1 should not create or modify `state/plan_state.json`.

## System 2

Use System 2 when:

- the goal needs multiple ticks
- the path is uncertain
- the goal has dependencies
- the goal may conflict with another need
- progress must be remembered

Examples:

- buy groceries
- travel to a distant place
- complete a work task
- coordinate with another agent
- escape danger through multiple steps

## Critical need override

Critical needs override the current intention.

Priority order:

1. Safety
2. Energy
3. Satiety

If a critical need interrupts an existing plan:

- use `interrupted` if the plan can continue later
- use `failed` only if the original goal is no longer possible

## Step advancement

Do not advance `current_step` just because `codegen` succeeded.

Advance only when observation confirms the step is complete.

Example:

- `codegen("walk to supermarket")` returns success
- The agent may still be walking
- Wait for the next observation
- Advance only if the next observation shows the agent is at the supermarket
