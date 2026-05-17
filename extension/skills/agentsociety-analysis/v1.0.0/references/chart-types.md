# Chart Types

A compact chart-family map for AgentSociety experiment analysis. Use it after the figure contract is clear
and the next question is which visual form best carries the finding.

## 1. Grouped Bar Chart

Use when:

- several methods or conditions are compared on one or more metrics
- units are clear and error bars have a defined meaning

Strengths:

- strong fit for report-facing comparison claims
- maps cleanly to experiment configuration differences

Watch for:

- crowded categories: prefer a shared legend and hidden x labels
- subtle differences: combine with dynamic y-axis tightening

## 2. Time Trend Chart

Use when:

- a metric changes across steps, ticks, days, rounds, or phases
- before/after intervention behavior matters

Strengths:

- good for system evolution
- easy to augment with event markers and phase boundaries

Watch for:

- time order must be explicit
- smoothing should not hide raw structure when raw structure matters

## 3. Distribution Chart

Use when:

- spread, skew, outliers, or long tails matter
- several agent groups or experiment settings need distribution comparison

Common forms:

- box plot
- violin plot
- histogram
- KDE

Watch for:

- sample if the dataset is very large
- state what the box or interval means

## 4. Scatter or Relationship Chart

Use when:

- two continuous variables have an analytically meaningful relationship
- the chart should operate at agent level, episode level, or another granular unit

Watch for:

- reduce overplotting with alpha, sampling, or binning
- only move such a chart into the final report when the relationship matters to the hypothesis

## 5. Heatmap

Use when:

- the result is naturally a metric matrix
- agent-type by feature matrices are central
- time-window by region or group summaries need matrix structure

Watch for:

- keep scale direction intuitive
- explain range and normalization clearly

## 6. Small Multiples

Use when:

- one finding requires subgroup, condition, or phase comparisons side by side
- each panel shares the same x/y semantics

Watch for:

- share scales whenever comparison benefits from it
- if panels multiply too far, trim to Top N or switch to a different summary form

## 7. Composite Figure

Use when:

- one finding needs several complementary views
- several already-approved atomic charts should become a single report-facing artifact

Typical structures:

- hero + support row
- triptych
- 2x2 grid

For assembly details, use `references/composite-figures.md`.

## Quick Routing

```text
single-metric comparison       -> grouped bar chart
time evolution                 -> trend chart
spread or outliers             -> distribution chart
variable relationship          -> scatter chart
matrix structure               -> heatmap
one finding, multiple views    -> small multiples or composite figure
pre-rendered charts to merge   -> composite figure
```
