# Stage 2: Data Exploration

Goal: identify 1–3 core tables, run targeted EDA, record limitations — not final claims.

## Steps

1. `list-tables --db-path $DB_PATH` then `data-summary --db-path $DB_PATH`.
2. Explain why each **plan target table** matters; note row counts, missingness, time range.
3. Optional targeted `query-data --sql "SELECT ..."`.
4. **Read** `support/interactive-viz/SKILL.md` if the user wants interactive exploration — profile choice is in `analysis_plan.eda_profile` (`references/eda.md`).
5. **Default EDA** (harness — reads plan, runs EDA, auto-registers artifacts):

```bash
$PYTHON_PATH .agentsociety/bin/ags.py analysis run-explore-eda \
  --workspace $WORKSPACE --hypothesis-id $HYP_ID --experiment-id $EXP_ID
```

Low-level escape hatch: `run-eda --db-path $DB_PATH --output-dir $OUTPUT_DIR/data --type bundle` (manual `record-phase-artifacts` if no `--workspace`).

6. **External comparison** (if plan lists `external_datasets`): use `agentsociety-use-dataset` → align columns → optional `run-code` summary table → register under `record-phase-artifacts --phase explore`.
7. Explain EDA takeaways and data limits to user — inform doubt/confidence, not confirmatory claims.
8. If run is empty or failed: attestation `DONE_WITH_CONCERNS`, document `blocking_reason`; do not advance to claims without user decision.
9. `validate-explore` → `record-attestation` (`tables_inspected`, `data_limitations`, `eda_takeaway`).
10. `advance --phase claims`.

## Exit conditions

- `validate-explore` PASS (or user accepts `DONE_WITH_CONCERNS` and scope cut).
- EDA paths registered for `build-report-context`.
