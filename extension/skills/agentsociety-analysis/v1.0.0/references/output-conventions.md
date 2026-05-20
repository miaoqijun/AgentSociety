# Output Conventions

## Single hypothesis (`presentation/hypothesis_{id}/`)

User-visible artifacts only:

```text
presentation/hypothesis_{id}/
  report_zh.md              # required (validate-release)
  report_en.md              # required
  report_zh.html            # required; LLM-authored (see html-export.md)
  report_en.html            # required; LLM-authored
  artifact_manifest.json
  report_outline.json
  data/                     # EDA + analysis_summary.json only
  charts/                   # scripts + chart_*.png + figure_*.png (+ sidecar json)
  assets/                   # report-embedded copies (from collect-assets)
```

**Do not create** under `presentation/hypothesis_{id}/`:

| Forbidden   | Use instead                                               |
| ----------- | --------------------------------------------------------- |
| `analysis/` | `.agentsociety/analysis/hypothesis_{id}/` (harness state) |
| `figures/`  | `charts/`                                                 |
| `eda/`      | `data/` (e.g. `eda_quick_stats.md`, `eda_profile.html`)   |

## Harness state (machine-readable, hidden from presentation tree)

```text
.agentsociety/analysis/hypothesis_{id}/
  state.yaml
  analysis_plan.yaml
  claims.json

.agentsociety/analysis/synthesis/
  state.yaml
```

Run `analysis intake` to create dirs and migrate legacy `presentation/.../analysis/*.yaml` if present.

## Synthesis (`synthesis/`)

```text
synthesis/
  synthesis_report_zh.md
  synthesis_report_en.md
  synthesis_report_zh.html
  synthesis_report_en.html
  synthesis_brief.json
  charts/                   # optional cross-hypothesis figures (scripts + png)
  assets/                   # report embeds (sync from charts when needed)
  data/                     # optional supporting tables/json
  artifact_manifest.json    # optional
```

No `synthesis/analysis/` — synthesis harness state lives under `.agentsociety/analysis/synthesis/`.

Also under `data/` after `build-report-context`:

- `evidence_index.json`
- `report_context.md`

## Naming

- Charts: `chart_{nn}_{slug}.png` (+ optional `.svg`, `.py` in `charts/`)
- Composites: `figure_{nn}_{slug}.png` (+ `.json` metadata in `charts/`)
- EDA: `data/eda_quick_stats.md`, `data/eda_profile.html`, etc.
- Report embed: `![caption](assets/chart_01_slug.png)` with one-line caption below

## References in reports

See `artifact_manifest.json` template at bottom of prior versions; keep aligned with `report_zh.md` appendix table.
