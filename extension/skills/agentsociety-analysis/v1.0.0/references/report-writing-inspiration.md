# Report Writing — External Skills & Framework Integration

## Integrated in AgentSociety

| Capability           | How                                                    | Inspiration                                                                                 |
| -------------------- | ------------------------------------------------------ | ------------------------------------------------------------------------------------------- |
| Evidence aggregation | `build-report-context` → `report_context.md`           | deep-research evidence store                                                                |
| Report narrative     | **report-producer** subagent                           | deep-research report-assembly                                                               |
| HTML (required)      | LLM writes HTML + iframe to `run-eda` interactive HTML | `report-shell.reference.html`, `html-interactive-eda.md`, **frontend-design** / Canvas cues |
| Explore/charts       | **data-explorer** subagent                             | competeai analysis discipline                                                               |
| Synthesis            | **synthesis-producer** subagent                        | cross-run integration                                                                       |

## Subagent prompts (this skill)

- `subagent-prompts/data-explorer.md`
- `subagent-prompts/report-producer.md`
- `subagent-prompts/synthesis-producer.md`

## External repos (optional extra install)

| Source                                  | Link                                                              |
| --------------------------------------- | ----------------------------------------------------------------- |
| **frontend-design** (bundled support)   | `support/frontend-design/` — UI polish for `report_*.html`        |
| deep-research                           | https://github.com/199-biotechnologies/claude-deep-research-skill |
| competeai competition-dynamics-analysis | `auto-agent/competeai_skills_zh/competition-dynamics-analysis/`   |
| docx / pdf (workspace skills)           | Word/PDF when user wants office formats                           |

Mechanical HTML conversion was **removed** on purpose — quality comes from LLM authoring against `report_context.md` and quality references.
