# Memory Rules

Observation memory is optional.

Append to `state/memory.jsonl` only when the observation contains information that should influence later ticks.

## Remember

Good candidates:

- new location or arrival at a goal location
- available resource discovered, such as food, shelter, tools, or people
- hazard, threat, blocked path, or failed perception
- social commitment or instruction from another agent
- task-relevant fact that may not stay visible in later observations

## Do not remember

Avoid memory lines for:

- routine repeated observations
- unchanged nearby objects
- transient text already captured in `state/observation.txt`
- duplicate of the latest memory line
- low-value noise

## Suggested JSONL format

Use one line per memory item:

```json
{"type":"observation","tick":42,"content":"Arrived at the supermarket; entrance is available.","source":"observation"}
```

If the current tick is unknown, omit `tick`.

## Duplicate check

Before appending, compare with the latest memory line.

Do not append if the new content is substantially the same.
