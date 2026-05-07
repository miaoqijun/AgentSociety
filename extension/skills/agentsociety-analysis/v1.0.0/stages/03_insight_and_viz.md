# Stage 3: Insight and Visualization

Goal: convert data understanding into a small set of findings with evidence-backed charts.

## Steps

1. Propose 3-5 candidate findings in text first. For each finding, name the supporting table or query and say whether a chart is necessary.
2. For each finding that needs a chart, explain the chart type, query or computation logic, and expected takeaway. Use `references/chart-guide.md` when choosing chart forms.
3. Wait for the user to confirm, trim, or revise the finding and chart plan before generating visuals.
4. Generate charts one by one via `$PYTHON_PATH .agentsociety/bin/ags.py analysis run-code --db-path $DB_PATH --code $CHARTS_DIR/chart_{nn}_{description}.py --timeout 120`.
5. Keep generated code and chart outputs under `$CHARTS_DIR` so `run-code` persists artifacts relative to the `--code` file parent directory. Name chart files according to `references/output-conventions.md`, for example `chart_{nn}_{description}.png`.
6. Legend text must stay in English even if the surrounding discussion is Chinese. Use English-only values for `label=...`, `labels=[...]`, and `legend(...)`.
7. After each chart, show the result, explain what it supports, and revise if the user requests changes.
8. If a chart needs extra verification, use `$PYTHON_PATH .agentsociety/bin/ags.py analysis query-data` before regenerating it.
9. If the same chart code fails three times, stop and ask whether to skip, simplify, or revise the finding.
10. Once the user confirms the findings set, prepare a structured claims JSON payload with one entry per confirmed finding. Each entry should include at least `statement`, `confidence`, and `evidence`.

## Exit Conditions

- Findings are confirmed by the user.
- Any approved charts are generated within budget and tied to those findings.
