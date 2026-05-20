# Analysis

`agentsociety2.skills.analysis` is now a pure tool layer for experiment analysis.

Interactive orchestration has moved to the staged Claude Code skill under
`extension/skills/agentsociety-analysis/v1.0.0/`. That staged workflow is responsible
for deciding what to inspect, which charts to generate, when to write reports,
and when to enter cross-experiment synthesis.

## Architecture

```text
data.py        DataReader · ContextLoader · DataSummary
executor.py    code execution helpers · execution result types
output.py      EDAGenerator · AssetManager · ReportPaths
utils.py       path helpers · schema formatting · experiment file collection
models.py      shared data models · output/path constants
```

## Package Responsibilities

- Load experiment context and execution status from a workspace.
- Read SQLite schema, sample rows, and summary statistics.
- Generate quick stats and optional EDA artifacts.
- Execute analysis code in an isolated working directory.
- Collect `run/artifacts` files and generated charts for report embedding.

## Non-Goals

This package no longer owns:

- backend-managed analysis agents
- synthesis/orchestration entry points from the removed backend workflow
- internal LLM contracts or stage prompts

Cross-experiment comparison happens in Stage 6 (required synthesis) of the
`agentsociety-analysis` Claude Code skill.

## Harness

`agentsociety2.skills.analysis.harness` provides staged state, structural validators,
and LLM attestation gates (`record-attestation`, `validate-*`, `gate-status`, `advance`).
Analysis completes when `validate-synthesis` gate passes. See extension skill
`references/harness-contract.md` for the two-layer model.

## Quick Start

```python
from pathlib import Path

from agentsociety2.skills.analysis import ContextLoader, DataReader, EDAGenerator

workspace = Path("./workspace")
db_path = workspace / "hypothesis_1" / "experiment_1" / "run" / "sqlite.db"

context = ContextLoader(workspace).load_context("1", "1")
summary = DataReader(db_path).read_full_summary()
quick_stats = EDAGenerator().generate_quick_stats(
    db_path,
    tables=["agent_profile"],
)
```

## CLI Surface

The staged skill uses
`extension/skills/agentsociety-analysis/v1.0.0/scripts/analysis.py`, which exposes:

- `load-context`
- `list-tables`
- `data-summary`
- `query-data`
- `run-code`
- `run-eda`
- `compose-figure`
- `collect-assets`
- `build-report-context`
- `validate-report-quality`
- `record-report-review`
- `record-synthesis-review`

## Output Layout

Single-experiment outputs live under:
`presentation/hypothesis_{id}/`

- `report_zh.md` / `report_en.md` (required for harness)
- required LLM-authored bilingual `.html` reports (see extension skill `references/html-export.md`)
- `.agentsociety/analysis/hypothesis_{id}/` harness state (`state.yaml`, `analysis_plan.yaml`, `claims.json`)
- `data/analysis_summary.json`
- `data/eda_*.html` or `eda_quick_stats.md`
- `charts/`
- `assets/`

Optional cross-experiment synthesis outputs live under:
`synthesis/`

## Staged Workflow

For the full interactive workflow, use the extension skill files:

- `extension/skills/agentsociety-analysis/v1.0.0/SKILL.md`
- `extension/skills/agentsociety-analysis/v1.0.0/stages/01_frame.md`
- `extension/skills/agentsociety-analysis/v1.0.0/stages/02_data_explore.md`
- `extension/skills/agentsociety-analysis/v1.0.0/stages/03_claims.md`
- `extension/skills/agentsociety-analysis/v1.0.0/stages/04_refine.md`
- `extension/skills/agentsociety-analysis/v1.0.0/stages/05_produce.md`
- `extension/skills/agentsociety-analysis/v1.0.0/stages/06_synthesis.md`

The plotting and composite-figure guidance in that skill now follows a contract-first
reference layout, but remains adapted to
AgentSociety's Python-only analysis toolchain and report output conventions.
