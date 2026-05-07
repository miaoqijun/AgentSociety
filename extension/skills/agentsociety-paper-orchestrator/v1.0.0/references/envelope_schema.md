# Skill Envelope

Every Task subagent dispatched by this orchestrator returns an envelope
with the following shape (defined in
`agentsociety2.skills.paper.models.Envelope`).

## Schema

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `status` | enum | yes | `DONE`, `DONE_WITH_CONCERNS`, `NEEDS_CONTEXT`, `BLOCKED`, `PIVOT_RECOMMENDED`, `HUMAN_GATE_REQUIRED` |
| `artifacts_read` | list[str] | yes | Absolute or workspace-relative paths the subagent read |
| `artifacts_written` | list[str] | yes | Same; empty if the subagent only inspected |
| `key_findings` | list[str] | yes | Short bullet-line summaries; orchestrator surfaces these in dispatch logs |
| `blocking_reason` | string | optional | Required when `status == BLOCKED` or `NEEDS_CONTEXT` |
| `recommended_next_step` | string | optional | Free-form hint for the orchestrator's next dispatch |
| `severity` | enum | optional | `info`, `warning`, `fatal` - drives router behaviour |

## Status Semantics

| Status | Semantics | Router action |
|--------|-----------|---------------|
| `DONE` | Artifact ready, no concerns | Persist + advance phase |
| `DONE_WITH_CONCERNS` | Artifact ready but reviewer flagged risks | Persist + log concerns; advance phase |
| `NEEDS_CONTEXT` | Subagent missing input it can't fetch | Re-dispatch with the listed missing files |
| `BLOCKED` (`severity=fatal`) | Cannot recover without human input | Halt + report |
| `BLOCKED` (`severity=warning`) | Recoverable; needs router decision | Route to revision-router |
| `PIVOT_RECOMMENDED` | Subagent thinks the angle/structure is wrong | Route to revision-router with `target_layer=framing` |
| `HUMAN_GATE_REQUIRED` | Major-pivot threshold tripped | Open a human gate; pause loop |

## Producer vs. Reviewer Envelopes

Producer envelopes typically include `artifacts_written` (the JSON they
emitted) and use `DONE` / `DONE_WITH_CONCERNS`. Reviewer envelopes
include `artifacts_read` (the artifact they judged) and may use
`PIVOT_RECOMMENDED` or `HUMAN_GATE_REQUIRED`.

## Persistence

Every subagent envelope returned to the orchestrator ends up in:

```
<workspace>/paper/runs/<TS>/dispatch_<NNN>.json
```

Plus a per-run final envelope:

```
<workspace>/paper/runs/<TS>/envelope.json
```

These records are append-only; the orchestrator never edits past
dispatch records.

## Build / Parse Helpers

Python-side helpers (use these in subagent prompts when explaining how
to format the return JSON):

```python
from agentsociety2.skills.paper.envelope import (
    build_envelope, parse_envelope, envelope_to_json,
)
```
