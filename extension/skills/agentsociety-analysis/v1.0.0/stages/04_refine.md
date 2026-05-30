# Stage 4: Refine (Charts & Figure Contracts)

Goal: claim-driven visuals only — no decorative exploration charts.

Read `references/analysis-quality.md` (Refine) and `references/charts.md` before code.

## Steps

1. For each claim with `needs_chart: true`, write a **figure contract**. Template: `references/charts.md`.
2. `record-contract --payload '{...}'` per chart.
3. Generate with `run-code` from `assets/chart_scaffold.reference.py` + `references/chart-recipes.md`.
4. On layout/QA issues, **read and apply** `support/scientific-visualization/SKILL.md` (squint test, CI bands, grayscale-safe encoding).
5. Optional: `compose-figure --spec FILE` using `assets/layout-atlas/` wireframes for multi-panel figures.
6. Optional interactive sidecar: `references/eda.md` + `chart_export` when contract sets `presentation_mode: plotly|altair`.
7. `validate-chart` per artifact → `validate-refine` → `record-attestation` (`charts_map_to_claims`, `visual_message_clear`).
8. `advance --phase produce` only when refine `gate_pass`.

## Quality (required)

- One chart = one message; English-only legends; Okabe-Ito / semantic palette locked.
- Same condition → same color across report.
- Simulation limitations in captions where relevant.

## Exit conditions

- Every chart traces to claim + contract.
- `validate-refine` PASS + refine attestation.
