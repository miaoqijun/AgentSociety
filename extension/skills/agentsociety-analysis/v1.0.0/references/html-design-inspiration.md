# HTML Report Design — Inspiration & Constraints

Analysis reports are **scientific deliverables**, not marketing landings. Borrow polish from frontend skills, but keep readability and evidence traceability first.

## Skills to consult (when available)

| Source                                                         | Use for analysis HTML                                             | Do **not** copy blindly                        |
| -------------------------------------------------------------- | ----------------------------------------------------------------- | ---------------------------------------------- |
| **agentsociety-analysis** `report-shell.reference.html`        | Layout, EDA iframe, tables, figures                               | —                                              |
| **`support/frontend-design`** (inside `agentsociety-analysis`) | Typography, CSS variables, tab polish — see `analysis-reports.md` | Bundled support, not a separate pipeline skill |
| **Cursor `canvas` skill**                                      | Hierarchy, labeled charts, flat minimal UI                        | React/in-IDE; disk reports stay HTML + iframe  |
| **deep-research** (optional install)                           | Long-form section flow, evidence tone                             | Citation-heavy research ≠ simulation report    |
| **pdf / docx** skills                                          | Print/export after HTML is stable                                 | Not the primary authoring path                 |

### Adapted principles (simulation report)

1. **One visual system** — reuse shell CSS; don’t mix matplotlib defaults with unrelated web fonts in the body.
2. **Hierarchy** — KPI strip → prose → tables → interactive EDA → findings figures → appendix.
3. **Motion** — light only: tab switch, smooth scroll to `#eda-interactive`; no decorative parallax.
4. **Color** — navy + slate neutrals (shell); chart colors stay in figure PNGs.
5. **Interactive EDA** — embed via **iframe** to `data/eda_profile.html` / `data/eda_sweetviz.html` (see `html-interactive-eda.md`), not rebuilding ydata/Sweetviz inside the report.

## When user wants “more beautiful”

1. Read `references/support-skills.md`, then `support/frontend-design/SKILL.md` + `support/frontend-design/references/analysis-reports.md` (ships with **更新技能**).
2. Refine authored HTML from `report-shell.reference.html` (spacing, table hover, figure cards, EDA tab).
3. Ensure bilingual HTML mirrors the same structure.
4. Optional: **pdf** skill for print export.

## Anti-patterns (from frontend-design “slop” lists)

- Full-page gradients, glassmorphism stacks, emoji section headers
- Replacing tables with screenshot grids
- Inlining 5MB ydata HTML into one file (use iframe + index)
- Breaking relative paths (`assets/`, `data/`) when moving the report folder
