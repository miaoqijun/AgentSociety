# Analysis Harness Contract

The harness splits work into two layers. Do not duplicate LLM judgment in Python validators.

## Layer 1 — Structural (Python, deterministic)

Checks artifacts, schemas, paths, and cross-references:

| Phase     | Structural checks                                                                                                |
| --------- | ---------------------------------------------------------------------------------------------------------------- |
| frame     | `analysis_plan.yaml` fields via Pydantic                                                                         |
| explore   | replay catalog, target datasets/tables, `phase_artifacts.explore` paths exist                                    |
| claims    | `claims.json` shape, confirmatory claim present, at least one confirmatory claim approved                        |
| refine    | `validate-refine` (contracts + validated files on disk); per-chart `validate-chart`                              |
| produce   | Reports exist, `report_outline.json`, `artifact_manifest.json`, `analysis_summary.json`, asset graph consistency |
| synthesis | Reports exist, `synthesis_brief.json`, source paths, per-hypothesis summaries/evidence/reviews                   |

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

`record-attestation` automatically stores an `artifact_fingerprint` for the current phase.
If relevant files change afterwards, `validate-<phase>` returns `attestation_stale`; re-read
the changed artifacts and record the attestation again. `advance` requires the **prior**
phase `gate_pass=true` (`structural_pass` AND `attestation_pass`).

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
- Reviewing reflection drafts before promotion; user preferences require explicit confirmation
- Asking for post-analysis user feedback and recording it before durable preference promotion

## Downstream gates

- **Pipeline:** `research-pipeline update-stage analysis completed` only after `validate-synthesis` PASS.
- **Paper:** `paper-toolkit` should consume outputs only after `validate-synthesis` passes when `presentation/hypothesis_*` exists.

## JSON payloads

CLI `--payload` and on-disk `*.json` metadata use `json-repair` before Pydantic validation. Templates: `references/json-payloads.md`.

## Anti-patterns

- Do not rely on harness keyword search in report body (removed).
- Do not skip `record-attestation` after validate passes.
- Do not edit phase artifacts after attestation without re-attesting; stale attestations block gates.
- Do not write `approved: true` in claims without user alignment — use attestation `rubric.claims_user_approved`.
- Do not treat structural PASS as sufficient quality — see `references/analysis-quality.md`.
- Do not treat `draft-reflection` as long-term memory; promote reviewed lessons explicitly and keep project lessons separate from user preferences.
- Do not use `--include-preferences` without `record-feedback` or explicit `user-confirmed` evidence.
