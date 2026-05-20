# HTML Reports (LLM-authored only)

There is **no** `export-report-html` or Markdown→HTML converter in this stack. **Bilingual HTML is required** alongside MD; the agent (or report-producer subagent) authors both as first-class deliverables.

## When to write HTML

- User explicitly wants browser preview or a shareable static page
- Otherwise deliver Markdown only (`report_zh.md`, `report_en.md`)

## Primary references (in-repo)

1. **`assets/report-shell.reference.html`** — metrics, tabbed interactive EDA iframe, tables, figures, appendix.
2. **`references/html-interactive-eda.md`** — embed `run-eda` interactive HTML (`eda_profile.html` / `eda_sweetviz.html`).
3. **`references/html-design-inspiration.md`** — typography/layout cues from **frontend-design** & Canvas skills (scientific tone).
4. **`references/report-embeddings.md`** — images, tables, paths.
5. **`references/analysis-quality.md`** — same facts as Markdown.

## Making HTML look polished (LLM checklist)

| Element     | Guidance                                                                                                      |
| ----------- | ------------------------------------------------------------------------------------------------------------- |
| Header      | Gradient navy + hypothesis/experiment meta                                                                    |
| Metrics     | 3–4 KPIs from EDA/SQL                                                                                         |
| §数据       | Tab **摘要** (table + prose) + Tab **交互式 EDA** (`iframe` → `data/eda_profile.html` or `eda_sweetviz.html`) |
| §发现       | `.figure-block` per chart; optional metric table                                                              |
| Appendix    | `.artifact-table` + EDA file links                                                                            |
| Limitations | `.limitations` callout                                                                                        |

Avoid: plain `<p>` only, `charts/` paths in `src`, broken relative URLs, inlining entire ydata HTML into one file (use iframe).

## Related extension skills (optional, user-driven)

| Skill                            | Use for analysis HTML                                                  |
| -------------------------------- | ---------------------------------------------------------------------- |
| **agentsociety-analysis** (this) | Contract, paths, `report-shell.reference.html`                         |
| **pdf**                          | Export print-ready PDF from finished HTML or MD if user wants archival |
| **pptx**                         | Slide deck from findings — not a substitute for `report_zh.html`       |
| **docx**                         | Word handoff from Markdown                                             |

Read `support/frontend-design/` (`support-skills.md`) when polishing HTML. Still no MD→HTML pipeline.

**In-IDE alternative:** Cursor **Canvas** (`.canvas.tsx`) suits live metric exploration; **disk reports** stay as `report_zh.html` with iframe to `data/eda_*.html`.

## Workflow

1. `collect-assets` so all report figures exist under `assets/`.
2. Finish bilingual Markdown and pass review gates.
3. Read `report-embeddings.md`, `report-shell.reference.html`, `data/report_context.md`.
4. Write `report_zh.html` / `report_en.html` — mirror MD sections; embed tables and EDA per reference shell.
5. Open in Live Preview: verify images, table scroll, and `data/eda_profile.html` link.

## What not to do

- Do not pipe Markdown through pandoc/scripts as the default path.
- Do not duplicate a different story in HTML vs Markdown.
- Do not embed full EDA profiler HTML via iframe unless the user requests it.
