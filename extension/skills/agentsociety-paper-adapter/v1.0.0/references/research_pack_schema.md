# ResearchPack Schema

Canonical pydantic shape:
:class:`agentsociety2.skills.paper.models.ResearchPack`.

```jsonc
{
  "workspace_path": "<absolute>",
  "topic": "<TOPIC.md content>",
  "research_objective": "<topic heading or override>",
  "hypotheses": [
    {
      "hypothesis_id": "1",
      "text": "<HYPOTHESIS.md trimmed to 4000 chars>",
      "experiments": ["1", "2"],
      "confidence": "high|medium|low"
    }
  ],
  "experiments": [
    {
      "experiment_id": "1",
      "hypothesis_id": "1",
      "design": "<EXPERIMENT.md trimmed to 4000 chars>",
      "confidence": "high|medium|low"
    }
  ],
  "analyses": [
    {
      "analysis_id": "hp1_summary",
      "hypothesis_id": "1",
      "summary": "<report*.md trimmed + summarize_analysis_result_json output>",
      "raw_json": { /* analysis_summary.json verbatim, dict only */ }
    }
  ],
  "figures": [
    {
      "figure_id": "hp1_<file_stem>",
      "file_path": "<absolute>",
      "source": "<workspace-relative path>",
      "caption_hint": "<title-cased filename>"
    }
  ],
  "literature": [
    {
      "cite_key": "smith2024",
      "title": "...",
      "authors": "Alice Author and Bob Builder",
      "year": "2024",
      "doi": "10.1234/...",
      "journal": "...",
      "bibtex": "@article{smith2024, ...}"
    }
  ],
  "synthesis_report": "<synthesis_report{_zh,_en,}.md content>",
  "draft_inputs": {},
  "provenance": [
    {
      "artifact_id": "topic",
      "source_path": "/.../TOPIC.md",
      "confidence": "high|low",
      "notes": ""
    }
  ],
  "generated_at": "<ISO 8601 UTC>"
}
```

## Provenance Rules

| `artifact_id` pattern | Meaning |
|-----------------------|---------|
| `topic` | TOPIC.md |
| `hypothesis:<id>` | hypothesis_<id>/HYPOTHESIS.md |
| `experiment:<hid>.<eid>` | hypothesis_<hid>/experiment_<eid>/EXPERIMENT.md |
| `analysis:<hid>` | presentation/hypothesis_<hid>/report*.md OR data/analysis_summary.json (whichever exists) |
| `figure:<figure_id>` | per-figure file path |
| `synthesis` | synthesis/synthesis_report*.md |
| `literature_index` | papers/literature_index.json |

`confidence`:

- `high`: source file exists, non-empty, parsed cleanly
- `medium`: source partially populated (currently unused; reserved for
  future heuristics)
- `low`: source missing OR empty OR JSON parse failed

Downstream producers should refuse to build claims that rest on
`low`-confidence artifacts unless the orchestrator explicitly authorizes
override.

## Cite Key Derivation

`cite_key` is derived deterministically from `(title, idx, year)` via
`agentsociety2.skills.paper.adapter.summary.sanitize_bibtex_key`:

1. Lower-case the title; keep only ASCII alphanumerics + spaces
2. Take the first whitespace-delimited token (or `ref<idx>` fallback)
3. Concatenate with the year string

Producer markdown should always reference these exact keys via
`[CITE:<cite_key>]` so `compose/md_to_tex` -> `\supercite{<cite_key>}`
resolves against `references.bib`.

## Output Limits

To stay token-cheap for downstream producers, the adapter trims long
text fields:

- `hypotheses[].text` - 4000 chars
- `experiments[].design` - 4000 chars
- `analyses[].summary` (per-hypothesis report portion) - 6000 chars
- `analyses[].summary` (analysis_summary.json portion) - 4000 chars

`raw_json` is preserved in full because reviewer skills may need exact
numbers (effect sizes, CIs).
