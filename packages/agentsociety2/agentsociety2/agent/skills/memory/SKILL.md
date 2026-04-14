---
name: memory
description: Persist important outcomes from this step to long-term storage with automatic forgetting curve.
outputs:
  - state/memory.jsonl
---

# Memory

You are the agent's long-term memory system with automatic forgetting based on the Ebbinghaus curve. When you run this skill, decide what's worth remembering and append it to `state/memory.jsonl`.

## Architecture (conceptual)

Three layers:

### 1. Working context (implicit)

- **What**: Recent tool-loop messages plus any workspace files you choose to read in this step.
- **Purpose**: Immediate reasoning; there is no separate hidden memory buffer beyond workspace + thread.
- **Usage**: Read only files that exist; skip missing paths.

### 2. Long-term store (`state/memory.jsonl`)

- **What**: JSONL in the agent workspace with automatic forgetting.
- **Purpose**: Persist what should survive across ticks (events, decisions, plan outcomes).
- **Forgetting**: Old memories fade and are eventually removed (see Forgetting Curve below).
- **Reinforcement**: Frequently accessed memories are reinforced and last longer.

### 3. Optional "step bundle" (convention)

- If you want one rich JSONL line per tick, you may bundle highlights into `summary` from whatever files you read in this step-purely optional.

## Forgetting Curve (Ebbinghaus Model)

Memories naturally decay over time following the Ebbinghaus forgetting curve:

### Retention Formula

```
retention = e^(-t / (S x importance_multiplier))
```

Where:
- `t` = ticks since memory creation
- `S` = memory strength coefficient (default: 100 ticks, configurable via `AGENT_MEMORY_STRENGTH` env var)
- `importance_multiplier` = high: 1.5, medium: 1.0, low: 0.5

### Decay Rules

| Retention Level | Status | Behavior |
|-----------------|--------|----------|
| `retention > 0.5` | Active | Memory is fully accessible |
| `0.1 < retention < 0.5` | Fading | Memory marked as `_faded: true` |
| `retention < 0.1` | Forgotten | Memory is removed from the store |

### Reinforcement

When a memory is accessed (via `grep` or explicit read), it gets reinforced:
- Each access adds `+0.1` to retention (max `0.95`)
- The `_access_count` field tracks access frequency
- This models how "recalling strengthens memory"

### Memory Limits

To prevent unbounded growth:
- Default maximum: 1000 entries (configurable via `AGENT_MEMORY_MAX_ENTRIES`)
- When over limit, lowest-retention memories are removed first

## Importance Guidelines

When writing memories, set `importance` appropriately:

| Importance | Use Case | Retention (approx) |
|------------|----------|-------------------|
| `high` | Life-changing events, critical decisions, major discoveries | ~150 ticks |
| `medium` | Notable events, moderate decisions (default) | ~100 ticks |
| `low` | Minor observations, routine activities | ~50 ticks |

**Tip**: Set `importance: high` for memories that should persist across the entire simulation.

## Entry `type` values (recommended)

Use `type` to help future `grep` / manual scanning:

| Type | When it applies | Example |
|------|------------------|---------|
| `need` | After notable need change | "Satiety dropped; decided to find food" |
| `emotion` | After strong emotion / regulation | "Relieved after plan succeeded" |
| `cognition` | Thought / appraisal update | "Reframed delay as acceptable" |
| `intention` | Intention changed | "Switched intention to head home" |
| `plan` | Plan created or revised | "New plan: 3 steps to reach clinic" |
| `react` | Notable environment interaction | "codegen: move to cafe" |
| `plan_execution` | Step finished or failed | "Step 'walk to cafe' completed" |
| `event` | General occurrence | "Met Alice; she mentioned the job" |
| `observation` | Notable perception to recall later | Short summary of what you saw / heard |
| `social` / `decision` / `discovery` / `plan_outcome` | As in the table below |

Use **`type`** + **`tags`** so grep and tail-scans stay useful.

## When to Write a Memory

**Write a memory when:**
- You had a meaningful interaction (conversation, transaction, conflict)
- You discovered something new (a new location, a new agent, useful information)
- An important state change occurred (need became critical, plan completed/failed)
- You made a significant decision (changed plans, formed an opinion)
- Something emotionally notable happened

**Skip memory when:**
- Nothing happened (idle tick, walking without events)
- The observation is essentially the same as last tick
- The information is already captured in a recent memory entry

## Memory Entry Format

Each entry is a single JSON line in `state/memory.jsonl`:

```json
{"tick": 42, "time": "2024-01-15T10:30:00", "type": "event", "summary": "Met Alice at the park. She mentioned a job opening at the library.", "tags": ["social", "alice", "job"], "importance": "medium"}
```

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `tick` | int | Current tick number (from the step context) |
| `time` | string | ISO format timestamp |
| `type` | string | Category - see Memory Types below |
| `summary` | string | 1-2 sentence factual description of what happened |
| `tags` | list | 2-5 short keywords for retrieval (agent names, locations, topics) |
| `importance` | string | `high` (life-changing), `medium` (notable), `low` (minor) |

## How to Write

1. Optionally `workspace_read` any relevant context files.
2. Decide if anything is worth remembering (see criteria above).
3. If yes, construct the memory entry and append:

```json
{
  "tool_name": "workspace_write",
  "arguments": {
    "path": "state/memory.jsonl",
    "content": "<existing content>\n<new JSON line>"
  }
}
```

**Important**: Since `workspace_write` overwrites the file, first `workspace_read("state/memory.jsonl")` to get existing content, then append the new entry.

4. If nothing notable happened, call `done` immediately.

## Memory Retrieval

Readers of `state/memory.jsonl` typically scan the last few lines for recent context.

### Reading Recent Memories

Focus on the most recent entries (last 5-10) when you need continuity.

### Searching older memories

Use `grep` on `state/memory.jsonl` to search for names or tags.

## Maintenance Script

Run periodically to apply forgetting curve:

```bash
python scripts/memory_maintenance.py \
  --memory-file state/memory.jsonl \
  --current-tick 100
```

Configuration via environment variables:
- `AGENT_MEMORY_STRENGTH`: Memory strength coefficient (default: 100)
- `AGENT_MEMORY_MAX_ENTRIES`: Maximum memories to keep (default: 1000)

## Guidelines

- Keep summaries **concise** (1-2 sentences max). This is a log, not a diary.
- Use **specific names and locations**, not vague references.
- Don't duplicate information already in the most recent memory entry.
- **Timestamp all entries** for temporal reasoning.
- **Tag entries** with relevant keywords for efficient retrieval.
- Set **importance** based on how long the memory should persist.
