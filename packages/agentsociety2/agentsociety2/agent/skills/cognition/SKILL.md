---
name: cognition
description: Core cognitive skill producing emotion, needs, and intention from context.
inputs:
  - state/observation.txt
outputs:
  - state/emotion.json
  - state/needs.json
  - state/intention.json
---

# Cognition

Core cognitive skill that integrates perception, needs, emotions, and intentions.
Produces `state/emotion.json`, `state/needs.json`, and `state/intention.json`.

## Activation

Activate this skill early in each tick to establish emotional state and current goal.

## Input Files (optional)

| File | Use |
|------|-----|
| `state/observation.txt` | Current environment perception |
| `state/memory.jsonl` | Last 5-10 lines for continuity |
| `state/emotion.json` | Prior state for continuity |
| `state/intention.json` | Prior intention |

## Output Files

### state/emotion.json

Emotional state with three layers:

```json
{
  "primary": "Hope",
  "valence": 0.5,
  "arousal": 0.4,
  "mood": {
    "valence": 0.2,
    "arousal": 0.5,
    "stability": 0.7
  },
  "intensities": {
    "sadness": 3,
    "joy": 6,
    "fear": 2,
    "disgust": 1,
    "anger": 1,
    "surprise": 3
  },
  "note": "I should grab lunch soon. Feeling pretty good about the morning."
}
```

### state/needs.json

Physiological and social needs:

```json
{
  "satiety": 0.72,
  "energy": 0.65,
  "safety": 0.80,
  "social": 0.45,
  "current_need": "satiety",
  "thresholds": {"satiety": 0.2, "energy": 0.2, "safety": 0.2, "social": 0.3},
  "should_interrupt_plan": false
}
```

### state/intention.json

Current goal with TPB scores:

```json
{
  "intention": "Have lunch at the café",
  "priority": 1,
  "attitude": 0.9,
  "subjective_norm": 0.7,
  "perceived_control": 0.8,
  "reasoning": "Satiety is dropping, it's lunch time."
}
```

## Need System

### Need Dimensions

| Need | Range | Threshold | Description |
|------|-------|-----------|-------------|
| `satiety` | 0.0-1.0 | 0.2 | Hunger satisfaction |
| `energy` | 0.0-1.0 | 0.2 | Physical energy |
| `safety` | 0.0-1.0 | 0.2 | Security (physical, financial) |
| `social` | 0.0-1.0 | 0.3 | Social fulfillment |

### Natural Decay

Per-tick decay rates:

| Need | Decay | Notes |
|------|-------|-------|
| `satiety` | -0.02 | Constant decay |
| `energy` | -0.03 | Higher during activity |
| `safety` | varies | Based on environment threats |
| `social` | varies | Based on interaction history |

### Time-Based Decay Multipliers

Decay rates vary by time of day (realistic circadian effects):

| Need | Time Period | Multiplier | Reason |
|------|-------------|------------|--------|
| `satiety` | 06:00-09:00 | 1.5× | Breakfast time, hungrier |
| `satiety` | 11:00-13:00 | 1.8× | Lunch time |
| `satiety` | 18:00-20:00 | 1.6× | Dinner time |
| `energy` | 22:00-06:00 | 0.5× | Night, lower consumption |
| `energy` | 14:00-16:00 | 1.3× | Afternoon slump |
| `social` | 18:00-23:00 | 1.2× | Evening social hours |

### Activity Impact

| Activity | Energy Δ | Satiety Δ | Social Δ | Notes |
|----------|----------|-----------|----------|-------|
| eating | +0.05 | +0.30 | — | Full meal |
| snacking | — | +0.10 | — | Light snack |
| sleeping | +0.20 | -0.02 | — | Full rest |
| resting | +0.10 | — | — | Light rest |
| working | -0.02 | -0.01 | — | Mental work |
| exercising | -0.03 | -0.02 | — | Physical activity |
| socializing | -0.01 | — | +0.05 | Conversation |
| party | -0.02 | -0.01 | +0.10 | Social event |
| reading | -0.005 | — | — | Light mental |
| walking | -0.01 | — | — | Light movement |
| running | -0.02 | — | — | Heavy exercise |

### Need Priority & Interrupt Rules

| Priority | Need | Interrupt Plan? | Condition |
|----------|------|-----------------|-----------|
| 1 (highest) | `satiety` | YES | < 0.2 (critical) |
| 2 | `energy` | YES | < 0.2 (fatigue) |
| 3 | `safety` | NO | < 0.2 (anxiety) |
| 4 | `social` | NO | < 0.3 (loneliness) |
| 5 (lowest) | `whatever` | NO | All needs satisfied |

### Initial Values

Starting values when agent is created:

| Need | Initial | Notes |
|------|---------|-------|
| `satiety` | 0.7 | Recently eaten |
| `energy` | 0.3 | Needs rest soon |
| `safety` | 0.9 | Feeling secure |
| `social` | 0.8 | Socially satisfied |

## Emotion System

### Three-Layer Model

**Layer 1: Emotion** (seconds to minutes)
- Dimensions: sadness, joy, fear, disgust, anger, surprise (0-10)
- Max change: ±2 per tick per dimension

**Layer 2: Mood** (hours to days)
- `valence`: -1 to 1 (positive/negative)
- `arousal`: 0 to 1 (energy level)
- `stability`: 0 to 1 (resistance to change)

**Layer 3: Personality** (long-term, stable)
- Big Five traits from agent profile

### Primary Emotions

Exactly one from: `Joy`, `Distress`, `Fear`, `Hope`, `Satisfaction`, `Disappointment`, `Pride`, `Anger`, `Gratitude`, `Shame`, `Love`, `Hate`, etc.

### Need-Emotion Linkage

| Need Condition | Emotion Effect |
|----------------|----------------|
| satiety < 0.3 | anger +2, joy -1 |
| energy < 0.3 | sadness +1, joy -1 |
| safety < 0.3 | fear +2 |
| social < 0.3 | sadness +1 |

## Intention System (TPB)

### TPB Fields

| Field | Range | Meaning |
|-------|-------|---------|
| `attitude` | 0-1 | Personal favorability |
| `subjective_norm` | 0-1 | Social pressure |
| `perceived_control` | 0-1 | Feasibility confidence |

### Emotion Modifiers

| Emotion | attitude Modifier | perceived_control Modifier |
|---------|-------------------|---------------------------|
| joy > 7 | +0.10 | +0.05 |
| anger > 6 | -0.10 | -0.05 |
| fear > 6 | -0.10 | -0.10 |
| sadness > 6 | -0.05 | -0.05 |

## Personality Modulation

Personality traits modulate needs, emotions, and decisions.

### Big Five Traits

| Trait | Range | High Value | Low Value |
|-------|-------|------------|-----------|
| `openness` | 0.0-1.0 | Curious, creative | Cautious, practical |
| `conscientiousness` | 0.0-1.0 | Organized, disciplined | Flexible, spontaneous |
| `extraversion` | 0.0-1.0 | Outgoing, energetic | Reserved, solitary |
| `agreeableness` | 0.0-1.0 | Cooperative, trusting | Competitive, skeptical |
| `neuroticism` | 0.0-1.0 | Sensitive, volatile | Calm, stable |

### Default Values

Moderate personality (fallback if not specified in profile):

```json
{
  "openness": 0.5,
  "conscientiousness": 0.5,
  "extraversion": 0.5,
  "agreeableness": 0.5,
  "neuroticism": 0.3
}
```

### Personality → Emotion Effects

| Trait Condition | Emotion Effect |
|-----------------|----------------|
| `neuroticism > 0.7` | Amplify all emotions × 1.3 |
| `neuroticism < 0.3` | Cap emotion changes at ±1 per tick |
| `extraversion > 0.7` | Amplify joy, surprise × 1.2 |
| `extraversion > 0.7` | Reduce fear, sadness × 0.8 |
| `agreeableness > 0.7` | Reduce anger responses -2 |
| `agreeableness > 0.7` | Increase joy from cooperation +2 |

### Personality → Need Effects

| Trait Condition | Need Effect |
|-----------------|-------------|
| `extraversion > 0.7` | Social threshold +0.1 (more sensitive) |
| `neuroticism > 0.7` | Safety threshold +0.1 (more anxious) |
| `conscientiousness > 0.7` | Respond to decay earlier (±10%) |
| `openness > 0.7` | More willing to explore, try new things |

### Personality → Intention Effects

| Trait Condition | Intention Bias |
|-----------------|----------------|
| `openness > 0.7` | Prefer novel, exploratory intentions |
| `extraversion > 0.7` | Prefer social intentions |
| `agreeableness > 0.7` | Prefer cooperative, helping intentions |
| `conscientiousness > 0.7` | Prefer structured, goal-oriented intentions |
| `neuroticism > 0.7` | Prefer safety-seeking intentions |

### Text → Trait Mapping

When profile contains personality text, extract traits:

| Keywords | Trait Adjustment |
|----------|-----------------|
| curious, creative, adventurous | openness +0.2 |
| practical, routine-oriented, cautious | openness -0.2 |
| organized, disciplined, reliable | conscientiousness +0.2 |
| spontaneous, flexible, carefree | conscientiousness -0.2 |
| outgoing, social, energetic | extraversion +0.2 |
| reserved, quiet, solitary | extraversion -0.2 |
| cooperative, trusting, helpful | agreeableness +0.2 |
| competitive, critical, skeptical | agreeableness -0.2 |
| anxious, sensitive, moody | neuroticism +0.2 |
| calm, stable, relaxed | neuroticism -0.2 |

## Workflow

1. Read optional input files (skip missing)
2. Load or infer personality traits from profile
3. Update need levels (decay + activity + time multipliers)
4. Update emotion intensities (respect continuity + personality modulation)
5. Generate intention candidates
6. Resolve inner conflicts (if multiple strong candidates)
7. Apply TPB scoring with emotion and personality modifiers
8. Write output files

## Inner Conflict Resolution

Simulate human ambivalence through competing internal drives.

### Conflict Detection

A conflict exists when:

- Multiple intentions have similar TPB scores (difference < 0.1)
- Or urgent need conflicts with ongoing plan
- Or short-term desire conflicts with long-term goal

### Conflict Resolution Strategies

| Strategy | When Used | Example |
|----------|-----------|---------|
| `need_priority` | Physiological need critical | Hunger > socializing |
| `emotion_override` | Strong emotion present | Anger may override logic |
| `habit_wins` | Both options weak | Default to routine |
| `deliberation` | High stakes decision | Generate reasoning, may flip coin |
| `defer` | Both viable, no urgency | Postpone, gather more info |

### Conflict Output

When conflict is detected, add to `intention.json`:

```json
{
  "intention": "Go to café for lunch",
  "priority": 1,
  "conflict": {
    "detected": true,
    "competing_intention": "Continue working on project",
    "resolution": "need_priority",
    "reasoning": "Hunger is critical (satiety=0.15), must eat now"
  }
}
```

## Context Sensitivity

Behavior adapts to situational context.

### Context Factors

| Factor | Impact |
|--------|--------|
| `time_of_day` | Affects energy, appropriate activities |
| `location` | Affects available actions, social expectations |
| `social_context` | Alone vs. with others, affects extraversion expression |
| `recent_events` | Recent successes/failures affect confidence |
| `ongoing_plan` | Commitment to current plan reduces switching |

### Time-Based Context

| Time | Typical State | Appropriate Actions |
|------|---------------|---------------------|
| 06:00-09:00 | Low energy, waking | Morning routine, breakfast |
| 09:00-12:00 | High alertness | Work, study, productive tasks |
| 12:00-14:00 | Moderate, hungry | Lunch, break |
| 14:00-17:00 | Declining alertness | Routine work, meetings |
| 17:00-20:00 | Varied | Transition, dinner, social |
| 20:00-23:00 | Relaxation | Leisure, social, entertainment |
| 23:00-06:00 | Low energy | Sleep, rest |

### Location-Based Context

| Location | Behavior Modifier |
|----------|-------------------|
| `home` | More relaxed, private behaviors OK |
| `workplace` | More formal, productivity-focused |
| `public` | Social awareness heightened |
| `friend's place` | More extraverted, casual |

## Daily Routine

Recognize and respect established routines.

### Routine Detection

Routines form when:

- Same action taken at similar time for 3+ consecutive days
- Action aligns with need satisfaction pattern

### Routine Types

| Routine | Typical Time | Need Addressed |
|---------|--------------|----------------|
| `morning_routine` | 06:00-08:00 | Multiple (hygiene, food) |
| `work_commute` | 08:00-09:00 | Structure |
| `lunch_routine` | 12:00-13:00 | Satiety |
| `evening_routine` | 18:00-20:00 | Social, satiety |
| `sleep_routine` | 22:00-23:00 | Energy recovery |

### Routine Override

Routines may be skipped when:

- Higher priority need emerges
- Unexpected event requires response
- Strong emotion motivates deviation
- Social obligation conflicts

### Routine in Output

Add to `intention.json` when routine is active:

```json
{
  "intention": "Have breakfast",
  "priority": 1,
  "is_routine": true,
  "routine_name": "morning_routine",
  "routine_step": 2
}
```

## Need-Driven Plan Adjustment

Intention should adapt to changing needs.

### Trigger Conditions

| Condition | Action |
|-----------|--------|
| Need drops below threshold | Generate interrupt intention |
| Need declining rapidly | Prepare to act soon |
| Need satisfied unexpectedly | Free up attention for other goals |
| Multiple needs critical | Prioritize by survival importance |

### Interrupt Rules

| Need Level | Interrupt Strength |
|------------|-------------------|
| < 0.1 (critical) | Force immediate action |
| < 0.2 (urgent) | Strong suggestion |
| < 0.3 (concerning) | Consider in next decision |
| > 0.3 | No interrupt |

### Plan Adjustment Output

When current plan conflicts with need:

```json
{
  "intention": "Take a break and eat",
  "priority": 1,
  "plan_adjustment": {
    "original_plan": "Continue working",
    "adjustment_reason": "satiety_critical",
    "resume_plan_after": true,
    "resumable_intention": "Continue working on project"
  }
}
```

## Notes

- Skip missing files gracefully
- Respect emotion continuity rules (max ±2 change)
- Urgent needs (below threshold) should influence intention priority
- The `note` field in emotion.json contains brief inner monologue
- Personality is stable: only change after major life events (rare)
- Routines provide default behavior but can be overridden
- Inner conflicts are normal and should be represented when they occur
