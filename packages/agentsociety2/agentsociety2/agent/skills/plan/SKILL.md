---
name: plan
description: Turn the current intention into an environment action for this tick.
inputs:
  - state/intention.json
  - state/observation.txt
  - state/needs.json
  - state/plan_state.json
outputs:
  - state/plan_state.json
---

# Plan

You are the agent's **motor / executive** layer: turn a stated goal into a concrete `codegen` call (and optional `state/plan_state.json` for multi-step work).

## Intention source (no hard deps)

1. If `state/intention.json` exists, use it.
2. Else if `state/thought.txt` or `state/observation.txt` exists, infer a **single short goal line**, write a minimal `state/intention.json` yourself (`intention`, `priority`, `reasoning` fields), then execute.
3. Else use Agent Identity + a conservative default (e.g. `wait` / observe) and still write `state/intention.json` so the workspace stays explicit.

## Configuration

The plan skill has configurable parameters:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `max_plan_steps` | 6 | Maximum number of steps in a generated plan |
| `max_react_interactions_per_step` | 3 | Maximum environment interactions per step using ReAct paradigm |
| `template_mode_enabled` | false | When true, use `{variable_name}` placeholders in instructions |

## Inputs

| File | Content |
|------|---------|
| `state/intention.json` | Goal for this tick (see **Intention source** above if absent) |
| `state/observation.txt` | Current perception (for grounding actions in reality) |
| `state/observation_ctx.json` | Structured environment context (if available) |
| `state/plan_state.json` | Ongoing multi-step plan state (if exists) |
| `state/memory.jsonl` | Optional context |

## Plan Model

A plan consists of multiple steps:

```json
{
  "target": "Go to the supermarket and buy groceries",
  "reasoning": "Need food for the week",
  "steps": [
    {
      "intention": "Walk to supermarket",
      "status": "pending",
      "start_time": null,
      "evaluation": null
    },
    {
      "intention": "Enter store",
      "status": "pending",
      "start_time": null,
      "evaluation": null
    },
    {
      "intention": "Pick items",
      "status": "pending",
      "start_time": null,
      "evaluation": null
    },
    {
      "intention": "Pay",
      "status": "pending",
      "start_time": null,
      "evaluation": null
    }
  ],
  "index": 0,
  "completed": false,
  "failed": false,
  "start_time": "2024-01-15T10:00:00",
  "end_time": null
}
```

### Plan Step Status

| Status | Description |
|--------|-------------|
| `pending` | Step has not been started yet |
| `in_progress` | Step is currently being executed |
| `completed` | Step has been successfully completed |
| `failed` | Step has failed and cannot be completed |

### Plan Step Evaluation

After each step execution, record the evaluation:

```json
{
  "success": true,
  "evaluation": "Successfully walked to the supermarket",
  "consumed_time": 15
}
```

## Multi-Step Plans

Some goals take multiple ticks. Use `state/plan_state.json` to track progress:

```json
{
  "goal": "Go to the supermarket and buy groceries",
  "steps": ["walk to supermarket", "enter store", "pick items", "pay"],
  "current_step": 1,
  "started_tick": 42
}
```

### Step Execution Cycle

Each tick:

1. `workspace_read("state/plan_state.json")` — check if there's an ongoing plan.
2. If the current step is done (based on observation), increment `current_step`.
3. Execute the current step via `codegen`.
4. `workspace_write("state/plan_state.json", ...)` — persist updated state.
5. When all steps are done, delete or clear `state/plan_state.json`.

## Step Execution with ReAct Paradigm

For each plan step, use the ReAct (Reasoning + Acting) paradigm:

1. **Reason**: Analyze the current observation and determine what action to take
2. **Act**: Execute the action via `codegen`
3. **Observe**: Check the environment response
4. **Repeat**: Continue until step is complete or max interactions reached

### ReAct Interaction Limit

Each step has a maximum number of environment interactions (default: 3). This prevents infinite loops and ensures the agent doesn't get stuck.

### ReAct Interaction Record

Track each interaction:

```json
{
  "plan_step_index": 0,
  "interaction_num": 1,
  "instruction": "Move to the café on Main Street",
  "reasoning": "I need to get to the café to eat",
  "answer": "Successfully moved to café entrance",
  "status": "success"
}
```

## CRITICAL: Avoid Redundant Queries

Before generating any instruction, follow these principles to act like a real person:

### 1. Check Observation First
Before generating any instruction, carefully review the observation provided. If it already contains the information you need, DO NOT query the environment again for the same information.

### 2. Check Previous Interactions
Review the conversation history. DO NOT repeat the same query or action that was already attempted. If a previous interaction already provided the needed information, use that information instead of querying again.

### 3. Energy Conservation
Interacting with the environment consumes energy (like a real person). Only query the environment when absolutely necessary. If you already know the answer from observation or previous interactions, proceed with the action directly.

### 4. Avoid Duplicate Actions
If you have already attempted an action in a previous interaction, do not repeat it unless there is a clear reason (e.g., the previous attempt failed and you need to retry with modifications).

### 5. Use Available Information Priority
Always prioritize using information from:
- Current observation (highest priority)
- Previous interactions in this conversation
- Related memories
Only query the environment as a last resort when the information is truly needed and not available elsewhere.

## Environment Constraints

**IMPORTANT**: You are operating in the simulated world. Please do NOT attempt any actions that are infeasible according to the **AVAILABLE ACTIONS** in the environment.

- Your actions are limited by the AVAILABLE ACTIONS in the environment
- Actions can only be a single or a combination of the AVAILABLE ACTIONS
- Ensure that the level of detail in your actions corresponds precisely to the allowed action space

## Re-observe After Every Action

After each `codegen` call (except when status indicates completion):

1. **Call `<observe>` again** to get the updated environment state
2. **Update `state/observation.txt`** with the new observation
3. **Continue reasoning** based on the new state

This ensures the agent maintains accurate awareness of the environment after each action.

Example sequence:
```
1. codegen("Move to café") → response
2. codegen("<observe>") → new observation
3. Update state/observation.txt
4. Continue with next action or conclude
```

## Checking Step Completion

Classify the **active plan step** after each interaction:

| Status | Meaning |
|--------|---------|
| `completed` | Step intention is satisfied given latest observation / tool thread. |
| `in_progress` | Still in flight. If the environment says the action is **unsupported**, use **`failed`**, not endless `in_progress`. |
| `failed` | Unreachable, or **repeated failures** on the same subgoal with no progress (prefer `failed` over spinning). |
| `pending` | Not started yet (if your `state/plan_state.json` tracks that). |

Check: step goal → latest observation → actions in thread / `state/memory.jsonl` → goal met? Multiple dead-end retries → `failed`. Then update `state/plan_state.json`.

## Plan Interruption

### Intention vs current plan

Reconcile `state/intention.json` with the plan you are executing:

1. Is the latest intention **materially different** from the plan’s target?
2. Is it **more urgent** than finishing the current plan?
3. Should you **drop** the plan and replan?

If the balance is “yes”, clear or rewrite `state/plan_state.json` and build a new plan.

If the workspace indicates an urgent need that should interrupt the current plan, discard the plan and replan toward addressing that need.

### When to Interrupt a Plan

An ongoing plan should be interrupted when:

1. **New urgent need**: A more urgent need has emerged (e.g., safety drops critical, satiety/energy critically low)
2. **Impossible continuation**: The environment cannot support the current plan
3. **Better opportunity**: A significantly better intention has been identified
4. **Plan vs Intention mismatch**: Current intention is significantly different from plan target

#### Need-based interrupt

When the workspace signals that a plan should be interrupted (e.g., an urgent need flag), reset `state/plan_state.json` and generate steps that address the urgent condition.

### Systematic Interruption Decision Process

Before executing any plan step, check these conditions in order:

#### Step 1: Check needs.json for urgent needs

```json
{
  "tool_name": "workspace_read",
  "arguments": {"path": "state/needs.json"}
}
```

If `should_interrupt_plan` is `true`, **interrupt immediately** and replan to address the urgent need.

#### Step 2: Check intention alignment

```json
{
  "tool_name": "workspace_read",
  "arguments": {"path": "state/intention.json"}
}
```

Compare the current intention with the plan target:

| Condition | Action |
|-----------|--------|
| Intention matches plan target | Continue plan |
| Intention differs but less urgent | Continue plan, note new intention |
| Intention differs and more urgent | Interrupt plan, replan |
| Intention is about survival (eat/rest/flee) | Interrupt immediately |

#### Step 3: Environmental feasibility

Check if the current plan step is still feasible:

| Situation | Action |
|-----------|--------|
| Environment supports current step | Continue |
| Environment changed, step impossible | Mark step as `failed`, replan |
| Environment changed, alternative available | Modify plan, continue |

### Interruption Priority Matrix

| Priority | Condition | Must Interrupt? |
|----------|-----------|-----------------|
| 1 | `satiety` or `energy` critical (< 0.2) | **YES** - Survival |
| 2 | `safety` critical (< 0.2) with immediate threat | **YES** - Safety |
| 3 | New intention conflicts with plan + is more urgent | **YES** - Priority |
| 4 | Plan step has failed 3+ times | **YES** - Stuck |
| 5 | Environment makes plan impossible | **YES** - Infeasible |
| 6 | New interesting opportunity | **MAYBE** - Consider tradeoffs |
| 7 | Minor intention change | **NO** - Continue |

### How to Determine Interruption

Ask yourself:
1. Is the latest intention significantly different from the current plan target?
2. Is the latest intention more urgent or important than completing the current plan?
3. Should the current plan be interrupted to pursue the new intention?

If the answer is yes, set the plan to interrupted and generate a new plan.

### Interruption Decision

```json
{
  "tool_name": "workspace_read",
  "arguments": {"path": "state/intention.json"}
}
```

Compare current intention with plan target. If significantly different and more urgent, interrupt:

```json
{
  "tool_name": "workspace_write",
  "arguments": {
    "path": "state/plan_state.json",
    "content": "{}"
  }
}
```

Then generate a new plan based on the new intention.

## Continue Executing After Step Completion

When a step completes successfully:

1. **Increment step index** to move to next step
2. **Check if more steps remain**
3. **If more steps**: Continue executing the next step (don't wait for next tick if capacity allows)
4. **If last step completed**: Mark plan as completed and clear or finalize `state/plan_state.json`

Example flow:
```
Step 0: Walk to supermarket
  → completed → move to step 1
Step 1: Enter store
  → completed → move to step 2
Step 2: Pick items
  → in_progress → wait for next tick
```

## Agent Break (Proactive Stop)

The agent can proactively stop execution:

- Use empty `instruction` (`""`) or `"<break>"` to indicate stopping
- Provide a `status` field (`success`, `fail`, `error`) to explain why
- This is useful when the agent determines no further action is needed

## Single-Step Actions

For most intentions, a single `codegen` call suffices:

```json
{
  "tool_name": "codegen",
  "arguments": {
    "instruction": "<action description>",
    "ctx": {}
  }
}
```

### Instruction Examples

| Intention | codegen instruction |
|-----------|-------------------|
| move to café | `"Move to the café on Main Street."` |
| talk to Alice | `"Say hello to Alice and ask how she's doing."` |
| buy food | `"Purchase a meal at the current location."` |
| rest | `"Find a bench or quiet spot and rest."` |
| explore | `"Walk around and observe the neighborhood."` |

Pass relevant context from `state/observation_ctx.json` in the `ctx` argument if the environment expects structured data (e.g., location IDs, agent IDs).

## Plan Generation

When there's no active plan, generate one from the current intention:

1. Read related memories for the intention
2. Consider current observation (use info from observation, don't plan redundant queries)
3. Generate step-by-step plan (limited to max_plan_steps, typically 6)
4. Ensure steps are actionable and realistic

### Decomposing a goal into steps

1. Each step is one clear **`intention`** string: what to achieve in that slice of work.  
2. **`steps`** contains only what is **necessary**, at most **`max_plan_steps`** (default 6).  
3. Use **`state/memory.jsonl`** (tail or `grep`) so you do not repeat known-failed moves.  
4. Every step must be **executable under AVAILABLE ACTIONS** from the world description—no made-up verbs.  
5. Avoid **query-only** steps to re-fetch facts you already have: rely on `state/observation.txt` / `state/observation_ctx.json` when they already state place, time, nearby entities.

**Feasibility:** instructions must match the simulator’s action vocabulary—either one allowed action or a valid combination, at the right granularity.

### Plan Generation Guidelines

1. Each execution step should have a clear `intention` field
2. `steps` list should only include steps necessary to fulfill the intention
3. Consider related memories when planning steps
4. Steps should be actionable and realistic
5. No need to plan too many query steps because an overall observation will be provided first for each step
6. **Don't tear the core action into over-detailed steps** — keep each step meaningful

## Handling Environment Responses

After calling `codegen`, check the result:

- **`ok: true`**: the action was accepted. Read `stdout` for any feedback.
- **`status: "in_progress"`**: the action is still ongoing (e.g., traveling). Call `done` and resume next tick.
- **`ok: false`**: the action failed. Read `stderr` for the reason. Consider:
  - Retrying with a different approach
  - Adjusting the intention (write updated `state/intention.json` for next tick)
  - Abandoning the plan if it's not feasible

## Decision Guidelines

- **Respect priority**: A `high` priority intention should be acted on immediately. A `low` priority intention can be deferred if something better comes up.
- **Stay grounded**: Only attempt actions that make sense given your current location and observation. Don't try to interact with entities that aren't nearby.
- **One action per tick**: Execute one meaningful action, then call `done`. Don't try to chain multiple environment actions in a single step.
- **Handle idle gracefully**: If the intention is `wait` or there's nothing to do, it's fine to call `codegen` with a simple idle action or just call `done` directly.
- **Avoid redundant queries**: Check observation first before querying the environment for information.
- **Use available information**: Prioritize information from current observation, previous interactions, and related memories.

## After success or failure

Update `state/plan_state.json` (and optionally `state/memory.jsonl`) to record step outcomes.

## Workspace Files Summary

| File | Purpose |
|------|---------|
| `state/plan_state.json` | Current multi-step plan state |
| `state/intention.json` | Current goal (from any source) |
| `state/observation.txt` | Current environment perception |
| `state/observation_ctx.json` | Structured environment data |
| `state/memory.jsonl` | Optional execution notes |

## Template Mode (Optional)

When `template_mode_enabled` is true, instructions use placeholder syntax for variables:

### How It Works

Instead of embedding values directly, use placeholders with a variables dict:

```json
{
  "instruction": "Move to {location}",
  "variables": {"location": "home"}
}
```

### Template Mode Rules

1. **MANDATORY**: When you have variables (location, item, amount, etc.), you MUST use `{variable_name}` placeholders
2. Plain text with concrete values will break template caching
3. The instruction MUST contain placeholders if there are ANY variables

### Good Examples

```json
{"instruction": "Move to {location}", "variables": {"location": "home"}}
{"instruction": "Buy {item} for {price} dollars", "variables": {"item": "apple", "price": 5}}
{"instruction": "Send {amount} to {target}", "variables": {"amount": "100", "target": "Alice"}}
```

### Bad Examples (DO NOT do this)

```json
{"instruction": "Move to home", "variables": {"location": "home"}}  // Should use {location}
{"instruction": "Buy apple for 5 dollars", "variables": {"item": "apple", "price": 5}}  // Should use placeholders
```

Template mode is useful when instructions are cached and reused with different parameters.
