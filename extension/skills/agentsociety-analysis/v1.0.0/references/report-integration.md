# Report Integration (EDA → Charts → Final Report)

Goal: **one narrative thread**. Tool outputs stay in `data/` and `charts/`, but the **final report** must synthesize them — not leave EDA in a silo.

## Pipeline

```text
explore: run-eda → presentation/hypothesis_{id}/data/eda_*
         record-phase-artifacts (paths)
claims:  record-claim (evidence pointers)
refine:  run-code → charts/chart_*.png
         record-contract
produce: build-report-context  ← aggregates everything
         dispatch report-producer (or equivalent) reading data/report_context.md
         write report_zh.md / report_en.md (sections cite EDA + charts)
         write analysis_summary.json, report_outline.json, artifact_manifest.json
         validate-release
```

## Mechanical aggregation (`build-report-context`)

```bash
$PYTHON_PATH .agentsociety/bin/ags.py analysis build-report-context \
  --workspace . --hypothesis-id $HYP_ID
```

Writes:

| File                       | Role                                                                                |
| -------------------------- | ----------------------------------------------------------------------------------- |
| `data/evidence_index.json` | Machine index: every source, `kind`, `phase`, target `report_section`               |
| `data/report_context.md`   | LLM digest: excerpts grouped by overview / data / findings / conclusions / appendix |

Sources pulled from:

- `phase_artifacts` in harness state (EDA paths you registered)
- All files under `data/` (except the index itself)
- `charts/chart_*.png`, `charts/figure_*.png`
- `claims.json` and `figure_contracts` in harness state

## How to write each report section

| Section         | Integrate                                                                                                                                             |
| --------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------- |
| **overview**    | Research question from `analysis_plan.yaml`; experiment design one paragraph                                                                          |
| **data**        | **Synthesize** `eda_quick_stats.md` / profiling HTML takeaways — row counts, missingness, metric ranges; link `data/eda_*.html` in appendix if needed |
| **findings**    | One subsection per confirmatory claim; embed `assets/chart_*.png`; numbers must match SQL/EDA                                                         |
| **conclusions** | Answer research question; copy limitations from plan + explore attestation                                                                            |
| **appendix**    | Artifact table + optional EDA HTML links                                                                                                              |

## Rules

1. **Do not** paste full EDA HTML into the report body — summarize in prose + tables; link full `data/eda_*.html` in appendix (see `report-embeddings.md`).
2. **Do** register every explore output via `record-phase-artifacts` so it enters `evidence_index.json`.
3. **Do** run `build-report-context` immediately before drafting reports.
4. HTML (required): LLM-authored `report_zh.html` / `report_en.html` per `references/html-export.md` and `assets/report-shell.reference.html` — required for `validate-release` PASS.

## Synthesis (Stage 6)

Run `build-report-context` per hypothesis first. In `synthesis_brief.json` list `source_artifacts` including each `data/report_context.md` or `report_zh.md`. Cross-hypothesis synthesis should **compare** integrated findings, not re-scatter raw EDA files.

See `references/report-writing-inspiration.md` for borrowable external skill patterns.
