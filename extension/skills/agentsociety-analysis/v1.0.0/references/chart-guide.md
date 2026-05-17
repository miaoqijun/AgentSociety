# Chart Guide

Use charts only when they clarify a finding better than text or a small table.
Every chart starts from `references/figure-contract.md`.
If one finding needs several coordinated views, generate atomic charts first and
then assemble them into one composite figure.

Reference map for the current documentation layout:

- plotting scaffold and export rules: `references/api.md`
- chart families: `references/chart-types.md`
- layout and legend patterns: `references/common-patterns.md`
- final acceptance checks: `references/qa-contract.md`

## Selection Guide

- Distribution: histogram, KDE, box, or violin. Use when spread, skew, or outliers matter to the finding.
- Relationship: scatter or line. Verify both columns exist and have enough non-null support.
- Time series: line or area with clear time ordering and labels. Use a ribbon only when uncertainty or range is part of the point.
- Categorical comparison: bar or box. Collapse long tails to Top N plus `other` when categories are crowded.
- Composition over time: stacked area or grouped bars only when category count stays readable.
- Robustness or subgroup comparison: small aligned panels or interval plots. Keep scales comparable when visual comparison matters.
- No chart: skip charting when the table is empty, the core columns are all null, or the text conclusion is obvious without a figure.

## Claim-First Plotting

- Write the finding sentence before choosing the plot type.
- Choose one visual center: the main series, subgroup, or threshold that carries the point.
- Use supporting encodings quietly. Grid lines, secondary series, and annotations should never compete with the core comparison.
- When a chart exists only to prove stability or sanity, prefer a compact panel over a full-width hero chart.

## Compact Archetypes

- `single-panel comparison`: one metric across categories, methods, or cohorts.
- `trend with uncertainty`: a time axis plus one or two emphasized trajectories.
- `distribution focus`: one variable across groups with spread shown clearly.
- `small multi-panel grid`: 2-4 tightly related views that share a scale or grouping rule.
- `composite figure`: 2-4 pre-rendered charts or images assembled under one finding with panel labels.

## Plotting Conventions

- Use `matplotlib` with the `Agg` backend in generated scripts.
- Set `plt.rcParams["font.family"] = "sans-serif"`, define `font.sans-serif`, and keep `svg.fonttype = "none"` so vector text stays editable.
- Reuse palette families and helper functions from `references/api.md` instead of inventing a fresh color system for each chart.
- Reuse layout patterns from `references/common-patterns.md` when the problem is legend placement, multi-panel arrangement, or print-safe encoding.
- Reuse `references/composite-figures.md` when the task is no longer “draw one chart” but “assemble several approved panels into one report-ready figure”.
- Prefer PNG output at about 150-200 dpi for report embedding.
- Keep a same-stem SVG beside the PNG when the chart may later flow into paper, slide, or vector editing.
- For composite figures, export each source panel as PNG first and then combine them with `compose-figure`.
- Keep figure sizes readable and bounded, typically no larger than 12x8 for single panels. Wider grids are acceptable when each panel still has legible labels.
- Always include a title plus axis labels. Use a legend only when it reduces ambiguity.
- Legend text must be English only. Do not use Chinese in `label=...`, `labels=[...]`, or `legend(...)`.
- Sample very large datasets before plotting if full rendering is not needed for the finding.

## Visual Hierarchy

- Keep one restrained palette per report section: neutrals plus one signal family and at most one accent family.
- Reuse the same condition or method color across charts.
- Prefer the semantic palette when direction matters, and the soft method-family palette when related methods need to read as one family.
- Prefer direct labels over legends when series positions are stable and the chart has few lines.
- If the legend is large, dedicate a small legend-only panel or move the legend outside the plotting area.
- Tighten y-axis ranges when the finding depends on small differences, but make the truncation obvious and avoid misleading baselines for bar charts.
- Use hatching or marker shape when color alone would be ambiguous in grayscale or dense print.

## Failure Checks

- If several categories collapse into unreadable labels, trim, sort, or aggregate before plotting.
- If a chart needs a paragraph to explain what to look at, the layout or chart type is still wrong.
- If two panels invite direct comparison, align scales unless the chart explicitly explains why they differ.
- Before treating a chart as final, verify it against `references/qa-contract.md`.
