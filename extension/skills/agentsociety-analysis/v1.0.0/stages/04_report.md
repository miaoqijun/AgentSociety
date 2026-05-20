# Stage 4 (legacy name): Report Writing

> **Use `stages/05_produce.md` for the produce stage.** This file is kept as a pointer for older prompts.

# Stage 5: Report Writing (alias)

Goal: write a bilingual report from confirmed findings and approved charts.

## Steps

1. Confirm the section outline before drafting. The default structure is: experiment overview, data description, core findings, conclusions, and appendix.
2. Write the Chinese-first report set under `presentation/hypothesis_{id}/`. By default this means `report_zh.md` plus `report_en.md` before the report is considered complete.
3. Reference charts or composite figures with `![Title](assets/chart_xx_name.png)` or `![Title](assets/figure_xx_name.png)`, and place a one-line description directly below each visual.
4. Include an appendix artifact table inside `report_zh.md`. The table must list `filename`, `type`, `description`, and `finding number` for every referenced chart, composite figure, or other included artifact.
5. Run `$PYTHON_PATH .agentsociety/bin/ags.py analysis collect-assets --workspace $WORKSPACE --hypothesis-id $HYP_ID --experiment-id $EXP_ID --output-dir $OUTPUT_DIR --charts-dir $CHARTS_DIR --filter chart_01_x.png,figure_01_summary.png` with only the visuals actually referenced in the report, so the CLI writes files into `$OUTPUT_DIR/assets/` and keeps only report-referenced PNG/SVG assets there.
6. Write `report_outline.json` in `$OUTPUT_DIR`: section ids (`overview`, `data`, `findings`, `conclusions`, …) and figures with `asset`, `caption`, `finding_number`.
7. Write or update `artifact_manifest.json` in `$OUTPUT_DIR` per `references/output-conventions.md`.
8. Write `data/analysis_summary.json` with `summary`, `key_findings`, `limitations`.
9. Keep `artifact_manifest.json`, `report_outline.json`, and `assets/` aligned.
10. Produce `report_zh.html` and `report_en.html` after Markdown is stable (required for `validate-release`).
11. Apply `checklists/quality.md` before presenting the report for review.
12. Run `$PYTHON_PATH .agentsociety/bin/ags.py analysis validate-release --workspace $WORKSPACE --hypothesis-id $HYP_ID --experiment-id $EXP_ID`.
13. Run `$PYTHON_PATH .agentsociety/bin/ags.py analysis record-attestation --workspace $WORKSPACE --hypothesis-id $HYP_ID --payload '{...}'` with `phase: produce` and rubric from `references/phase-attestation.md`.

## Exit Conditions

- `validate-release` gate returns `PASS` (structural + produce attestation).
- Then proceed to Stage 6 synthesis; not pipeline `analysis completed` until `validate-synthesis`.
