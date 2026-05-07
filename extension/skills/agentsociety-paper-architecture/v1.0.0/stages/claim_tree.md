# Stage: claim_tree

Build the paper's claim ledger from the storyline map and research pack.

## Routing Table

| Condition | Dispatch | Persist |
|-----------|----------|---------|
| `phase=manuscript-build` AND no `claim_ledger.json` | producer with `target_artifact=claim_tree` | `paper-orchestrator architecture --artifact claim_ledger --payload <JSON>` |
| reviewer verdict on claim_ledger = `revise_*` | producer (claim_tree) with reviewer notes | same |
| same-target retry count >= 2 (per `paper_state.counters`) | open `human_gate` | n/a |

## Dispatch Instructions

### Producer Dispatch

1. Read `paper_state.yaml` to get workspace path, phase, and counters.
2. Build the producer input JSON:
   ```json
   {
     "workspace_path": "<absolute>",
     "research_pack_path": "<ws>/paper/state/research_pack.json",
     "storyline_path": "<ws>/paper/artifacts/storyline_map.json",
     "claim_ledger_path": null,
     "figure_argument_map_path": null,
     "target_artifact": "claim_tree",
     "block": null,
     "figures_for_block": null,
     "claims_for_block": null,
     "prior_review_findings": [],
     "round_constraints": []
   }
   ```
3. Open a Task subagent with prompt from `subagent-prompts/producer.md`.
4. Parse the envelope JSON from the subagent's response.
5. Persist the `claim_ledger` field via CLI:
   ```
   $PYTHON_PATH .agentsociety/bin/ags.py paper-orchestrator architecture \
     --workspace <ws> --artifact claim_ledger --payload '<ClaimLedger JSON>'
   ```

### Retry Logic

If a subsequent reviewer returns a `revise_*` verdict on the claim_ledger:

1. Increment `paper_state.counters.claim_regenerations`.
2. If counter >= 2, open a human_gate instead of re-dispatching.
3. Otherwise, re-dispatch with `prior_review_findings` populated from
   the reviewer's issues.
