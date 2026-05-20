# Bundled support (inside agentsociety-analysis)

## Layout

Report/UI helpers live under **`support/`** in this skill version. After **更新技能**, they appear at:

```text
.claude/skills/agentsociety-analysis/support/<bundle>/
```

Example (HTML polish):

```text
support/frontend-design/SKILL.md
support/frontend-design/references/analysis-reports.md
```

Use paths relative to the active `agentsociety-analysis` skill root, or the workspace paths above.

## Taxonomy

| Tier                     | Examples                                                             | Where                                       |
| ------------------------ | -------------------------------------------------------------------- | ------------------------------------------- |
| **AgentSociety product** | `agentsociety-analysis`, `agentsociety-run-experiment`, paper skills | `.claude/skills/agentsociety-*`             |
| **Office**               | `pdf`, `docx`, `xlsx`, `pptx`                                        | `.claude/skills/pdf` …                      |
| **Analysis support**     | `frontend-design`                                                    | **Inside** `agentsociety-analysis/support/` |

Support bundles are **not** listed as their own pipeline skills. Only invoke them while running **agentsociety-analysis** (e.g. stage 5 HTML).

## Claude Code note

Nested folders under `agentsociety-analysis/` are **not** registered as separate top-level skills. Read `support/.../SKILL.md` as files while this skill is active. If you need a standalone activatable `frontend-design` skill, install it yourself under `.claude/skills/frontend-design` (optional; not bundled by AgentSociety).

## Adding more bundles

1. Add `support/<name>/` under `v1.0.0/` in the extension.
2. Document scope in `support/<name>/references/` or a short bridge markdown.
3. Link from `html-design-inspiration.md` / `html-export.md` as needed.
