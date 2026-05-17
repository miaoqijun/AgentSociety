# Output Conventions

Single-experiment outputs live under:

```text
presentation/
  hypothesis_{id}/
    report_zh.md
    report_zh.html
    report_en.md
    report_en.html
    report.md
    report.html
    assets/
    charts/
    data/
    artifact_manifest.json
```

Cross-experiment synthesis outputs live under:

```text
synthesis/
  synthesis_report_zh.md
  synthesis_report_en.md
  assets/
  artifact_manifest.json
```

## Naming Rules

- Chart filenames: `chart_{nn}_{description}.png`
- Optional companion vector export: `chart_{nn}_{description}.svg`
- Matching plotting scripts may live beside them as `chart_{nn}_{description}.py`
- Composite figure filenames: `figure_{nn}_{description}.png`
- Composite figure metadata sidecar: `figure_{nn}_{description}.json`
- EDA outputs: `eda_{type}_{table}.html` or similar type-specific names
- Keep only report-referenced charts in `assets/`
- Keep intermediate plotting scripts, atomic charts, and composite figure specs under `charts/`
- When `collect-assets` filters a referenced chart PNG, sibling same-stem vector exports are preserved automatically.
- When `collect-assets` filters a referenced composite figure PNG, its same-stem JSON sidecar should remain under `charts/` as production metadata rather than being copied into `assets/`.
- Do not write synthesis outputs under `presentation/`; they belong directly in `synthesis/`.
- Do not store temporary EDA screenshots in `assets/` unless the report explicitly references them.

## Report References

- Reference charts or composite figures as `![Title](assets/chart_01_example.png)` or `![Title](assets/figure_01_example.png)`.
- Put a one-line description immediately below each chart or composite figure.
- Keep `artifact_manifest.json` aligned with the final report and asset set.

## Artifact Manifest

Claude Code writes and updates `artifact_manifest.json` directly. Keep it consistent with the appendix artifact table in `report_zh.md`.

```json
{
  "hypothesis_id": "1",
  "generated_at": "2026-04-16T15:30:00",
  "artifacts": [
    {
      "filename": "chart_01_distribution.png",
      "type": "chart",
      "description": "Distribution plot for finding 1",
      "finding_number": 1,
      "included_in_report": true
    }
  ]
}
```
