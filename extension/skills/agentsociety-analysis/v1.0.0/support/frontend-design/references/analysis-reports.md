# Frontend Design × AgentSociety Analysis Reports

Read `support/frontend-design/SKILL.md` (or `.claude/skills/agentsociety-analysis/support/frontend-design/SKILL.md` in the workspace) for craft. This file **scopes** it to simulation analysis HTML — not landing pages.

## When to combine skills

| Task                                | Skills                                                                                                     |
| ----------------------------------- | ---------------------------------------------------------------------------------------------------------- |
| `report_zh.html` / `report_en.html` | **agentsociety-analysis** + **frontend-design** (this bridge)                                              |
| `presentation/.../data/eda_*.html`  | Already interactive (ydata/Sweetviz); embed via iframe per agentsociety-analysis `html-interactive-eda.md` |
| Marketing site / dashboard          | frontend-design only                                                                                       |

## Non-negotiable analysis constraints (override frontend-design defaults)

1. **Evidence first** — numbers match `report_context.md` and Markdown reports; no decorative KPIs.
2. **Scientific tone** — prefer `assets/report-shell.reference.html` navy/slate system; do **not** apply purple-gradient-on-white or chaotic maximalism unless user explicitly asks.
3. **Interactivity** — preserve Tab + iframe to `data/eda_profile.html` / `data/eda_sweetviz.html`; polish tab bar, iframe chrome, table hover only.
4. **No MD→HTML** — refine authored HTML; do not run pandoc on `report_zh.md`.
5. **Paths** — `assets/` for figures, `data/` for EDA; run `collect-assets` before final HTML.

## What to steal from frontend-design

- Distinctive but readable font pairing (e.g. display for `h1`, refined body — avoid Inter if possible)
- CSS variables for spacing and colors aligned with shell
- Subtle motion: tab transition, table row hover, optional `prefers-reduced-motion` respect
- Refined figure cards and data-table typography

## Read order

1. `agentsociety-analysis` → `html-export.md`, `report-embeddings.md`, `html-interactive-eda.md`
2. `assets/report-shell.reference.html` (in agentsociety-analysis v1.0.0)
3. `support/frontend-design/SKILL.md` (general craft)
4. This file (scope guardrails)

## Source

Bundled from [anthropics/skills `frontend-design`](https://github.com/anthropics/skills/tree/main/skills/frontend-design) (Apache-2.0, see `LICENSE.txt`).
