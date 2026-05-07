# Stage 4: Report Writing

Goal: write a bilingual report from confirmed findings and approved charts.

## Steps

1. Confirm the section outline before drafting. The default structure is: experiment overview, data description, core findings, conclusions, and appendix.
2. Write the Chinese-first report set under `presentation/hypothesis_{id}/`. By default this means `report_zh.md` plus `report_en.md` before the report is considered complete.
3. Reference charts with `![Title](assets/chart_xx_name.png)` and place a one-line description directly below each chart.
4. Include an appendix artifact table inside `report_zh.md`. The table must list `filename`, `type`, `description`, and `finding number` for every referenced chart or other included artifact.
5. Run `$PYTHON_PATH .agentsociety/bin/ags.py analysis collect-assets --workspace $WORKSPACE --hypothesis-id $HYP_ID --experiment-id $EXP_ID --output-dir $OUTPUT_DIR --charts-dir $CHARTS_DIR --filter chart_01_x.png,chart_02_y.png` with only the charts actually referenced in the report, so the CLI writes files into `$OUTPUT_DIR/assets/` and keeps only report-referenced charts there.
6. Write or update `artifact_manifest.json` directly in `$OUTPUT_DIR` as part of Stage 4. Claude Code must maintain it using the schema and naming rules from `references/output-conventions.md`.
7. Keep `artifact_manifest.json`, the appendix artifact table, and the files in `assets/` aligned with each other.
8. If requested, produce `report_zh.html` or `report_en.html` after both Markdown reports are stable.
9. Apply `checklists/quality.md` before presenting the report for review.

## Exit Conditions

- The report passes the quality checklist, and the Chinese and English Markdown reports are complete unless the user explicitly narrowed the deliverable, and
- the user confirms it is complete or explicitly asks to return to Stage 3.
