---
name: memory
description: Long-term memory with automatic forgetting and relationship tracking.
inputs:
  - state/observation.txt
outputs:
  - state/memory.jsonl
  - state/relationships.json
---

# Memory

Long-term memory system with automatic forgetting (Ebbinghaus curve) and relationship tracking.

## Architecture

### 1. Working Context (implicit)
- Recent tool-loop messages + workspace files
- Immediate reasoning; no separate buffer

### 2. Long-term Store (`state/memory.jsonl`)
- JSONL with automatic forgetting
- Persist events, decisions, relationships, beliefs

### 3. Relationship Store (`state/relationships.json`)
- Social relationship tracking
- Trust, familiarity, affection per agent

## Forgetting Curve

### Retention Formula

```
retention = e^(-t / (S x importance_multiplier))
```

- `t`: ticks since creation
- `S`: strength coefficient (default: 100)
- `importance_multiplier`: high=1.5, medium=1.0, low=0.5

### Decay Rules

| Retention | Status | Behavior |
|-----------|--------|----------|
| > 0.5 | Active | Fully accessible |
| 0.1-0.5 | Fading | Marked `_faded: true` |
| < 0.1 | Forgotten | Removed |

### Reinforcement

- Each access adds +0.1 to retention (max 0.95)
- `_access_count` tracks access frequency

### Emotional Reinforcement

Memories with strong emotions are retained longer:

| Emotion Intensity | Retention Bonus |
|-------------------|-----------------|
| > 8 (extreme) | +0.3 |
| 6-8 (strong) | +0.2 |
| 4-6 (moderate) | +0.1 |
| < 4 (weak) | No bonus |

### Spacing Effect

Repeated access over time strengthens memory more than mass access:

| Access Pattern | Strength Multiplier |
|----------------|---------------------|
| Massed (same tick) | 1.0x |
| Distributed (1 tick apart) | 1.2x |
| Distributed (5+ ticks apart) | 1.5x |

## Memory Entry Types

| Type | Use Case |
|------|----------|
| `event` | General occurrence |
| `observation` | Notable perception |
| `decision` | Significant choice made |
| `plan` | Plan created or revised |
| `plan_outcome` | Step completed or failed |
| `belief` | Belief about world/agent/self |
| `social` | Relationship-relevant interaction |
| `emotion` | Strong emotional experience |

### Belief Subtypes

| Subtype | Example |
|---------|---------|
| `belief:world` | "The café opens at 8am" |
| `belief:agent` | "Alice is generous" |
| `belief:self` | "I am good at cooking" |

## Relationship System

### Dimensions

| Dimension | Range | Description |
|-----------|-------|-------------|
| `trust` | 0.0-1.0 | How much you trust them |
| `familiarity` | 0.0-1.0 | How well you know them |
| `affection` | -1.0-1.0 | Positive/negative feeling |

### Relationship Types

| Type | Trust | Familiarity | Description |
|------|-------|-------------|-------------|
| `stranger` | < 0.2 | < 0.2 | Never or barely met |
| `acquaintance` | >= 0.2 | >= 0.2 | Limited interaction |
| `friend` | >= 0.5 | >= 0.4 | Regular positive contact |
| `close_friend` | >= 0.7 | >= 0.6 | Deep connection |
| `enemy` | < 0.2 | >= 0.3 | Known adversary |

### Interaction Impact

| Interaction | Trust Δ | Familiarity Δ | Affection Δ |
|-------------|---------|---------------|-------------|
| Positive conversation | +0.05 | +0.03 | +0.05 |
| Collaboration success | +0.10 | +0.05 | +0.08 |
| Help received | +0.15 | +0.05 | +0.12 |
| Conflict | -0.10 | +0.02 | -0.15 |
| Betrayal | -0.30 | +0.05 | -0.40 |

### Natural Decay

- Trust: -0.01 per tick
- Familiarity: -0.02 per tick
- Affection: drifts toward 0

## Output Files

### state/memory.jsonl

```json
{"tick": 42, "time": "2024-01-15T10:30:00", "type": "social", "summary": "Had coffee with Alice. She mentioned the new project.", "tags": ["alice", "coffee", "project"], "importance": "medium"}
```

### state/relationships.json

```json
{
  "agents": {
    "2": {
      "name": "Alice",
      "trust": 0.75,
      "familiarity": 0.50,
      "affection": 0.60,
      "relation": "friend",
      "last_interact": "2024-01-15T10:30:00"
    }
  },
  "updated_at": "2024-01-15T10:30:00"
}
```

## When to Write

**Write when:**
- Meaningful interaction occurred
- Important discovery made
- Significant decision taken
- Strong emotion experienced
- Relationship status changed

**Skip when:**
- Nothing notable happened
- Information duplicates recent entry

## Workflow

1. Read existing memory.jsonl and relationships.json
2. Apply forgetting curve (remove decayed entries)
3. Evaluate what's worth remembering
4. Update relationships based on interactions
5. Append new memory entry if notable
6. Write output files

## Configuration

- `AGENT_MEMORY_STRENGTH`: Memory strength (default: 100)
- `AGENT_MEMORY_MAX_ENTRIES`: Max memories (default: 1000)
