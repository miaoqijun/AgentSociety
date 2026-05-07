# Stage: section_outline

Generate the section outline that partitions the manuscript into
draftable blocks.

## Routing Table

| Condition | Dispatch | Persist |
|-----------|----------|---------|
| `claim_ledger.json` AND `figure_argument_map.json` both exist | producer with `target_artifact=section_outline` | **None** — outline lives in envelope only |

## Outline Structure

The producer returns a `section_outline` field in its envelope (NOT
persisted to disk). The orchestrator extracts the `blocks[]` array and
dispatches one `draft_section` Task per block.

### Block Schema

```json
{
  "blocks": [
    {
      "block_id": "abstract_main",
      "kind": "abstract+main",
      "title": "Abstract and Introduction",
      "claim_ids": ["C1", "C2"],
      "figure_ids": [],
      "target_paths": [
        "<ws>/paper/artifacts/manuscript/abstract.md",
        "<ws>/paper/artifacts/manuscript/main.md"
      ]
    },
    {
      "block_id": "results_01_pattern",
      "kind": "results",
      "title": "Emergent Mobility Patterns",
      "claim_ids": ["C3"],
      "figure_ids": ["F1"],
      "target_paths": [
        "<ws>/paper/artifacts/manuscript/results/01_pattern.md"
      ]
    },
    {
      "block_id": "discussion",
      "kind": "discussion",
      "title": "Discussion",
      "claim_ids": ["C5"],
      "figure_ids": ["F4"],
      "target_paths": [
        "<ws>/paper/artifacts/manuscript/discussion.md"
      ]
    }
  ]
}
```

### Block Taxonomy

| Kind | Count | Target paths |
|------|-------|-------------|
| `abstract+main` | always 1 | `abstract.md` + `main.md` |
| `results` | 1 per result section | `results/<NN>_<slug>.md` |
| `discussion` | always 1, last | `discussion.md` |

### Block Partition Logic

The orchestrator groups `figure_argument_map.figures[]` by
`target_section`. Each unique `target_section` produces one `results`
block. Claims are assigned to blocks based on which figures support them.

## Dispatch Instructions

1. Build the producer input JSON:
   ```json
   {
     "workspace_path": "<absolute>",
     "research_pack_path": "<ws>/paper/state/research_pack.json",
     "storyline_path": "<ws>/paper/artifacts/storyline_map.json",
     "claim_ledger_path": "<ws>/paper/artifacts/claim_ledger.json",
     "figure_argument_map_path": "<ws>/paper/artifacts/figure_argument_map.json",
     "target_artifact": "section_outline",
     "block": null,
     "figures_for_block": null,
     "claims_for_block": null,
     "prior_review_findings": [],
     "round_constraints": []
   }
   ```
2. Open a Task subagent with prompt from `subagent-prompts/producer.md`.
3. Extract `section_outline.blocks[]` from the envelope.
4. For each block, dispatch a `draft_section` Task (see
   `stages/draft_section.md`).
