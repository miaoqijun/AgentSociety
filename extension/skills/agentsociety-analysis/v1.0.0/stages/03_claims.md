# Stage 3: Claims

Goal: register confirmatory and exploratory claims with evidence pointers before any report-level charts.

## Steps

1. Propose 3-5 candidate findings in text; label each `confirmatory` or `exploratory`.
2. For each claim, run `record-claim` with `claim_id`, `statement`, `mode`, `evidence`, `needs_chart`.
3. After user alignment, run `validate-claims` then `record-attestation` with `rubric.claims_user_approved` and `confirmatory_vs_exploratory_clear`.
4. Run `advance --phase refine` when explore+claims gates passed (`gate-status`).

## Exit Conditions

- `validate-claims` gate `PASS` (structural + claims attestation).
