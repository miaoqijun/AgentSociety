# Stage: produce_storyline

Dispatch the framing producer to generate a `storyline_map` from the
research pack.

## Routing Table

| Condition | Dispatch | Persist |
|-----------|----------|---------|
| `phase=framing` AND no `storyline_map.json` | producer | `paper-orchestrator framing --payload <storyline_map JSON>` |
| `storyline_map.json` persisted, no review_round for current angle | angle-critic (read-only) | `paper-orchestrator review --payload <Review JSON> --round N` |
| producer envelope = `DONE_WITH_CONCERNS` OR angle-critic verdict != `accept` | contribution-auditor (read-only) | same CLI subcmd |
| any reviewer verdict = `pivot_conceptual` or `pivot_major` | revision-router (orchestrator-internal) | n/a |
| all reviewers accept | advance phase | n/a |

## Dispatch Instructions

### Producer Dispatch

1. Read `paper_state.yaml` to get workspace path and run context.
2. Build the producer input JSON:
   ```json
   {
     "workspace_path": "<absolute>",
     "research_pack_path": "<ws>/paper/state/research_pack.json",
     "paper_state_path": "<ws>/paper/state/paper_state.yaml",
     "prior_storyline_path": null,
     "prior_review_findings": [],
     "round_constraints": [],
     "target_artifact": "storyline_map"
   }
   ```
3. Open a Task subagent with prompt from `subagent-prompts/producer.md`.
4. Parse the envelope JSON from the subagent's response.
5. Persist the `storyline_map` field via CLI:
   ```
   $PYTHON_PATH .agentsociety/bin/ags.py paper-orchestrator framing \
     --workspace <ws> --payload '<storyline_map JSON>'
   ```

### Angle-Critic Dispatch

After storyline_map is persisted:

1. Build the critic input JSON:
   ```json
   {
     "workspace_path": "<absolute>",
     "storyline_path": "<ws>/paper/artifacts/storyline_map.json",
     "research_pack_path": "<ws>/paper/state/research_pack.json",
     "paper_state_path": "<ws>/paper/state/paper_state.yaml",
     "round_num": 1
   }
   ```
2. Open a Task subagent with prompt from `subagent-prompts/angle-critic.md`.
3. Parse the Review envelope.
4. Persist via: `paper-orchestrator review --payload <Review JSON> --round 1`.
5. If verdict != `accept`, proceed to contribution-auditor.

### Contribution-Auditor Dispatch (conditional)

Only when triggered by the routing table:

1. Build the auditor input JSON (same shape as angle-critic).
2. Open a Task subagent with prompt from `subagent-prompts/contribution-auditor.md`.
3. Parse the Review envelope.
4. Persist via: `paper-orchestrator review --payload <Review JSON> --round N`.
