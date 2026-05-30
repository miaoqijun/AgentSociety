# Stage 1: Frame (Analysis Plan)

Goal: lock context and analysis plan before deep exploration (PAP-lite).

## Steps

1. Run `load-context --workspace $WORKSPACE --hypothesis-id $HYP_ID --experiment-id $EXP_ID`.
2. Summarize hypothesis, experiment design, run status, duration, and errors. Confirm direction with user.
3. Record working paths:
   - `DB_PATH=.../run/sqlite.db`
   - `RUN_DIR=.../run`
   - `OUTPUT_DIR=.../presentation/hypothesis_{id}`
   - `CHARTS_DIR=$OUTPUT_DIR/charts`
4. Run `intake --workspace $WORKSPACE --hypothesis-id $HYP_ID --experiment-id $EXP_ID`.
5. Run `memory-context --workspace $WORKSPACE --hypothesis-id $HYP_ID`. If lessons/recipes exist, apply to plan (do not override current user instructions).
6. **Optional external tools** (when relevant — see `references/integrations.md`):
   - **Literature:** `agentsociety-literature-search` — refresh related work before fixing success criteria.
   - **External data:** `agentsociety-use-dataset` — search/download baseline dataset; note paths in plan payload.
   - **Hypothesis revision:** if analysis invalidates HYPOTHESIS.md, pause and use `agentsociety-hypothesis` before continuing.
7. Run `write-plan --payload '{...}'` with `research_question`, `primary_metrics`, `target_tables`, `confirmatory_claims`, `eda_profile` (default `bundle`), optional `eda_profiles`, `synthesis_scope_hypothesis_ids`, optional `external_datasets` paths from step 6.
8. `validate-plan` → `record-attestation` (`phase: frame`, rubric: `research_question_confirmed`, `success_criteria`).
9. `advance --phase explore`.

## Output layout (do not violate)

User artifacts under `presentation/hypothesis_{id}/` only. Harness state under `.agentsociety/analysis/hypothesis_{id}/`. Details: `references/harness.md#output-paths`.

## Exit conditions

- `validate-plan` PASS + frame attestation recorded.
- Working paths explicit.
