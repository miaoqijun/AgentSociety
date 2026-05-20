# Stage 5: Produce (Bilingual Report)

Goal: write reports that a skeptical reader can trust — not just files that pass `validate-release`.

## Steps

1. Orchestrator: `build-report-context` after refine passes.
2. Dispatch **report-producer** (`subagent-prompts/report-producer.md`).
3. Dispatch **report-reviewer** (`subagent-prompts/report-reviewer.md`) — independent; must not be the same run as producer.
4. `record-report-review` with verdict **PASS** (score ≥ 4, no blocking issues).
5. On REVISE/FAIL: send `revision_instructions` back to report-producer → re-review (do not attest).
6. Deliver `report_zh.md`, `report_en.md`, `report_zh.html`, `report_en.html` (see `html-export.md`).
7. `validate-report-quality` (optional pre-check) → `validate-release` → `record-attestation` (`phase: produce`, `independent_review_pass: true`).

See `references/report-review.md`, `references/report-assembly.md`, `checklists/quality.md`.

## Exit Conditions

- `validate-release` PASS (structure + mechanical quality + fresh independent review).
- Limitations explicit in prose and `analysis_summary.json`.
- Proceed to Stage 6 synthesis (required).
