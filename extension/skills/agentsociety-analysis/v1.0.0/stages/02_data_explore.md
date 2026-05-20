# Stage 2: Data Exploration

Goal: identify the 1-3 tables that matter most for the hypothesis and understand their limits.

## Steps

1. Run `$PYTHON_PATH .agentsociety/bin/ags.py analysis list-tables --db-path $DB_PATH` for a cheap overview.
2. Run `$PYTHON_PATH .agentsociety/bin/ags.py analysis data-summary --db-path $DB_PATH` to inspect schema, row counts, and quality signals.
3. Identify the core tables and explain why they are relevant to the analysis direction.
4. If needed, use `$PYTHON_PATH .agentsociety/bin/ags.py analysis query-data --db-path $DB_PATH --sql "SELECT ..."` for targeted checks.
5. Run `$PYTHON_PATH .agentsociety/bin/ags.py analysis run-eda --db-path $DB_PATH --output-dir $OUTPUT_DIR/data --type TYPE --tables table_a` where `TYPE` matches `analysis_plan.eda_profile`.
6. After `run-eda`, pass `--workspace $WORKSPACE --hypothesis-id $HYP_ID` to auto-register explore artifacts (so they flow into `build-report-context` at produce time), or run `record-phase-artifacts` manually.
7. Explain data shape, limitations, and EDA takeaways to the user (LLM judgment — not keyword checks).
8. Run `$PYTHON_PATH .agentsociety/bin/ags.py analysis validate-explore --workspace $WORKSPACE --hypothesis-id $HYP_ID --experiment-id $EXP_ID`.
9. Run `$PYTHON_PATH .agentsociety/bin/ags.py analysis record-attestation` for phase `explore` per `references/phase-attestation.md`.
10. Run `$PYTHON_PATH .agentsociety/bin/ags.py analysis advance --workspace $WORKSPACE --hypothesis-id $HYP_ID --experiment-id $EXP_ID --phase claims`.

## Exit Conditions

- `validate-explore` returns `PASS`.
- The relevant tables and data limits are understood.
