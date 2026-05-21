# Cognition Policy

## Purpose

Cognition converts perception and memory into internal state:

```text
observation + needs + memory + profile/state + plan status
    -> emotion.json + intention.json
```

It should answer two questions:

1. What is the agent feeling or needing now?
2. What should the agent try to do next?


## Needs source of truth

If `state/needs.json` exists, it is the authoritative source for need values.

Cognition should:

1. read `state/needs.json`
2. copy or merge those values into `emotion.needs`
3. use them to decide mood and intention priority
4. avoid writing conflicting need values elsewhere

`emotion.needs` is a cognition snapshot. It is useful for debugging and downstream reasoning, but it should not become an independent competing state store.

Only write `state/needs.json` if the runtime explicitly defines cognition as the owner of need updates. Otherwise, need updates belong to the environment or person state manager.

## Intention stability

Do not replace the current intention every tick.

Keep the current intention when:

- it is still relevant
- it is not blocked
- no critical need overrides it
- the current plan is making progress

Revise or replace the intention when:

- safety, energy, or satiety becomes critical
- the plan failed or is blocked
- a new obligation or opportunity is clearly more important
- the observation contradicts the old goal
- the old goal has already been achieved

## Critical need policy

If a critical need is below `0.2`, intention should usually address that need.

Priority order:

1. Safety
2. Energy
3. Satiety

Examples:

- `safety < 0.2` -> find safety, avoid danger, call for help
- `energy < 0.2` -> rest or sleep
- `satiety < 0.2` -> eat available food or seek food

## Emotion policy

Emotion should be a compact state summary, not a diary.

Good `mood` values include:

- calm
- focused
- curious
- tired
- hungry
- anxious
- concerned
- frustrated
- satisfied
- uncertain

Use `drivers` to explain the main causes.

## Intention type

`goal` should be actionable but not a low-level command.

Good:

```json
{"goal":"find food nearby"}
```

Bad:

```json
{"goal":"codegen('eat bread')"}
```

`plan` decides exact environment commands later.

## Priority values

Use:

- `critical`: safety, energy, or satiety emergency
- `high`: important obligation, blocked plan recovery, major opportunity
- `medium`: normal current goal
- `low`: optional exploration or minor preference

## Source values

Use:

- `need`
- `observation`
- `memory`
- `plan`
- `social`
- `profile`
- `user`
