# Progressive Report Assembly (produce)

Scaled from deep-research **report-assembly** for single-hypothesis simulation reports. Execution is **LLM/subagent**, not batch scripts.

## Orchestrator + report-producer

1. Orchestrator: `build-report-context` (mechanical index + digest).
2. Dispatch **report-producer** subagent with paths in `subagent-prompts/report-producer.md`.
3. Subagent writes section-by-section (recommended one major `##` per edit pass):
   - 概述 / setup
   - 数据 (EDA synthesis from `report_context.md`)
   - 发现 (claims + `assets/` figures)
   - 结论 + limitations
   - 附录 (artifact table)
4. Subagent mirrors in English.
5. Subagent fills JSON metadata files.
6. Orchestrator: **report-reviewer** → `record-report-review` → `validate-release` → `record-attestation`.

## Evidence discipline

- Every finding paragraph must trace to `evidence_index.json` sources
- `claims.json` is the claim ledger; reports are narrative only
- No orphan EDA files — if it mattered, it appears in **数据** or appendix

## HTML (optional)

Only when user requests. Subagent reads `assets/report-shell.reference.html` and writes HTML with the **same** facts as Markdown — not a conversion step.
