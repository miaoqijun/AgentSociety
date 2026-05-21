# Examples

## Example 1: meaningful social interaction

Context:

```text
Observation: Alice is at the park. She says she knows about a library job opening.
```

Memory:

```json
{"tick":42,"time":"2024-01-15T10:30:00","type":"social","summary":"Alice mentioned a library job opening at the park.","tags":["alice","park","job"],"importance":"medium"}
```

## Example 2: critical need and plan interruption

Context:

```text
energy: 0.12
The agent interrupted the grocery plan to sleep.
```

Memory:

```json
{"tick":43,"type":"plan","summary":"Interrupted the grocery plan because energy was critically low.","tags":["energy","grocery_plan","interruption"],"importance":"medium"}
```

## Example 3: discovery

Context:

```text
Observation: A supermarket entrance is visible to the north.
```

Memory:

```json
{"tick":44,"type":"discovery","summary":"Found a supermarket entrance to the north.","tags":["supermarket","entrance","north"],"importance":"medium"}
```

## Example 4: plan outcome

Context:

```text
The agent paid for groceries and left the store.
```

Memory:

```json
{"tick":50,"type":"plan_outcome","summary":"Completed the grocery shopping plan and paid successfully.","tags":["groceries","payment","completed"],"importance":"high"}
```

## Example 5: skip duplicate

Latest memory:

```json
{"tick":42,"type":"social","summary":"Alice mentioned a library job opening at the park.","tags":["alice","park","job"],"importance":"medium"}
```

New context:

```text
Alice is still at the park. The library job was mentioned again.
```

Action:

```text
done
```

Reason:

```text
The new fact duplicates the latest memory line.
```

## Example 6: skip routine tick

Context:

```text
Observation: The agent is still walking along the same road. No new objects or interactions.
```

Action:

```text
done
```

Reason:

```text
Routine movement without new facts is not worth storing.
```
