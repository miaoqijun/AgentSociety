---
name: agentsociety-analysis
version: 1.0.0
description: Use when an experiment run has completed and the user wants interpretation, charts, composite figures, panel-based visual summaries, or analysis reports from the generated data. Also use when several generated charts or existing PNG/JPG assets need to be combined into one report-ready figure with labeled panels.
---

# Analysis

Use this skill as guidance for interactive experiment analysis. Claude Code stays responsible for orchestration, judgment, and user communication. The CLI is only for mechanical operations.

## Overview

Analyze experiment results from AgentSociety simulations. Explore data interactively, produce targeted visualizations or composite figures, and write bilingual reports with optional cross-experiment synthesis.

The plotting and figure-assembly parts of this skill follow a contract-first structure adapted to the `agentsociety2` analysis stack: fixed Python backend, SQLite-first evidence tracking, `ags.py analysis` tool surface, and report asset management under `presentation/` and `synthesis/`.

## When to Use

- An experiment run has completed and `sqlite.db` exists in the run directory.
- The user asks to analyze results, explore data, visualize data, combine multiple assets into one figure, create charts, or write analysis reports.
- The user references a hypothesis or experiment ID and wants to understand outcomes.

**Do NOT use when:**

- The experiment run has not completed (no `sqlite.db`).
- The user only wants to configure or launch experiments (use run-experiment instead).

## Quick Reference

| Command | Purpose |
|---------|---------|
| `$PYTHON_PATH .agentsociety/bin/ags.py analysis load-context --workspace . --hypothesis-id ID --experiment-id ID` | Load experiment context |
| `$PYTHON_PATH .agentsociety/bin/ags.py analysis list-tables --db-path PATH` | List tables in SQLite DB |
| `$PYTHON_PATH .agentsociety/bin/ags.py analysis data-summary --db-path PATH` | Full data summary |
| `$PYTHON_PATH .agentsociety/bin/ags.py analysis query-data --db-path PATH --sql "SELECT ..."` | Read-only SQL query |
| `$PYTHON_PATH .agentsociety/bin/ags.py analysis run-code --db-path PATH --code FILE` | Execute analysis code |
| `$PYTHON_PATH .agentsociety/bin/ags.py analysis run-eda --db-path PATH --output-dir DIR --type TYPE` | Generate EDA report |
| `$PYTHON_PATH .agentsociety/bin/ags.py analysis compose-figure --spec FILE` | Combine multiple raster charts/images into one labeled figure |
| `$PYTHON_PATH .agentsociety/bin/ags.py analysis collect-assets --workspace . --hypothesis-id ID --experiment-id ID --output-dir DIR` | Collect report assets |

Use the Python interpreter from `.env`. See `CLAUDE.md` for setup.

## First Move: Analysis Contract Before Plotting

Before generating any chart code or combining existing assets, establish the contract below:

1. Core finding: what specific claim should the next visual defend?
2. Evidence source: which table, query, aggregation, or prior chart supports it?
3. Figure scope: is the artifact a `single chart` or `composite figure`?
4. Figure archetype: choose the simplest structure that carries the message.
5. Output contract: decide filenames, export bundle, and where the artifact will appear in the report.

The highest-priority rule is: each visual artifact must strengthen an already identified analytical finding. Generic EDA should stay in Stage 2 unless it is promoted into Stage 3 by an explicit finding.

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Skipping context loading and going straight to charts | Always start with Stage 1 (`load-context`) |
| Starting from a favorite plot type before defining the message | Write a figure contract first: finding, scope, evidence source, and expected takeaway |
| Generating more than 5 charts without approval | Cap at 5 per single-experiment analysis; ask the user for more |
| Writing analysis output to wrong directory | Single-experiment goes to `presentation/hypothesis_{id}/`, synthesis goes to `synthesis/` |
| Running EDA on all tables indiscriminately | Only run EDA for tables explicitly selected during Stage 2 |
| Inventing helper scripts instead of using the analysis CLI | Use `.agentsociety/bin/ags.py analysis ...` for all mechanical operations |
| Chart without description | Every chart in the report must have a one-line description directly below it |
| Overloaded colors, repeated legends, or weak panel hierarchy | Reuse the chart contract and `references/chart-guide.md` before regenerating |
| Leaving a multi-view finding as several disconnected screenshots | Generate atomic charts first, then assemble a single `figure_{nn}_{slug}.png` with labeled panels |
| Treating simulation output as direct real-world proof | Downgrade the claim strength and record the caveat in the figure contract or report text |
| Using ad hoc matplotlib defaults in one script and styled output in another | Reuse `references/api.md` and `references/common-patterns.md` so colors, fonts, and export rules stay consistent |

## Workflow

```dot
digraph analysis_flow {
    rankdir=LR;
    node [shape=box, style=filled, fillcolor="#E8F4FD"];
    load [label="load-context"];
    scope [label="confirm analysis\nquestion"];
    explore [label="inspect tables\nand data shape"];
    findings [label="propose findings"];
    charts [label="generate approved\ncharts only"];
    report [label="write report"];
    synth [label="cross-experiment\nsynthesis"];

    load -> scope -> explore -> findings -> charts -> report;
    report -> synth [style=dashed, label="user requests comparison"];
}
```

## Pipeline Position

**Predecessors:** run-experiment (completed run with `sqlite.db`)
**Optional inputs:** web-research (supplementary context for interpretation), use-dataset (external datasets for comparison)
**Successors:** agentsociety-paper-orchestrator
**Also feeds:** hypothesis (refinement cycle when analysis informs hypothesis revision)

## Stage Notes

- `stages/01_context.md`: always first
- `stages/02_data_explore.md`: after context is confirmed
- `stages/03_insight_and_viz.md`: after the data shape is understood
- `stages/04_report.md`: after findings and charts are approved
- `stages/05_synthesis.md`: only when the user requests comparison

## Shared References

- Figure contract: `references/figure-contract.md`
- Python backend rule: `references/backend-selection.md`
- Chart selection: `references/chart-guide.md`
- Plot API and palettes: `references/api.md`
- Design rationale: `references/design-theory.md`
- Plot layout patterns: `references/common-patterns.md`
- Chart families: `references/chart-types.md`
- Composite figure assembly: `references/composite-figures.md`
- Chart QA and export checks: `references/qa-contract.md`
- Analysis methods: `references/analysis-methods.md`
- Worked examples: `references/tutorials.md`
- Demo routing: `references/demos.md`
- Output layout: `references/output-conventions.md`
- Report self-check: `checklists/quality.md`

## CLI Tool

Use `$PYTHON_PATH .agentsociety/bin/ags.py analysis` for all mechanical operations:

- `load-context`, `data-summary`, `list-tables`, `query-data`, `run-code`, `run-eda`, `compose-figure`, `collect-assets`

## Subagent Delegation

Stages 2-3 (data exploration + visualization) are the most context-intensive steps, especially with large SQLite databases. Delegate to a subagent when:

- The database has many tables and extensive data exploration is needed
- Complex visualizations require iterative SQL querying and chart refinement
- You are mid-pipeline and context is becoming a concern

**How to delegate:**

1. Complete Stage 1 yourself (`load-context`). Confirm the analysis direction with the user.
2. Dispatch a subagent with the context, DB path, and analysis questions. Instruct it to read `subagent-prompts/data-explorer.md` and follow it.
3. After the subagent returns findings and chart paths, you write the report (Stage 4) yourself with user collaboration.

**Do NOT delegate:** simple analyses with 1-2 tables and straightforward queries.

## Runtime Contract

- Start with Stage 1 for every new analysis request.
- Do not skip directly to charting before the relevant tables and questions are clear.
- Use `.agentsociety/bin/ags.py analysis ...` instead of inventing parallel helper scripts.
- Keep intermediate reasoning in the conversation, not inside generated helper code.
- Treat Stage 5 as optional and only enter it when the user explicitly asks for cross-experiment or cross-hypothesis comparison.
- Use the Python toolchain exclusively for analysis plotting and figure assembly in this skill.

## Hard Constraints

- Maximum 5 charts per single-experiment analysis unless the user explicitly approves a trade-off.
- Every chart plan starts from a finding contract before code generation.
- Every chart that appears in the report must have a one-line description directly below it.
- When one finding requires multiple coordinated views or pre-rendered assets, assemble them into a single `figure_{nn}_{description}.png` with panel labels instead of pasting separate screenshots into the report.
- Run EDA only for tables explicitly selected during Stage 2.
- Write single-experiment output to `presentation/hypothesis_{id}/`.
- Write synthesis output only to the dedicated `synthesis/` root directory, never under `presentation/`.
- Reports are bilingual, Chinese-first by default. Write `report_zh.md` + `report_zh.html` and `report_en.md` + `report_en.html` under `presentation/hypothesis_{id}/`.
- Generated matplotlib charts must use the `Agg` backend, English-only legend text, and a publication-safe rcParams block that keeps SVG text editable.
- Final charts and reports must pass `references/qa-contract.md` before being described as complete.
- Scripts are mechanical helpers only; Claude Code remains the orchestrator.

## Progress Tracking

After analysis report is written:
```bash
$PYTHON_PATH .agentsociety/bin/ags.py research-pipeline update-stage analysis completed
```
