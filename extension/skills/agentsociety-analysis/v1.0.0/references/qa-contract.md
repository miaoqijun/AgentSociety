# QA Contract

Before describing a chart or report as complete, run this minimum acceptance pass. This file replaces the
older scattered chart QA notes and keeps chart review aligned with report outputs, asset directories, and
evidence traceability.

## Chart-Level Checks

| Check | Pass condition |
|---|---|
| Finding alignment | The chart matches the recorded figure contract |
| Data traceability | The table, columns, SQL, or aggregation logic can be stated clearly |
| Axes and units | Title, axis labels, units, and grouping names are complete where needed |
| Text readability | Tick, legend, and annotation text remain clear at report viewing size |
| Legend strategy | The legend does not obscure data and is not needlessly repeated |
| Color consistency | The same method or condition keeps the same color across related charts |
| Grayscale safety | The chart remains interpretable in grayscale or low-saturation projection |
| Export consistency | PNG and SVG use the same title, labels, and legend wording |

## Script-Level Checks

| Check | Pass condition |
|---|---|
| Backend | `matplotlib.use("Agg")` is set |
| Fonts | `font.family = sans-serif` and `font.sans-serif` are configured |
| SVG text | `svg.fonttype = "none"` is set |
| Filenames | The output uses `chart_{nn}_{slug}` or `figure_{nn}_{slug}` |
| Figure cleanup | The script closes figures after export to avoid state buildup |

## Composite-Figure Checks

| Check | Pass condition |
|---|---|
| Panel order | Left-to-right and top-to-bottom order matches report narration |
| Panel labels | `a/b/c...` labels match the report text |
| Hierarchy | Supporting panels do not overpower the main panel |
| Source quality | Text remains readable when each atomic chart is viewed by itself |
| Spec retention | `figure_{nn}_{slug}.json` remains in `charts/` |

## Report-Level Checks

| Check | Pass condition |
|---|---|
| Bilingual reports | `report_zh.md` and `report_en.md` are complete unless scope was explicitly narrowed |
| One-line descriptions | Every figure has a one-line description directly below it |
| Asset consistency | `assets/`, report references, and `artifact_manifest.json` agree |
| Claim boundary | Simulation results are not overstated as real-world causal proof |
| Appendix table | The artifact table in `report_zh.md` matches the actual outputs |

## Minimum Evidence Notes

Every report-facing chart should have at least the following information available:

```text
finding:
table or query:
sample scope:
aggregation rule:
metric definition:
output files:
```

## Failure Triggers

Return to Stage 3 instead of pushing forward if any of the following happen:

- the main conclusion is hard to identify at a glance
- the chart needs a long paragraph just to explain what to look at
- a critical comparison depends on a truncated axis that is not clearly signaled
- the same method changes color across charts
- `artifact_manifest.json` disagrees with the report references
