# Analysis Harness Contract

The harness splits work into two layers. Do not duplicate LLM judgment in Python validators.

## Layer 1 — Structural (Python, deterministic)

Checks artifacts, schemas, paths, and cross-references:

| Phase     | Structural checks                                                                                                |
| --------- | ---------------------------------------------------------------------------------------------------------------- |
| frame     | `analysis_plan.yaml` fields via Pydantic                                                                         |
| explore   | `sqlite.db`, target tables, `phase_artifacts.explore` paths exist                                                |
| claims    | `claims.json` shape, confirmatory claim present                                                                  |
| refine    | `validate-refine` (contracts + files on disk); per-chart `validate-chart`                                        |
| produce   | Reports exist, `report_outline.json`, `artifact_manifest.json`, `analysis_summary.json`, asset graph consistency |
| synthesis | Reports exist, `synthesis_brief.json`, source paths on disk                                                      |

Commands: `validate-<phase>` returns `structural_pass` plus issues with `code` (machine-readable).

## Layer 2 — Attestation (LLM, schema-validated)

After you finish the narrative work for a phase, record judgment:

```bash
$PYTHON_PATH .agentsociety/bin/ags.py analysis record-attestation \
  --workspace . --hypothesis-id ID --payload '{
  "phase": "explore",
  "status": "DONE",
  "key_findings": ["..."],
  "artifacts_written": ["presentation/hypothesis_ID/data/eda_quick_stats.md"],
  "rubric": {
    "tables_inspected": ["metrics"],
    "data_limitations": "...",
    "eda_takeaway": "..."
  }
}'
```

Harness state files live under `.agentsociety/analysis/hypothesis_{id}/`, not under `presentation/`.

Rubric keys per phase: see `references/phase-attestation.md`.

`validate-<phase>` also requires a matching attestation. `advance` requires the **prior** phase `gate_pass=true` (`structural_pass` AND `attestation_pass`).

## Monitoring

```bash
$PYTHON_PATH .agentsociety/bin/ags.py analysis gate-status --workspace . --hypothesis-id ID
```

Returns per-phase `structural_pass`, `attestation_pass`, `gate_pass`, and `rubric_keys`.

## LLM responsibilities (not harness)

- Choosing analysis angle and interpreting ambiguous patterns
- Deciding which claims are confirmatory vs exploratory
- Chart design and report prose
- Synthesis narrative and scientific caveats for simulation evidence

## Downstream gates

- **Pipeline:** `research-pipeline update-stage analysis completed` only after `validate-synthesis` PASS.
- **Paper:** `paper-orchestrator build-pack` checks `validate-synthesis` when `presentation/hypothesis_*` exists.

## JSON payloads

CLI `--payload` and on-disk `*.json` metadata use `json-repair` before Pydantic validation. Templates: `references/json-payloads.md`.

## Anti-patterns

- Do not rely on harness keyword search in report body (removed).
- Do not skip `record-attestation` after validate passes.
- Do not write `approved: true` in claims without user alignment — use attestation `rubric.claims_user_approved`.
- Do not treat structural PASS as sufficient quality — see `references/analysis-quality.md`.
