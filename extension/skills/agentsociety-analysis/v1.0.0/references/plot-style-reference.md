# Plot Style Reference

Compatibility alias for older references. The main content now lives in:

- `references/api.md`
- `references/design-theory.md`
- `references/common-patterns.md`

## Current Role

If an older stage note, historical script guide, or existing workspace still points to
`plot-style-reference.md`, treat it as an index for:

- rcParams and export rules: `references/api.md`
- color and layout principles: `references/design-theory.md`
- legend, multi-panel, and axis patterns: `references/common-patterns.md`

## Minimum Required Block

```python
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

plt.rcParams["font.family"] = "sans-serif"
plt.rcParams["font.sans-serif"] = ["Arial", "DejaVu Sans", "Liberation Sans"]
plt.rcParams["svg.fonttype"] = "none"
```
