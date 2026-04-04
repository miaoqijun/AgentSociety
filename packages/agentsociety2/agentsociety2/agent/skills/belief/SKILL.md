---
name: belief
description: Maintain and update beliefs about the world, other agents, and self.
outputs:
  - state/beliefs.json
---

# Belief

Maintain and update beliefs about the world, other agents, and yourself.

## Understanding Beliefs

As a person, you have **beliefs** that shape your understanding of the world. These beliefs influence your decisions, intentions, and emotional responses. They can be confirmed, challenged, or revised based on new observations.

## When to Use

Activate this skill when:
- You have observed something that confirms or contradicts an existing belief
- You have learned new information about the world or another agent
- You want to recall what you believe before making a decision
- Significant events warrant belief revision

## Input Files (optional, read if present)

| File | Use |
|------|-----|
| `observation.txt` | Current perception containing new information |
| `memory.jsonl` | Recent events to extract belief updates |
| `state/beliefs.json` | Existing belief state to update |
| `relationships.json` | Context for beliefs about other agents |

## Belief Types

| Type | Subject | Example |
|------|---------|---------|
| `world` | Environment/Facts | "The café opens at 8am" |
| `agent` | Other Agents | "Alice is generous" |
| `self` | Self-perception | "I am good at cooking" |
| `social_norm` | Social rules | "People usually tip 15%" |

## Belief Properties

| Property | Type | Description |
|----------|------|-------------|
| `id` | string | Unique identifier (e.g., "b1", "b2") |
| `type` | string | One of: world, agent, self, social_norm |
| `subject` | string | What/whom the belief is about |
| `predicate` | string | The belief content (for agent/self types) |
| `content` | string | Full statement (for world/social_norm types) |
| `confidence` | 0.0–1.0 | How strongly you hold this belief |
| `source` | string | Origin: observation, memory, inference, communication |
| `last_updated` | string | ISO timestamp of last update |
| `evidence_count` | int | Number of confirming observations |

## Confidence Dynamics

| Event | Confidence Change |
|-------|-------------------|
| Confirming observation | +0.10 |
| Contradicting observation | -0.20 |
| No related observation for 10+ ticks | -0.05 (decay) |
| Multiple confirming observations | +0.05 each (diminishing) |

Beliefs with confidence < 0.2 are automatically removed (forgotten).

## What to Do

1. `workspace_read("state/beliefs.json")` if exists (skip if missing)
2. `workspace_read("observation.txt")` if exists for new information
3. `workspace_read("memory.jsonl")` last 5-10 lines for evidence
4. Update confidence of existing beliefs based on new observations
5. Add new beliefs for novel information
6. Remove beliefs with confidence below threshold
7. `workspace_write("state/beliefs.json", ...)` with updated state
8. `done`

## Output File Schema

### beliefs.json

```json
{
  "beliefs": [
    {
      "id": "b1",
      "type": "agent",
      "subject": "Alice",
      "predicate": "is_generous",
      "confidence": 0.75,
      "source": "observation",
      "last_updated": "2024-01-15T10:30:00",
      "evidence_count": 3
    },
    {
      "id": "b2",
      "type": "world",
      "content": "The park closes at 10pm",
      "confidence": 0.90,
      "source": "memory",
      "last_updated": "2024-01-14T18:00:00",
      "evidence_count": 1
    },
    {
      "id": "b3",
      "type": "self",
      "subject": "self",
      "predicate": "good_at_cooking",
      "confidence": 0.65,
      "source": "inference",
      "last_updated": "2024-01-10T12:00:00",
      "evidence_count": 5
    },
    {
      "id": "b4",
      "type": "social_norm",
      "content": "People usually queue politely at the bakery",
      "confidence": 0.80,
      "source": "observation",
      "last_updated": "2024-01-12T09:00:00",
      "evidence_count": 2
    }
  ],
  "updated_at": "2024-01-15T10:30:00"
}
```

## Belief Update Rules

### Confirmation
When observation aligns with belief:
- Increase confidence
- Increment evidence_count
- Update last_updated

### Contradiction
When observation contradicts belief:
- Decrease confidence more strongly
- If confidence drops below 0.3, consider revising belief content
- If confidence drops below 0.2, remove belief

### New Belief Formation
When observing something novel:
- Create new belief entry
- Set initial confidence based on observation reliability
- Set source appropriately

## Integration with Other Skills

- **cognition**: Beliefs influence emotional responses (violated beliefs → anger)
- **plan**: Beliefs affect decision-making and planning
- **relationship**: Agent beliefs influence trust calculations
- **memory**: Important belief updates should be recorded

## Notes

- Keep beliefs concise and actionable
- Avoid redundant beliefs (similar content, same subject)
- Update `last_updated` even when confidence doesn't change
- Use consistent predicate naming for similar beliefs
