# Stage: draft_section

Draft manuscript sections block by block. This is the only stage where
the subagent writes files directly to disk.

## Direct-Write Contract

The draft_section producer is the **only subagent** in the paper harness
that writes files to disk directly. All other producers return content
in their envelope for the orchestrator to persist.

**Why:** Multi-KB markdown documents are fragile when passed through
stdout JSON encoding.

**Contract:**
- Producer receives `target_paths` in its input.
- Producer writes .md files at those paths.
- Producer emits its envelope as the **last line of stdout** after all
  writes complete.
- The orchestrator does NOT call a CLI persist subcommand.
- The orchestrator verifies files exist after the subagent returns.

## Block Dispatch Order

Blocks are dispatched sequentially in this order:

1. **`abstract+main`** (1 block) — writes `abstract.md` + `main.md`
2. **`results/<NN>_<slug>`** (N blocks, ordered by
   `figure_argument_map.figures[].target_section`) — writes 1 file each
3. **`discussion`** (1 block, last) — writes `discussion.md`

Results blocks must be ordered by argumentative strength (strongest
first), not by analysis chronology.

## Dispatch Instructions

For each block from `section_outline.blocks[]`:

1. Create the manuscript directory structure if it does not exist:
   ```
   mkdir -p <ws>/paper/artifacts/manuscript/results/
   ```

2. Filter claims and figures for this block:
   - `claims_for_block`: claim_ledger entries whose IDs are in
     `block.claim_ids`
   - `figures_for_block`: figure_argument_map entries whose IDs are in
     `block.figure_ids`

3. Build the producer input JSON:
   ```json
   {
     "workspace_path": "<absolute>",
     "research_pack_path": "<ws>/paper/state/research_pack.json",
     "storyline_path": "<ws>/paper/artifacts/storyline_map.json",
     "claim_ledger_path": "<ws>/paper/artifacts/claim_ledger.json",
     "figure_argument_map_path": "<ws>/paper/artifacts/figure_argument_map.json",
     "target_artifact": "draft_section",
     "block": {
       "block_id": "<from outline>",
       "kind": "<from outline>",
       "title": "<from outline>",
       "claim_ids": ["<from outline>"],
       "figure_ids": ["<from outline>"]
     },
     "figures_for_block": [<filtered figure entries>],
     "claims_for_block": [<filtered claim entries>],
     "target_paths": ["<from outline target_paths>"],
     "prior_review_findings": [],
     "round_constraints": ["<from paper/state/paper_state.yaml>"]
   }
   ```

4. Open a Task subagent with prompt from `subagent-prompts/producer.md`.

5. After the subagent returns:
   - Verify every path in `target_paths` exists and is non-empty.
   - Verify result blocks stayed under `manuscript/results/` rather than
     being flattened to `manuscript/results_*.md`.
   - Verify the written markdown contains no residual degraded-generation
     slot marker such as `[[METRIC_SLOT:s1]]`.
   - If any file is missing, re-dispatch the same block (max 1 retry).
   - If retry fails, open a human_gate.

6. Record the written paths in the orchestrator's dispatch log.
7. If `round_constraints` contains a `template_slots` instruction for
   this draft pass, honor it before attempting another unconstrained
   rewrite of the same unstable paragraph.

## Important Rules

- Each block must only use claims from `claims_for_block`. If the
  producer needs a claim not in the list, it must flag this as
  `DONE_WITH_CONCERNS` — the orchestrator may need to re-run the
  claim_tree stage.
- If a target file already exists, read it before editing. The file
  tools reject direct overwrites of unread files.
- Citation sentinels: `[CITE:key]` only, and `key` must come from the
  literature cite keys in `research_pack.json`. Claim IDs are invalid.
- Figure sentinels: `[FIG:id]` → will be converted to `Fig.~\ref{fig:id}`.
- If drafting drifts on evidence insertion, switch to the degraded
  generation fallback in `references/degraded_generation.md`, then write
  only the fully rendered markdown.
- Cross-section references require an explicit label from the
  orchestrator. In the absence of such a label, avoid `[SEC:*]`
  sentinels.
