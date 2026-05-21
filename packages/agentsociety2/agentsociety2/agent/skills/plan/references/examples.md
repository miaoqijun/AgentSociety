# Examples

These examples show how to convert an intention into one action for the current tick.

## Example 1: System 1 routine action

Use System 1 when the next action is obvious and does not require multi-step tracking.

Intention:

```json
{
  "goal": "reduce hunger"
}
```

Observation:

```text
satiety: 0.15

Available actions:
- eat bread
- drink water
- walk north
```

Action:

```text
codegen("eat bread")
done
```

Reason:

```text
Satiety is critically low, and "eat bread" is directly available.
No plan_state.json is needed.
```

## Example 2: System 2 multi-step goal

Use System 2 when the goal requires progress across multiple ticks.

Intention:

```json
{
  "goal": "buy groceries"
}
```

Observation:

```text
Available actions:
- walk to supermarket
- talk to passerby
- sit down
```

Plan state:

```json
{
  "goal": "buy groceries",
  "steps": [
    "go to supermarket",
    "enter supermarket",
    "pick groceries",
    "pay"
  ],
  "current_step": 0,
  "started_tick": 42,
  "status": "in_progress",
  "decision_mode": "system2",
  "failure_count": 0,
  "last_error": null
}
```

Action:

```text
codegen("walk to supermarket")
done
```

Reason:

```text
Only the current step is executed.
Do not advance current_step until the next observation confirms arrival.
```

## Example 3: interruption by critical need

Current plan:

```json
{
  "goal": "buy groceries",
  "steps": [
    "go to supermarket",
    "enter supermarket",
    "pick groceries",
    "pay"
  ],
  "current_step": 0,
  "started_tick": 42,
  "status": "in_progress",
  "decision_mode": "system2",
  "failure_count": 0,
  "last_error": null
}
```

Observation:

```text
energy: 0.1

Available actions:
- sleep
- sit down
- walk to supermarket
```

Updated plan state:

```json
{
  "goal": "buy groceries",
  "steps": [
    "go to supermarket",
    "enter supermarket",
    "pick groceries",
    "pay"
  ],
  "current_step": 0,
  "started_tick": 42,
  "status": "interrupted",
  "decision_mode": "system2",
  "failure_count": 0,
  "last_error": null,
  "interrupt_reason": "energy below 0.2",
  "resumable": true,
  "resume_conditions": "energy above 0.5"
}
```

Action:

```text
codegen("sleep")
done
```

Reason:

```text
Energy is critically low, so the current plan is interrupted.
The plan is resumable, so it is not marked as failed.
```

## Example 4: unavailable action

Intention:

```json
{
  "goal": "buy groceries"
}
```

Observation:

```text
Available actions:
- sit down
- talk to passerby
- walk north
```

Bad action:

```text
codegen("walk to supermarket")
```

Reason:

```text
"walk to supermarket" is not listed in available actions.
```

Better action:

```text
codegen("walk north")
done
```

Reason:

```text
The action must match the available actions.
If the route is unclear, take one available exploratory action or stop with blockage noted.
```
