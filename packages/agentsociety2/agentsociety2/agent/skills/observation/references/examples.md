# Examples

These examples show the intended behavior. They are not extra steps to execute.

## Example 1: successful observation

Agent Identity:

```json
{
  "id": "agent_12"
}
```

Call:

```text
codegen(instruction="<observe>", ctx={"id": "agent_12"})
```

Result:

```json
{
  "status": "success",
  "stdout": "Location: kitchen\nAvailable actions:\n- eat bread\n- drink water\n- walk north",
  "ctx": {
    "tick": 10,
    "location": "kitchen",
    "available_actions": ["eat bread", "drink water", "walk north"]
  }
}
```

Writes:

```text
workspace_write("state/observation.txt", stdout)
workspace_write("state/observation_ctx.json", ctx as JSON)
done
```

## Example 2: in progress

Result:

```json
{
  "status": "in_progress",
  "stdout": ""
}
```

Action:

```text
done
```

Reason:

```text
The observation is still running. Do not call observe again in the same tick.
```

## Example 3: failed observation

Result:

```json
{
  "status": "error",
  "stderr": "agent id not found"
}
```

Write:

```text
workspace_write("state/observation.txt", "Observation failed: agent id not found")
done
```

Reason:

```text
The skill records the perception failure but does not invent world state.
```

## Example 4: after an environment action

Previous skill already did:

```text
codegen("walk north")
```

Result:

```json
{
  "status": "success"
}
```

Observation behavior:

```text
Do not observe again in the same tick.
Observe on the next tick instead.
```

## Example 5: optional memory

Observation:

```text
Location: street
A fire blocks the east road.
Available actions:
- walk west
- call for help
```

Optional memory line:

```json
{"type":"observation","content":"A fire blocks the east road.","source":"observation"}
```

Reason:

```text
The hazard may matter beyond the current tick.
```
