# Configuration Structure Reference

## init_config.json

```json
{
  "env_modules": [
    {"module_type": "SimpleSocialSpace", "kwargs": {...}}
  ],
  "agents": [
    {"agent_id": 1, "agent_type": "PersonAgent", "kwargs": {...}}
  ]
}
```

### Key Rules

- Use class names as type identifiers (e.g., `PersonAgent`, not `person_agent`).
- All parameters go in the `kwargs` dictionary.
- `agent_id` must equal `kwargs.id`.

## steps.yaml

```yaml
start_t: "2024-01-01T00:00:00"
steps:
  - type: run
    num_steps: 100
    tick: 1
  - type: ask
    question: "Summarize current state"
  - type: intervene
    instruction: "Modify something..."
  - type: questionnaire
    questionnaire_id: "post_run_survey"
    title: "Post-run survey"
    description: "Collect structured responses from agents after the run"
    target_agent_ids: [1, 2, 3]
    questions:
      - id: "mood"
        prompt: "How do you feel about the outcome?"
        response_type: "choice"
        choices: ["positive", "neutral", "negative"]
      - id: "reason"
        prompt: "Briefly explain your answer."
        response_type: "text"
```

### Step Types

| Type | Purpose | Key Fields |
|------|---------|------------|
| `run` | Simulate N ticks | `num_steps`, `tick` |
| `ask` | Query agents | `question` |
| `intervene` | Modify simulation state | `instruction` |
| `questionnaire` | Structured agent survey | `questionnaire_id`, `questions` |

### questionnaire Step

Use a `questionnaire` step when the experiment needs structured answers from agents during or after the simulation.

**Required fields:**
- `type: questionnaire`
- `questionnaire_id`: unique identifier for this questionnaire run
- `questions`: non-empty list of question objects

**Optional fields:**
- `title`: questionnaire title shown in the prompt context
- `description`: questionnaire-level instructions
- `target_agent_ids`: list of agent IDs; omit to survey all agents

**Question object fields:**
- `id`: unique question identifier
- `prompt`: question text
- `response_type`: one of `text`, `integer`, `float`, `choice`, `json`
- `choices`: required when `response_type` is `choice`
