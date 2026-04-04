---
name: relationship
description: Maintain and update social relationships with other agents.
outputs:
  - state/relationships.json
---

# Relationship

Maintain and update social relationships with other agents in the simulation.

## Understanding Social Relationships

As a person, you have **relationships** with other agents that evolve over time through interactions. These relationships influence your social decisions, emotional responses, and memory prioritization.

## When to Use

Activate this skill when:
- You have interacted with another agent (conversation, collaboration, conflict)
- You have observed another agent's behavior
- You want to recall your relationship with someone before interacting
- Time has passed and relationships may need decay adjustment

## Input Files (optional, read if present)

| File | Use |
|------|-----|
| `observation.txt` | Current perception containing other agents |
| `memory.jsonl` | Recent interactions to extract relationship updates |
| `state/relationships.json` | Existing relationship state to update |

## Relationship Dimensions

Each relationship has multiple dimensions:

| Dimension | Range | Description |
|-----------|-------|-------------|
| `trust` | 0.0–1.0 | How much you trust this person |
| `familiarity` | 0.0–1.0 | How well you know them |
| `affection` | -1.0–1.0 | Positive/negative feelings toward them |
| `relation` | string | Relationship type: `stranger`, `acquaintance`, `friend`, `close_friend`, `enemy` |

## Relationship Types

| Type | Trust Threshold | Familiarity Threshold | Description |
|------|-----------------|----------------------|-------------|
| `stranger` | < 0.2 | < 0.2 | Never or barely met |
| `acquaintance` | >= 0.2 | >= 0.2 | Know of them, limited interaction |
| `friend` | >= 0.5 | >= 0.4 | Regular positive interactions |
| `close_friend` | >= 0.7 | >= 0.6 | Deep connection and trust |
| `enemy` | < 0.2 | >= 0.3 | Negative relationship, known adversary |

## Natural Decay

Relationships weaken over time without interaction:

- Trust decays: -0.01 per tick (slow)
- Familiarity decays: -0.02 per tick (moderate)
- Affection drifts toward 0: -0.01 per tick (regression to neutral)

## Interaction Impact

| Interaction Type | Trust Δ | Familiarity Δ | Affection Δ |
|-----------------|---------|---------------|-------------|
| Positive conversation | +0.05 | +0.03 | +0.05 |
| Collaboration success | +0.10 | +0.05 | +0.08 |
| Help received | +0.15 | +0.05 | +0.12 |
| Conflict | -0.10 | +0.02 | -0.15 |
| Betrayal | -0.30 | +0.05 | -0.40 |
| Neutral interaction | +0.01 | +0.02 | 0 |

## What to Do

1. `workspace_read("state/relationships.json")` if exists (skip if missing)
2. `workspace_read("observation.txt")` if exists to detect interactions
3. `workspace_read("memory.jsonl")` last 5-10 lines for recent interaction context
4. Update relationship entries based on interactions
5. Apply natural decay to all relationships
6. `workspace_write("state/relationships.json", ...)` with updated state
7. `done`

## Output File Schema

### relationships.json

```json
{
  "agents": {
    "2": {
      "name": "Alice",
      "trust": 0.75,
      "familiarity": 0.50,
      "affection": 0.60,
      "relation": "friend",
      "last_interact": "2024-01-15T10:30:00",
      "interact_count": 12
    },
    "3": {
      "name": "Bob",
      "trust": 0.15,
      "familiarity": 0.10,
      "affection": -0.20,
      "relation": "stranger",
      "last_interact": null,
      "interact_count": 0
    }
  },
  "groups": ["book_club", "neighbors"],
  "updated_at": "2024-01-15T10:30:00"
}
```

## Update Triggers

Update relationships after:
- Any direct conversation or interaction
- Observing another agent's behavior toward you
- Hearing about another agent from third parties
- Significant time passage (decay)

## Notes

- Use agent IDs (numbers) as keys in the `agents` dict
- `last_interact` uses ISO format timestamp
- Groups are optional social categories the agent belongs to
- Relationships with `relation: "enemy"` still track familiarity (you know your enemies)
