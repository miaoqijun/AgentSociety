# agentsociety-analysis skill

A staged skill for analyzing AgentSociety experiment results, including data understanding,
evidence extraction, chart generation, composite figure assembly, and bilingual report writing.

This skill is built on the `agentsociety2` Python analysis tool layer. All mechanical operations
should go through:

```bash
$PYTHON_PATH .agentsociety/bin/ags.py analysis ...
```

Unlike a standalone manuscript-figure workflow, this skill treats visualization as part of
interactive experiment analysis. Every chart should be tied to a confirmed finding, a concrete
SQLite query or aggregation rule, and a final report reference.

## Core Principles

- Define the analysis question and finding before choosing a chart form.
- Define the evidence source before writing plotting code.
- Charts are driven by claims and contracts, not a fixed count (optional `max_charts` cap in harness state).
- Build composite figures from atomic charts first, then assemble them with `compose-figure`.
- Keep output directories, naming rules, report assets, and `artifact_manifest.json` aligned.

## Reference Layout

The current version uses a contract-first documentation layout tailored to `agentsociety2`:

- `SKILL.md`: entry contract and stage routing
- `references/figure-contract.md`: finding-to-figure contract
- `references/api.md`: Python plotting scaffold and export helpers
- `references/common-patterns.md`: reusable legend, axis, and panel patterns
- `references/design-theory.md`: visual hierarchy and evidence presentation
- `references/qa-contract.md`: chart and report acceptance checks
- `references/backend-selection.md`: fixed Python backend rule
- `references/tutorials.md` / `references/chart-types.md` / `references/demos.md`: examples and routing support

## Directory Layout

```text
agentsociety-analysis/
├── manifest.json
└── v1.0.0/
    ├── SKILL.md
    ├── support/          # bundled report/UI helpers (e.g. frontend-design)
    ├── assets/
    │   └── layout-atlas/
    ├── checklists/
    ├── references/
    ├── scripts/
    ├── stages/
    └── subagent-prompts/
```

## Primary Capabilities

- Load hypothesis and experiment context from the workspace
- Read SQLite schema, sample rows, and summary statistics
- Execute read-only SQL queries
- Run constrained Python analysis scripts and collect chart artifacts
- Generate EDA outputs
- Assemble multiple PNG/JPG/WebP charts into composite figures with panel labels
- Collect report-facing assets and experiment artifacts

## Runtime Requirements

- The active Python environment must be able to import `agentsociety2`
- Prefer `PYTHON_PATH` from the workspace `.env`
- Plotting scripts must use the `Agg` backend and set:
  `font.family = sans-serif`, `font.sans-serif`, and `svg.fonttype = none`

## Versioning

The current default version is `v1.0.0`. The extension runtime reads `manifest.json`
to resolve the default version and syncs it into the workspace `.claude/skills/` bundle.
