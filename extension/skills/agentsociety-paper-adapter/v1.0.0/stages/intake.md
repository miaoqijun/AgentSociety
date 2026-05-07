# Stage - Adapter Intake (no user interview)

The adapter has no human intake stage; it is a pure walk over the
workspace tree. This file documents what the adapter *will* read so
that the orchestrator can sanity-check the workspace before invoking
`build-pack`.

## Pre-flight Checklist

Before dispatching `paper-orchestrator build-pack`, confirm:

1. `<workspace>/TOPIC.md` exists and is non-empty (the topic seeds the
   default `research_objective` and the framing skill's intro draft).
2. At least one `<workspace>/hypothesis_<id>/` directory exists.
3. For each hypothesis, the corresponding
   `<workspace>/presentation/hypothesis_<id>/` tree contains either a
   `report*.md` or `data/analysis_summary.json` - missing both
   degrades the pack to "low confidence" and the framing producer
   will likely return `BLOCKED`.
4. `<workspace>/papers/literature_index.json` exists (if the user
   wants citations) and follows the
   `agentsociety-literature-search` schema (`{"entries": [...]}`).

If any of (1)-(3) fail, surface the gap to the user before running
`build-pack`. Do NOT attempt to fabricate inputs.

## What the Adapter Does

- Walks the workspace tree using `os.scandir`
- Reads each text file via `read_text_safe` (UTF-8; missing files
  return `""`)
- Summarizes `analysis_summary.json` via
  `summarize_analysis_result_json` (preserves `tables`, `row_counts`,
  `insights`, `findings`, `recommendations`, `conclusions`)
- Collects figure paths under `presentation/.../assets/` (extensions
  in `{.png, .jpg, .jpeg, .gif, .svg, .webp}`)
- Derives BibTeX cite keys from literature entries via
  `sanitize_bibtex_key` and pre-renders BibTeX strings via
  `build_reference_strings`
- Emits a provenance map flagging `low` confidence for missing /
  empty inputs

## Output Persistence

Result is written to `<workspace>/paper/state/research_pack.json`.

Producer / reviewer subagents downstream read this file as the single
source of grounded workspace context.
