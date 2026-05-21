# Examples

## Example 1: critical hunger

Observation:

```text
satiety: 0.12
Available actions:
- eat bread
- drink water
- walk north
```

emotion.json:

```json
{
  "tick": 12,
  "mood": "hungry",
  "needs": {
    "safety": 0.9,
    "energy": 0.6,
    "satiety": 0.12
  },
  "drivers": ["satiety is critically low", "food is available"]
}
```

intention.json:

```json
{
  "tick": 12,
  "goal": "eat available food",
  "reason": "satiety is critically low and bread is available",
  "priority": "critical",
  "source": "need"
}
```

## Example 2: preserve ongoing plan

Observation:

```text
Location: street near supermarket
Available actions:
- enter supermarket
- walk south
```

plan_state.json:

```json
{
  "goal": "buy groceries",
  "steps": ["go to supermarket", "enter supermarket", "pick groceries", "pay"],
  "current_step": 1,
  "status": "in_progress"
}
```

intention.json:

```json
{
  "goal": "buy groceries",
  "reason": "the grocery plan is still relevant and the next step is available",
  "priority": "medium",
  "source": "plan"
}
```

## Example 3: safety override

Observation:

```text
safety: 0.1
A fire blocks the east road.
Available actions:
- walk west
- call for help
```

intention.json:

```json
{
  "goal": "move away from the fire and seek safety",
  "reason": "safety is critically low due to a nearby fire",
  "priority": "critical",
  "source": "need"
}
```

## Example 4: blocked plan

Observation:

```text
Location: street
Available actions:
- walk west
- ask passerby for directions
```

plan_state.json:

```json
{
  "goal": "buy groceries",
  "steps": ["go to supermarket", "enter supermarket", "pick groceries", "pay"],
  "current_step": 0,
  "status": "in_progress",
  "failure_count": 2
}
```

intention.json:

```json
{
  "goal": "ask for directions to the supermarket",
  "reason": "the grocery plan is still relevant but the route is uncertain",
  "priority": "medium",
  "source": "plan"
}
```

## Example 5: social commitment from memory

Recent memory:

```json
{"type":"social","summary":"Alice asked to meet at the library after lunch.","tags":["alice","library","meeting"],"importance":"high"}
```

Observation:

```text
time: after lunch
Available actions:
- walk to library
- rest
```

intention.json:

```json
{
  "goal": "go to the library to meet Alice",
  "reason": "a high-importance social commitment is due now",
  "priority": "high",
  "source": "memory"
}
```
