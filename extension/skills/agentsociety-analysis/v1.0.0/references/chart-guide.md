# Chart Guide

Use charts only when they clarify a finding better than text or a small table.

## Selection Guide

- Distribution: histogram, KDE, or violin. Avoid pie charts for continuous values.
- Relationship: scatter or line. Verify both columns exist and have enough non-null support.
- Time series: line or area with clear time ordering and labels.
- Categorical comparison: bar or box. Collapse long tails to Top N plus `other` when categories are crowded.
- Composition over time: stacked area or grouped bars only when category count stays readable.
- No chart: skip charting when the table is empty, the core columns are all null, or the text conclusion is obvious without a figure.

## Plotting Conventions

- Use `matplotlib` with the `Agg` backend in generated scripts.
- Prefer PNG output at about 150 dpi.
- Keep figure sizes readable and bounded, typically no larger than 12x8.
- Always include a title plus axis labels. Add a legend only when it helps.
- Legend text must be English only. Do not use Chinese in `label=...`, `labels=[...]`, or `legend(...)`.
- Sample very large datasets before plotting if full rendering is not needed for the finding.
