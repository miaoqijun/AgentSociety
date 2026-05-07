# Stage: figure_argument

Build the figure-argument map linking figures to claims, then review
the figure logic.

## Routing Table

| Condition | Dispatch | Persist |
|-----------|----------|---------|
| `claim_ledger.json` exists AND no `figure_argument_map.json` | producer with `target_artifact=figure_argument_map` | `paper-orchestrator architecture --artifact figure_argument_map --payload <JSON>` |
| `figure_argument_map.json` persisted | figure-logic-reviewer (read-only) | `paper-orchestrator review --payload <Review JSON> --round N` |
| reviewer verdict != `accept` AND `revise_structural+` | re-dispatch producer (figure_argument_map) with reviewer notes | same |
| figure regen count >= 2 | open `human_gate` | n/a |

## Dispatch Instructions

### Producer Dispatch

1. Build the producer input JSON:
   ```json
   {
     "workspace_path": "<absolute>",
     "research_pack_path": "<ws>/paper/state/research_pack.json",
     "storyline_path": "<ws>/paper/artifacts/storyline_map.json",
     "claim_ledger_path": "<ws>/paper/artifacts/claim_ledger.json",
     "figure_argument_map_path": null,
     "target_artifact": "figure_argument_map",
     "block": null,
     "figures_for_block": null,
     "claims_for_block": null,
     "prior_review_findings": [],
     "round_constraints": []
   }
   ```
2. Open a Task subagent with prompt from `subagent-prompts/producer.md`.
3. Persist the `figure_argument_map` field via CLI.

### Figure-Logic-Reviewer Dispatch (always after producer)

1. Build the reviewer input JSON:
   ```json
   {
     "workspace_path": "<absolute>",
     "figure_argument_path": "<ws>/paper/artifacts/figure_argument_map.json",
     "claim_ledger_path": "<ws>/paper/artifacts/claim_ledger.json",
     "storyline_path": "<ws>/paper/artifacts/storyline_map.json",
     "research_pack_path": "<ws>/paper/state/research_pack.json",
     "round_num": 1
   }
   ```
2. Open a Task subagent with prompt from
   `subagent-prompts/figure-logic-reviewer.md`.
3. Persist the Review envelope via CLI.

### Retry Logic

If the reviewer returns `revise_structural` or worse:

1. Increment `paper_state.counters.figure_regenerations`.
2. If counter >= 2, open a human_gate.
3. Otherwise, re-dispatch the producer with `prior_review_findings`
   populated from the reviewer's issues.
