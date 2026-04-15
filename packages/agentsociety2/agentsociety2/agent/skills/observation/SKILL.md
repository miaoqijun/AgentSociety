---
name: observation
description: Fetch current environment perception.
outputs:
  - state/observation.txt
  - state/observation_ctx.json
---

# Observation

Fetch the latest sensory perception for the current tick—what you can see, hear, and perceive around you.

## Activation

Activate early in each tick to ground yourself in the environment.

## Output Files

### state/observation.txt

Natural language description of perception:
- Location (building, street, area)
- Nearby agents and objects
- Environmental context (time, weather)
- Available actions

### state/observation_ctx.json

Structured environment data:

```json
{
  "position": {"x": 100, "y": 200},
  "location": "park_entrance",
  "nearby_agents": [{"id": 2, "name": "Alice", "distance": 5.2}],
  "nearby_objects": [{"id": "bench_01", "type": "bench"}],
  "time": {"hour": 10, "minute": 30},
  "weather": "sunny",
  "available_actions": ["move", "interact", "wait"]
}
```

## Workflow

1. Call `codegen` with `instruction: "<observe>"` and `ctx: {"id": <agent_id>}`
2. Parse response:
   - `stdout`: observation text
   - `ctx`: structured data
3. Write to workspace:
   - `workspace_write("state/observation.txt", stdout)`
   - `workspace_write("state/observation_ctx.json", ctx)`
4. If `status: "in_progress"`, call `done` and resume next tick

## Re-observation

After any action, re-observe to update state:

```
1. codegen("Move to café") → response
2. codegen("<observe>") → new observation
3. Update state/observation.txt
```

## Guidelines

- Write observation every time you observe
- Handle errors gracefully—write a note to observation.txt
- The `ctx` JSON may be large; write it to file rather than memorizing

## Notes

- This skill only produces observation artifacts
- Higher-level state tracking is handled by other skills
- Skip if `codegen` fails—write error note instead
