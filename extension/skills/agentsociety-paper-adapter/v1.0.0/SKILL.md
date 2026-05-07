---
name: agentsociety-paper-adapter
version: 1.0.0
description: Use when paper inputs in an AgentSociety workspace need to be normalized into a `ResearchPack` for downstream paper skills.
---

# Paper Adapter

Translate a project-specific AgentSociety workspace into the
generic `ResearchPack` consumed by every other paper skill. The
adapter is intentionally **thin**: it walks the workspace tree, extracts
text, summarizes analysis JSON, derives BibTeX cite keys, and emits a
provenance map. It does **not** judge whether the materials are good
enough for a paper - that is the framing skill's job.

The adapter is exposed through the `paper-orchestrator build-pack`
sub-command; `paper-adapter` itself only exists as a plugin skill so
that future workspaces (non-AgentSociety) can swap in their own
adapter without touching the kernel.

## When to Use

- After a fresh `analysis` run produces new
  `presentation/hypothesis_*/report*.md` or
  `data/analysis_summary.json`
- When the user wants to refresh the literature index
  (`papers/literature_index.json`)
- After adding a new hypothesis directory the orchestrator should pick
  up

**Do NOT use when:**

- The orchestrator has not yet run `intake` (the state machine is the
  caller's gate)
- The user explicitly wants to skip the adapter (rare; only the
  framing skill's "manual override" path supports this)

## Quick Reference

| Action | Command |
|--------|---------|
| Build pack via orchestrator | `$PYTHON_PATH .agentsociety/bin/ags.py paper-orchestrator build-pack --workspace .` |
| Build pack directly | `$PYTHON_PATH .agentsociety/bin/ags.py paper-adapter --workspace . [--research-objective "..."]` |
| Read pack | open `<workspace>/paper/state/research_pack.json` |

Aliases: `paper-adapter`, `paper_adapter`.

## Inputs

| Path | Required? | Used as |
|------|-----------|---------|
| `<ws>/TOPIC.md` | recommended | `topic`, default `research_objective` |
| `<ws>/hypothesis_<id>/HYPOTHESIS.md` | recommended | `hypotheses[].text` |
| `<ws>/hypothesis_<id>/experiment_<eid>/EXPERIMENT.md` | optional | `experiments[].design` |
| `<ws>/presentation/hypothesis_<id>/report{_zh,_en,}.md` | optional | per-hypothesis analysis report |
| `<ws>/presentation/hypothesis_<id>/data/analysis_summary.json` | optional | summarized via `summary.summarize_analysis_result_json` |
| `<ws>/presentation/hypothesis_<id>/assets/*` | optional | figure inventory (image extensions only) |
| `<ws>/synthesis/synthesis_report{_zh,_en,}.md` | optional | cross-hypothesis synthesis text |
| `<ws>/synthesis/assets/*` | optional | synthesis-level figures |
| `<ws>/papers/literature_index.json` | recommended | `literature[]` + BibTeX strings |

Confidence flags in `provenance[]`: `high` (file exists and is
non-empty), `low` (file missing or empty). Producer subagents should
treat `low` provenance as suspect and avoid building strong claims on
it.

## Output

Emits the envelope expected by the orchestrator + persists
`<workspace>/paper/state/research_pack.json` matching the
:class:`agentsociety2.skills.paper.models.ResearchPack` schema.

See `references/research_pack_schema.md` for the field-by-field
contract.

## Subagent Delegation

The adapter is non-LLM. Do **not** dispatch subagents for it; just call
the CLI from the orchestrator.

## Pipeline Position

**Predecessors:** `agentsociety-analysis` (must populate the
`presentation/` tree)
**Successors:** `agentsociety-paper-framing`
**Required Sub-Skills:** none
