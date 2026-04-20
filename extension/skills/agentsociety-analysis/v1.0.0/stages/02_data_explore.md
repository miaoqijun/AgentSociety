# Stage 2: Data Exploration

Goal: identify the 1-3 tables that matter most for the hypothesis and understand their limits.

## Steps

1. Run `$PYTHON_PATH .agentsociety/bin/ags.py analysis list-tables --db-path $DB_PATH` for a cheap overview.
2. Run `$PYTHON_PATH .agentsociety/bin/ags.py analysis data-summary --db-path $DB_PATH` to inspect schema, row counts, and quality signals.
3. Identify the core tables and explain why they are relevant to the analysis direction.
4. If needed, use `$PYTHON_PATH .agentsociety/bin/ags.py analysis query-data --db-path $DB_PATH --sql "SELECT ..."` for targeted checks.
5. If lightweight profiling is useful, run `$PYTHON_PATH .agentsociety/bin/ags.py analysis run-eda --db-path $DB_PATH --output-dir $OUTPUT_DIR/data --type quick-stats --tables table_a,table_b` only for the selected tables.
6. Report the data shape, likely signal tables, and any limitations or quality issues.

## Exit Conditions

- The relevant tables and data limits are understood, and the user has no further exploration requests before findings are proposed.
