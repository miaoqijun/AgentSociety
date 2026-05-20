# Bundled support for agentsociety-analysis only

Third-party craft skills used when writing or polishing analysis HTML. They ship **inside** this skill version and sync with the workspace symlink — not as separate `agentsociety-*` or Office skills.

| Bundle             | Upstream                                                                                   |
| ------------------ | ------------------------------------------------------------------------------------------ |
| `frontend-design/` | [anthropics/skills](https://github.com/anthropics/skills/tree/main/skills/frontend-design) |

Workspace path (after preset apply):

```text
.claude/skills/agentsociety-analysis/support/frontend-design/
```

Read `references/support-skills.md` for how the orchestrator should use these files.
