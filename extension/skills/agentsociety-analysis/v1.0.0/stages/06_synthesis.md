# Stage 6: Synthesis + Experience Epilogue

Goal: workspace-level bilingual synthesis, mark analysis pipeline complete, then optional user debrief for experience沉淀.

Tool map: `references/integrations.md`.

## Part A — Synthesis (blocking)

1. Confirm scoped hypotheses have `validate-release` PASS.
2. Refresh `prepare-produce` or `build-report-context` per hypothesis if needed.
3. Dispatch **synthesis-producer** → **synthesis-reviewer** → `record-synthesis-review` (PASS required).
4. Deliver under `synthesis/`: `synthesis_brief.json`, bilingual MD + HTML reports.
5. `validate-synthesis` → `record-attestation` (`scope_sources_integrated`, `limitations_stated`, `independent_review_pass: true`).

Cross-hypothesis narrative: `references/reports.md`.

## Part B — Pipeline handoff (blocking)

```bash
$PYTHON_PATH .agentsociety/bin/ags.py research-pipeline update-stage analysis completed
```

If user wants a manuscript next → invoke **paper-toolkit** plugin (requires reports + `papers/literature_index.json`). Do not start paper before analysis stage is completed.

## Part C — Experience epilogue (required practice, non-blocking)

Run **after** Part A + Part B. Does **not** gate `validate-synthesis` or `update-stage`. `run-loop` / `gate-status` expose `epilogue` when both hypothesis and workspace releases are ready.

1. Chat with user — use `epilogue.conversation_prompts` or ask:
   - What conclusions felt strongest? What still feels uncertain?
   - What should we keep or change in reports/charts next time?
   - Any reusable method or pitfall worth capturing?
2. If answered: `record-feedback --payload '{...}'`.
3. `draft-reflection --workspace $WORKSPACE --hypothesis-id $HYP_ID --experiment-id $EXP_ID`.
4. Walk user through draft; edit if needed → `record-reflection`.
5. `review-reflection` (harness safety check).
6. `promote-reflection` — promotes lessons + `method_recipes/`.
7. **Only if user explicitly confirms preferences:** `promote-reflection --include-preferences` (requires prior `record-feedback`).
8. `memory-context` — show what the next analysis intake will inject.

Full governance: `references/experience-memory.md`.

## Exit conditions

- `validate-synthesis` PASS.
- Pipeline stage updated (`analysis completed`).
- Part C started with user — skipping promotion is OK; do not silently skip the conversation.
