# Design Theory

Charts in `agentsociety-analysis` are evidence-organizing tools first and visual objects second.
The goal is to let a report reader see, in one scan, what the finding is, where the evidence comes from,
and where to look first.

## Visual Hierarchy

Every finding should have a clear visual center:

- in a single chart, the center is usually the primary series, group, or time trend
- in a multi-panel artifact, the center is usually one main panel while the others explain, decompose, or validate it
- if every panel feels equally important, the finding is usually still too diffuse

## Analysis Charts vs EDA Charts

EDA charts answer: "what is in the data?"

Analysis charts answer: "given the current hypothesis, which evidence supports which judgment?"

That means an analysis chart should also satisfy:

- it is tied to a specific finding
- it names the table, columns, SQL, or aggregation rule behind it
- it has a stable place in the report
- it can be checked and rerun

## Chart Count Discipline

The default limit for a single-experiment report is 5 charts. The goal is not compression for its own sake,
but clear role assignment:

- a main finding chart
- a mechanism or decomposition chart
- a robustness or subgroup chart
- possibly one composite figure when multiple coordinated views are required

If several charts say almost the same thing, merge them into a composite figure or reduce some of them to text.

## Color Rules

- keep the same color for the same method, condition, or group throughout the report
- use color to express semantics before using it for decoration
- reserve red and green mainly for increase/decrease, warning, anomaly, or signed direction
- high saturation across large areas usually weakens the data rather than strengthening it

## Layout Rules

- prefer white backgrounds for report charts
- ordinary charts usually need only left and bottom spines
- if a compact chart feels crowded, reduce legend weight before shrinking text too far
- if a chart needs a long paragraph to explain where to look, the issue is usually chart form or hierarchy

## Composite Figure Rules

A composite figure exists to let multiple views support one finding, not merely to save file count.

Use one only when:

- panel order matches reading order
- panel labels match the report text
- the same condition keeps the same color across panels
- supporting panels stay visually quieter than the main evidence

## Reviewer-Oriented Check

Before and after drawing a chart, ask:

- which conclusion is easiest to misread from this figure?
- which axis range, grouping, or filter is most likely to confuse a reader?
- which comparison needs sample definition, units, or error-bar meaning in nearby prose?

These checks connect directly to `references/qa-contract.md`.
