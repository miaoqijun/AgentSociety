# API Reference

`agentsociety-analysis` uses a fixed Python plotting backend. This file collects the
minimum plotting scaffold, palette constants, export helpers, and reusable utilities
that match the `run-code` contract.

**Copy-paste starter:** `assets/chart_scaffold.reference.py`  
**Recipes:** `references/chart-recipes.md` · **Palettes & QA:** `references/charts.md`

## Required Scaffold

The following block should appear near the top of every matplotlib script:

```python
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

plt.rcParams["font.family"] = "sans-serif"
plt.rcParams["font.sans-serif"] = ["Arial", "DejaVu Sans", "Liberation Sans"]
plt.rcParams["svg.fonttype"] = "none"
```

Why this matters:

- `Agg` keeps rendering stable in headless environments
- the sans-serif stack gives cross-platform fallback consistency
- `svg.fonttype = "none"` keeps SVG text editable

## Recommended Style Helper

Copy from `assets/chart_scaffold.reference.py` — do not duplicate inline:

```python
apply_analysis_style()
fig, ax = plt.subplots(figsize=report_figsize(120))  # 120 mm wide
```

Runtime Plotly: `from agentsociety2.skills.analysis.chart_export import export_plotly_html`

## Optional Seaborn Layer

Use for distribution/box plots, CI bands, faceted small multiples. Still set `Agg` and English legends.

```python
import seaborn as sns

def apply_seaborn_layer(palette="colorblind", context="paper"):
    sns.set_theme(style="ticks", context=context, palette=palette, font_scale=1.05)
    apply_analysis_style()
```

Reset if needed: `sns.reset_defaults()`.

## Export Helper

```python
from pathlib import Path


def save_chart_bundle(fig, stem: str, output_dir: str | Path, dpi: int = 200):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    png_path = output_dir / f"{stem}.png"
    svg_path = output_dir / f"{stem}.svg"
    fig.savefig(png_path, dpi=dpi, bbox_inches="tight", facecolor="white")
    fig.savefig(svg_path, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return png_path, svg_path
```

The default bundle keeps both PNG and same-stem SVG for report embedding and later label adjustments.

## Panel Label Helper

For matplotlib multi-panel figures, place panel labels in axes coordinates:

```python
def add_panel_label(ax, label, x=-0.08, y=1.04, fontsize=11):
    ax.text(
        x,
        y,
        label,
        transform=ax.transAxes,
        fontsize=fontsize,
        fontweight="bold",
        ha="left",
        va="bottom",
        color="#111111",
    )
```

For composite figures produced by `compose-figure`, panel labels are drawn by the CLI tool layer.

## Direct Label Helper

Prefer over legend when ≤3 stable series:

```python
def direct_label_last_point(ax, xs, ys, label, color):
    ax.annotate(
        label,
        xy=(xs[-1], ys[-1]),
        xytext=(6, 0),
        textcoords="offset points",
        color=color,
        fontsize=9,
        fontweight="bold",
        va="center",
    )
```

## Suggested Palettes

See `references/color-palettes.md` for sequential/diverging rules.

### Semantic Palette

```python
PALETTE = {
    "blue_main": "#0F4D92",
    "blue_secondary": "#3775BA",
    "green_soft": "#AADCA9",
    "green_main": "#009E73",
    "red_soft": "#E9A6A1",
    "red_main": "#D55E00",
    "neutral_light": "#CFCECE",
    "neutral_mid": "#767676",
    "neutral_dark": "#4D4D4D",
    "teal": "#42949E",
    "violet": "#9A4D8E",
}
```

Suggested use:

- primary method or condition: `blue_main` or Okabe-Ito `#0072B2`
- control or attenuation: `neutral_mid` / `neutral_dark`
- improvement: `green_main`
- decline, anomaly, or warning: `red_main`

### Method-Family Palette

```python
PALETTE_METHOD_FAMILY = {
    "baseline_dark": "#484878",
    "baseline_mid": "#7884B4",
    "baseline_soft": "#B4C0E4",
    "ours_tiny": "#E4E4F0",
    "ours_base": "#E4CCD8",
    "ours_large": "#F0C0CC",
    "delta_up": "#009E73",
    "delta_down": "#D55E00",
}
```

Use this when several related methods or conditions should read as a coherent family.

## Colormap Rules

| Data type            | Use                                | Avoid               |
| -------------------- | ---------------------------------- | ------------------- |
| Sequential magnitude | `viridis`, `cividis`, `plasma`     | `jet`, `rainbow`    |
| Diverging signed     | `PuOr`, `RdBu`, `BrBG` + `center=` | red–green diverging |
| Correlation matrix   | `RdBu_r`, `center=0`, upper mask   | unlabeled heatmap   |

## Common Utilities

### Dynamic y-axis tightening

```python
def tighten_ylim(ax, values, margin_ratio=0.1):
    values = list(values)
    lo = min(values)
    hi = max(values)
    margin = (hi - lo) * margin_ratio if hi > lo else max(abs(lo) * margin_ratio, 0.1)
    ax.set_ylim(lo - margin, hi + margin)
```

Document truncated axes in figure contract `Reviewer check`.

### Large-data sampling

```python
def sample_frame(frame, n=5000, random_state=42):
    if len(frame) <= n:
        return frame
    return frame.sample(n=n, random_state=random_state)
```

Useful for scatter or dense distribution charts when full rendering adds clutter without improving the finding.

### CI trend (seaborn)

```python
import seaborn as sns

def plot_trend_with_ci(df, x, y, hue, ax=None):
    ax = ax or plt.gca()
    sns.lineplot(data=df, x=x, y=y, hue=hue, errorbar=("ci", 95), markers=True, ax=ax)
    sns.despine(ax=ax)
    return ax
```

Caption must state `95% CI` and aggregation level (per step, per agent, etc.).

## Figure Size Hints

| Chart type          | figsize (inches) |
| ------------------- | ---------------- |
| Single bar/scatter  | `(6, 4)`         |
| Time series         | `(7.5, 4.2)`     |
| Small-multiple grid | `(12, 8)` max    |
| Heatmap             | `(8, 5)`         |

Keep width ≤12 unless composite assembly requires larger atomic panels.

## Naming Conventions

- atomic chart: `chart_{nn}_{description}`
- composite figure: `figure_{nn}_{description}`
- chart script: `chart_{nn}_{description}.py`
- composite spec: `figure_{nn}_{description}.json`

Keep these aligned with `references/harness.md#output-paths`.

## Experience Memory Commands

- `draft-reflection --hypothesis-id ID --experiment-id ID`: create a reviewable
  learning draft from harness state.
- `record-reflection --hypothesis-id ID --payload reflection.json`: store an
  edited reflection payload.
- `record-feedback --hypothesis-id ID --payload feedback.json`: store user
  satisfaction, requested changes, and confirmed preference candidates.
- `review-reflection --hypothesis-id ID`: run the pre-promotion safety/quality
  review used by `promote-reflection`.
- `promote-reflection --hypothesis-id ID`: write project lessons and method
  recipes under `.agentsociety/memory/`.
- `promote-reflection --hypothesis-id ID --include-preferences`: also promote
  preference candidates after explicit user confirmation.
- `memory-context --hypothesis-id ID`: inspect the memory automatically injected
  into `intake`, `status`, and `run-loop`.

See `references/experience-memory.md` for governance and payload details.
