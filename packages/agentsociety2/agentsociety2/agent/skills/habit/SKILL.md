---
name: habit
description: Manage daily routines and habitual behaviors for realistic human simulation.
outputs:
  - state/habits.json
---

# Habit

Manage daily routines and habitual behaviors. Habits are automatic behaviors triggered by context (time, location, state) that reduce cognitive load and create realistic daily patterns.

## Understanding Habits

Habits are behaviors that become automatic through repetition. They:
- Trigger automatically when conditions are met
- Reduce decision fatigue for routine activities
- Strengthen with consistent execution
- Weaken when interrupted

## Habit Structure

Each habit has:

```json
{
  "habit_id": "morning_coffee",
  "trigger": {
    "time": "07:00-09:00",
    "location": "home",
    "condition": "energy < 0.5"
  },
  "action": "Make and drink coffee",
  "strength": 0.7,
  "success_count": 15,
  "fail_count": 2,
  "created_tick": 10,
  "last_triggered_tick": 42,
  "auto_execute": true
}
```

### Trigger Conditions

| Condition Type | Example | Description |
|----------------|---------|-------------|
| `time` | "07:00-09:00" | Time window when habit can trigger |
| `location` | "home", "work" | Location requirement |
| `condition` | "energy < 0.5" | State-based condition |
| `after` | "wake_up" | Must follow another habit or event |

### Strength Levels

| Strength | Behavior | Effect |
|----------|----------|--------|
| `> 0.8` | Automatic | Auto-inserted as intention candidate, high priority |
| `0.6-0.8` | Strong | Suggested intention, moderate priority |
| `0.4-0.6` | Moderate | Low priority suggestion |
| `< 0.4` | Weak | Only triggers if no other intentions |

## Habit Formation Rules

### Strengthening

```
strength += 0.05  # After successful execution
```

Max strength: 1.0

### Weakening

```
strength -= 0.02  # After missed trigger opportunity
strength -= 0.05  # After failed execution
```

Min strength: 0.0 (habit is removed)

### Formation Threshold

When `strength > 0.6`, habit becomes "semi-automatic":
- Added to intention candidates automatically
- Requires less cognitive resources
- More resistant to interruption

## Daily Routines

Daily routines are time-based habits that form a daily pattern:

```json
{
  "daily_routine": {
    "wake_time": "07:00",
    "sleep_time": "23:00",
    "meal_times": ["08:00", "12:30", "19:00"],
    "work_start": "09:00",
    "work_end": "18:00"
  }
}
```

### Routine vs Urgency

Daily routines can be interrupted by:
- Critical needs (satiety/energy < 0.2)
- Urgent safety concerns
- Higher-priority intentions

## Input Files (optional)

| File | Use |
|------|-----|
| `state/observation.txt` | Current location and activity |
| `state/needs.json` | Current need states |
| `state/emotion.json` | Current emotional state |
| `state/habits.json` | Existing habits to update |
| `state/intention.json` | Current intention (to check interruption) |

## What to Do

1. `workspace_read("state/habits.json")` if exists
2. `workspace_read("state/observation.txt")` if exists
3. `workspace_read("state/needs.json")` if exists
4. Check for triggered habits based on current context
5. Update habit strengths based on recent execution history
6. Generate intention suggestions for strong triggered habits
7. `workspace_write("state/habits.json", ...)`
8. `done`

## Trigger Evaluation

For each habit, evaluate if trigger conditions are met:

```
triggered = (
    time_match(current_time, habit.trigger.time) AND
    location_match(current_location, habit.trigger.location) AND
    condition_match(current_state, habit.trigger.condition)
)
```

### Time Matching

- "07:00-09:00": Current time within range
- "morning": 06:00-12:00
- "afternoon": 12:00-18:00
- "evening": 18:00-22:00
- "night": 22:00-06:00

### Location Matching

- Exact match: "home" == "home"
- Pattern match: "cafe_*" matches "cafe_main", "cafe_downtown"

### Condition Matching

Evaluate simple expressions:
- "energy < 0.5"
- "satiety > 0.3"
- "social < 0.5"

## Output File Schema

### state/habits.json

```json
{
  "habits": [
    {
      "habit_id": "morning_coffee",
      "trigger": {"time": "07:00-09:00", "location": "home"},
      "action": "Make and drink coffee",
      "strength": 0.75,
      "success_count": 15,
      "auto_execute": true
    },
    {
      "habit_id": "lunch_time",
      "trigger": {"time": "12:00-13:00"},
      "action": "Go to cafeteria",
      "strength": 0.65,
      "auto_execute": false
    }
  ],
  "daily_routine": {
    "wake_time": "07:00",
    "sleep_time": "23:00",
    "meal_times": ["08:00", "12:30", "19:00"]
  },
  "triggered_suggestions": [
    {
      "habit_id": "morning_coffee",
      "intention": "Make coffee",
      "priority": 2,
      "reason": "Morning routine habit (strength: 0.75)"
    }
  ],
  "updated_at": "2024-01-15T07:30:00"
}
```

## Integration with Other Skills

### Cognition Skill

The cognition skill should:
1. Read `state/habits.json` for triggered suggestions
2. Include strong habits (> 0.6 strength) as intention candidates
3. Apply habit strength to TPB attitude score

### Plan Skill

The plan skill should:
1. Check if an intention matches a strong habit
2. For habitual actions, use simplified planning
3. Allow habits to be interrupted by urgent needs

### Memory Skill

The memory skill should:
1. Record habit formation milestones
2. Track habit success/failure patterns
3. Support habit recovery after interruption

## Configuration

Environment variables:
- `AGENT_HABIT_STRENGTH_GAIN`: Strength increase on success (default: 0.05)
- `AGENT_HABIT_STRENGTH_LOSS`: Strength decrease on miss (default: 0.02)
- `AGENT_HABIT_AUTO_THRESHOLD`: Threshold for auto-execute (default: 0.6)
- `AGENT_HABIT_MAX_COUNT`: Maximum habits per agent (default: 20)

## Example Usage

### Creating a New Habit

After performing an action repeatedly, the agent may form a habit:

```json
{
  "tool_name": "workspace_write",
  "arguments": {
    "path": "state/habits.json",
    "content": "{ ... existing habits ... , new habit entry }"
  }
}
```

### Habit Suggestion in Cognition

When evaluating intentions, consider habits:

```json
{
  "intention": "Make coffee",
  "source": "habit:morning_coffee",
  "priority": 2,
  "reasoning": "Morning routine (habit strength: 0.75)"
}
```

## Notes

- Habits should not override critical needs
- Weak habits may fade and be removed
- New habits form slowly (realistic formation)
- Breaking a strong habit requires deliberate effort
