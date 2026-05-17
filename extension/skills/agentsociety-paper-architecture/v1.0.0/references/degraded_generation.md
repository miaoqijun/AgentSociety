# Degraded Generation

When free-form drafting becomes unstable, switch from “write the whole
paragraph” to “write a paragraph skeleton, then fill typed slots”.

This mechanism is reserved for difficult blocks:

- Dense result paragraphs carrying multiple metrics
- Paragraphs that repeatedly hallucinate citations or figure anchors
- Revisions where the structure is right but evidence insertion keeps
  drifting

## Slot Marker Format

Use double-bracket markers so they never collide with `[CITE:key]` or
`[FIG:id]` sentinels:

```text
[[CLAIM_SLOT:s1]]
[[METRIC_SLOT:s2]]
[[FIGURE_SLOT:s3]]
[[CITATION_SLOT:s4]]
[[EVIDENCE_SLOT:s5]]
[[TRANSITION_SLOT:s6]]
```

## Fallback Procedure

1. Draft a paragraph skeleton with 1 dominant argumentative function.
2. Replace fragile fragments with typed slots.
3. Bind each slot to one concrete source:
   - claim text from `claims_for_block`
   - metric text from analysis summaries
   - figure text from `figures_for_block`
   - citation text from valid `research_pack.literature[*].cite_key`
4. Fill the slots one by one.
5. Render the final paragraph and verify that **no `[[...]]` marker
   remains**.

## Constraints

- Slot filling is evidence-bound, not free invention.
- Every `[[CITATION_SLOT:*]]` must resolve to a valid `[CITE:key]`.
- Every `[[FIGURE_SLOT:*]]` must resolve to a valid `[FIG:id]`.
- A final manuscript file may contain `[CITE:key]` and `[FIG:id]`, but
  may never contain `[[...]]`.

## When to Report It

If degraded generation was required, mention it in `key_findings` so the
orchestrator and later reviewers know the block came through fallback
drafting rather than a stable one-shot draft.
