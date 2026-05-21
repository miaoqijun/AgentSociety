# Output Contract

## codegen call

Use the environment observe command exactly once:

```text
codegen(
  instruction: "<observe>",
  ctx: {"id": <your_agent_id>}
)
```

The agent id must come from Agent Identity.

## Expected codegen result

The exact shape may vary, but handle these fields when present:

```json
{
  "status": "success",
  "stdout": "current observation text",
  "ctx": {
    "tick": 42,
    "location": "home",
    "available_actions": ["sleep", "walk north"]
  }
}
```

## Workspace writes

On success:

```text
workspace_write("state/observation.txt", stdout)
```

If structured context is useful:

```text
workspace_write("state/observation_ctx.json", json.dumps(ctx, ensure_ascii=False, indent=2))
```

On error:

```text
workspace_write("state/observation.txt", "Observation failed: <short reason>")
```

Do not fabricate sensory content on failure.

## In-progress result

If `status` is `in_progress`:

- stop with `done`
- resume on the next tick
- do not immediately call observe again
- write partial stdout only if it is explicitly useful and safe to persist

## Ownership

This skill owns only:

- `state/observation.txt`
- `state/observation_ctx.json`
- optional observation lines in `state/memory.jsonl`

It must not modify:

- `state/intention.json`
- `state/plan_state.json`
- environment state except through `<observe>`
