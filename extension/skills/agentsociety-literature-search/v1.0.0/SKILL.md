---
name: agentsociety-literature-search
version: 1.0.0
description: Use when academic literature needs to be gathered or refreshed for a research topic, especially at the beginning of a project.
---

# Literature Search

Search academic literature from a remote API and save results to the workspace `papers/` directory. Queries all configured data sources (local, arXiv, CrossRef, OpenAlex) by default.

## When to Use

- User mentions "literature", "papers", "related work", "survey", or "background research"
- Starting a new research topic and `TOPIC.md` does not yet exist
- Existing `TOPIC.md` needs enrichment with more references
- User asks "what has been published on X?"

**Do NOT use when:**

- User already has a well-defined hypothesis and wants to design experiments (use hypothesis skill)
- User needs to run a simulation (use experiment-config skill)

## Quick Reference

Use the Python interpreter from `.env`. See `CLAUDE.md` for setup.
Run commands from the workspace root through `.agentsociety/bin/ags.py`.

| Action | Command |
|--------|---------|
| Basic search | `$PYTHON_PATH .agentsociety/bin/ags.py literature-search "query"` |
| Limit results | `$PYTHON_PATH .agentsociety/bin/ags.py literature-search "query" --limit 5` |
| Year range | `$PYTHON_PATH .agentsociety/bin/ags.py literature-search "query" --year-from 2020 --year-to 2024` |
| Complex topic | `$PYTHON_PATH .agentsociety/bin/ags.py literature-search "complex query" --multi-query` |
| Custom workspace | `$PYTHON_PATH .agentsociety/bin/ags.py literature-search "query" --workspace /path/to/dir` |

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| query | string | Yes | Search query (positional) |
| --limit | integer | No | Number of results (default: 10) |
| --year-from | integer | No | Start year filter |
| --year-to | integer | No | End year filter |
| --workspace | string | No | Workspace path (default: cwd) |
| --multi-query | flag | No | Split complex queries into subtopics |

## Output

```
papers/
  literature_index.json    # Auto-created/updated catalog
  article_title.md         # Per-article markdown summaries (saved directly in papers/)
```

Each article contains: `title`, `authors`, `abstract`, `year`, `journal`, `doi`, `url`, `score`, `source`.

## Prerequisites

Configure in `.env`:
```
LITERATURE_SEARCH_API_URL=http://localhost:8008/api/search
LITERATURE_SEARCH_API_KEY=lit-your-api-key-here
```

Validation checks: (1) service health (`/health`), (2) API key auth (`/api/stats`).

See `references/data-sources.md` for data source details.

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Running without `.env` configured | Set `LITERATURE_SEARCH_API_URL` and `LITERATURE_SEARCH_API_KEY` first |
| Using too broad a query without `--limit` | Add `--limit` to avoid overwhelming results |
| Forgetting `--multi-query` for complex topics | Use `--multi-query` when query spans multiple research areas |
| Not checking validation before searching | Run health/auth check first to avoid silent failures |
| Searching on wrong workspace | Specify `--workspace` explicitly when not in project root |

## Pipeline Position

**Predecessors:** None (entry point)
**Successors:** hypothesis
**Required Sub-Skills:** None

## Progress Tracking

After search completes successfully:
```bash
$PYTHON .agentsociety/bin/ags.py research-pipeline update-stage literature_search completed --metadata '{"paper_count": N}'
```
