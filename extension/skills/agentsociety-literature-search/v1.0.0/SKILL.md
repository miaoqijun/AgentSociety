---
name: agentsociety-literature-search
version: 1.0.0
description: Use when academic literature needs to be gathered or refreshed for a research topic, especially at the beginning of a project.
---

# Literature Search

Search academic literature from a remote API and save results to the workspace `papers/` directory. Queries all configured data sources (local, arXiv, CrossRef, OpenAlex) by default.

This skill has two responsibilities:

1. Retrieve and save structured literature metadata using the configured AgentSociety literature API.
2. Organize the saved results so later skills can cite, inspect, and optionally enrich them with full-text PDFs.

It does not treat full-text download as part of the search command. Full-text retrieval is a follow-up research action performed only when it is useful and legally accessible.

## When to Use

- User mentions "literature", "papers", "related work", "survey", or "background research"
- Starting a new research topic and `TOPIC.md` does not yet exist
- Existing `TOPIC.md` needs enrichment with more references
- User asks "what has been published on X?"
- User asks to refresh or expand `papers/literature_index.json`

**Do NOT use when:**

- User already has a well-defined hypothesis and wants to design experiments (use hypothesis skill)
- User needs to run a simulation (use experiment-config skill)
- User only wants to read a local PDF already in the workspace; open or summarize that file directly

## Quick Reference

Use the Python interpreter from `.env`. See `CLAUDE.md` for setup.
Run commands from the workspace root through `.agentsociety/bin/ags.py`.

| Action                  | Command                                                                                                                                |
| ----------------------- | -------------------------------------------------------------------------------------------------------------------------------------- |
| Basic search            | `$PYTHON_PATH .agentsociety/bin/ags.py literature-search "query"`                                                                      |
| Limit results           | `$PYTHON_PATH .agentsociety/bin/ags.py literature-search "query" --limit 5`                                                            |
| Year range              | `$PYTHON_PATH .agentsociety/bin/ags.py literature-search "query" --year-from 2020 --year-to 2024`                                      |
| Complex topic           | `$PYTHON_PATH .agentsociety/bin/ags.py literature-search "complex query" --multi-query`                                                |
| Custom workspace        | `$PYTHON_PATH .agentsociety/bin/ags.py literature-search "query" --workspace /path/to/dir`                                             |
| List PDF candidates     | `$PYTHON_PATH .agentsociety/bin/ags.py literature-full-text candidates`                                                                |
| Download open PDF       | `$PYTHON_PATH .agentsociety/bin/ags.py literature-full-text download --entry 1`                                                        |
| Register local PDF      | `$PYTHON_PATH .agentsociety/bin/ags.py literature-full-text register --entry 1 --file /path/to/paper.pdf`                              |
| Mark no PDF found       | `$PYTHON_PATH .agentsociety/bin/ags.py literature-full-text mark --entry 1 --status no_candidate --reason "No open PDF URL available"` |
| List enrichable entries | `$PYTHON_PATH .agentsociety/bin/ags.py literature-full-text enrich --dry-run`                                                          |
| Mark entry as enriched  | `$PYTHON_PATH .agentsociety/bin/ags.py literature-full-text enrich --entry 1`                                                          |

## Parameters

| Parameter     | Type    | Required | Description                          |
| ------------- | ------- | -------- | ------------------------------------ |
| query         | string  | Yes      | Search query (positional)            |
| --limit       | integer | No       | Number of results (default: 10)      |
| --year-from   | integer | No       | Start year filter                    |
| --year-to     | integer | No       | End year filter                      |
| --workspace   | string  | No       | Workspace path (default: cwd)        |
| --multi-query | flag    | No       | Split complex queries into subtopics |

Full-text helper parameters:

| Command                           | Important Parameters                                          | Description                                                                   |
| --------------------------------- | ------------------------------------------------------------- | ----------------------------------------------------------------------------- |
| `literature-full-text candidates` | `--entry N` optional                                          | Show candidate URLs inferred from `literature_index.json`                     |
| `literature-full-text download`   | `--entry N`, `--url URL` optional                             | Try open PDF URLs and update `extra_fields.full_text`                         |
| `literature-full-text register`   | `--entry N`, `--file PATH`                                    | Copy/register a local PDF and update the index                                |
| `literature-full-text mark`       | `--entry N`, `--status no_candidate\|failed`, `--reason TEXT` | Record why a PDF is unavailable                                               |
| `literature-full-text enrich`     | `--entry N` or `--dry-run`                                    | List or mark entries whose Markdown notes have been enriched via web research |

## Recommended Workflow

1. Read `TOPIC.md` if it exists. Use the research question, scope, target population, and key constructs to form the query.
2. Run one focused search first. Prefer 5-10 results unless the user asks for breadth.
3. Use `--year-from` / `--year-to` when the user wants recent work or a defined historical window.
4. Use `--multi-query` for topics with multiple constructs, methods, or domains.
5. Inspect `papers/literature_index.json` after the command completes. Confirm that entries were appended and that each entry has a local Markdown `file_path`.
6. Summarize what was found in research terms, not just as a list of titles.
7. If the user or downstream task needs original PDFs, follow "Optional Full-Text Retrieval" below.

## Output

```
papers/
  literature_index.json    # Auto-created/updated catalog
  article_title.md         # Per-article markdown summaries (saved directly in papers/)
  full_texts/              # Optional PDF originals downloaded by Claude/user
```

Each article contains: `title`, `authors`, `abstract`, `year`, `journal`, `doi`, `url`, `score`, `source`.
The catalog keeps the local Markdown note in `file_path`, so downstream tools can cite it as `@papers/article_title.md`.

The Markdown note is the primary local artifact. It should remain readable even when the original article PDF is not available.

## Index Contract

`papers/literature_index.json` follows this shape:

```json
{
  "version": "1.0",
  "created_at": "...",
  "updated_at": "...",
  "entries": [
    {
      "title": "Article title",
      "journal": "Journal or venue",
      "doi": "10.xxxx/xxxx",
      "abstract": "...",
      "file_path": "papers/article_title.md",
      "file_type": "markdown",
      "source": "literature_search",
      "query": "original query",
      "avg_similarity": 0.84,
      "saved_at": "...",
      "extra_fields": {
        "authors": ["..."],
        "year": 2024,
        "url": "https://..."
      }
    }
  ]
}
```

Keep `file_path` pointed at the Markdown note. If a PDF is downloaded later, put that path in `extra_fields.full_text.file_path` instead of replacing `file_path`.

## Optional Full-Text Retrieval

The search command does not automatically download publisher files. After a successful search, decide whether original PDFs are actually needed.

When the user asks for full texts, or when a downstream task genuinely needs the original article:

1. Run `literature-full-text candidates` to see what can be inferred from `papers/literature_index.json`.
2. Prefer explicit PDF URLs from metadata. For arXiv records, the helper converts `https://arxiv.org/abs/<id>` to `https://arxiv.org/pdf/<id>.pdf`.
3. Download only open-access files or files the user has provided permission to access. Do not bypass paywalls.
4. Use `literature-full-text download --entry N` for inferred candidates, or add `--url URL` when the user gives a specific PDF URL.
5. If the user provides a local PDF, use `literature-full-text register --entry N --file /path/to/paper.pdf`.
6. If no PDF is available, use `literature-full-text mark --entry N --status no_candidate --reason "..."`
7. The helper saves PDFs under `papers/full_texts/` and updates the entry with download status:

```json
"extra_fields": {
  "full_text": {
    "status": "downloaded",
    "file_path": "papers/full_texts/example.pdf",
    "source_url": "https://arxiv.org/pdf/2401.01234.pdf"
  }
}
```

If no open PDF is available, record a useful status instead:

```json
"extra_fields": {
  "full_text": {
    "status": "no_candidate",
    "reason": "Only DOI/landing page metadata was available."
  }
}
```

Keep `file_path` pointing to the Markdown note. The PDF path belongs in `extra_fields.full_text.file_path` so the literature index viewer can show both the readable note and the original PDF.

For more details, see `references/full-text-retrieval.md`.

### Enriching Notes When PDF Is Unavailable

When a PDF cannot be downloaded (paywall, no open access, etc.), you should still try to enrich the Markdown note with substantive content. Use web search to gather information about the article.

**Workflow:**

1. Identify entries with `full_text.status` of `"failed"` or `"no_candidate"`:
   ```bash
   $PYTHON_PATH .agentsociety/bin/ags.py literature-full-text enrich --dry-run
   ```
2. For each such entry, use your web search capability to find:
   - Blog posts, review articles, or preprint versions discussing the paper
   - Wikipedia or scholarly commentary referencing the work
   - Author pages, conference slides, or presentation videos
   - Open-access preprint versions on arXiv, bioRxiv, SSRN, etc.
3. Read and synthesize the search results. Then append a `## Web Research Notes` section to the existing Markdown note at `file_path`:

```markdown
## Web Research Notes

*Enriched via web search on YYYY-MM-DD. Original PDF was not available.*

### Key Findings
- (Summarize the main claims, methodology, and results based on what you found)

### Methodology Highlights
- (Describe the experimental or analytical approach as reported in secondary sources)

### Context and Impact
- (How this work relates to the field, citations, follow-up work)

### Sources
- [Source 1 title](url)
- [Source 2 title](url)
```

4. After appending the notes, mark the entry as enriched:
   ```bash
   $PYTHON_PATH .agentsociety/bin/ags.py literature-full-text enrich --entry N
   ```

**Rules:**
- Do not fabricate or guess content. Only include information you found through actual web search.
- Always cite the web sources you used.
- If the web search also yields nothing useful, leave the note as-is and do not append a section.
- If you find an open-access preprint version (e.g., arXiv), prefer downloading that PDF instead of just enriching the note.

## Prerequisites

Configure in `.env`:
```
LITERATURE_SEARCH_API_URL=http://localhost:8008/api/search
LITERATURE_SEARCH_API_KEY=lit-your-api-key-here
```

Validation checks: (1) service health (`/health`), (2) API key auth (`/api/stats`).

See `references/data-sources.md` for data source details.

## Common Mistakes

| Mistake                                       | Fix                                                                                     |
| --------------------------------------------- | --------------------------------------------------------------------------------------- |
| Running without `.env` configured             | Set `LITERATURE_SEARCH_API_URL` and `LITERATURE_SEARCH_API_KEY` first                   |
| Using too broad a query without `--limit`     | Add `--limit` to avoid overwhelming results                                             |
| Forgetting `--multi-query` for complex topics | Use `--multi-query` when query spans multiple research areas                            |
| Not checking validation before searching      | Run health/auth check first to avoid silent failures                                    |
| Searching on wrong workspace                  | Specify `--workspace` explicitly when not in project root                               |
| Replacing `file_path` with a PDF path         | Keep `file_path` as the Markdown note; store PDFs in `extra_fields.full_text.file_path` |
| Downloading paywalled PDFs automatically      | Only download open-access or user-authorized files                                      |

## Pipeline Position

**Predecessors:** None (entry point)
**Successors:** hypothesis
**Required Sub-Skills:** None

## Progress Tracking

After search completes successfully:
```bash
$PYTHON .agentsociety/bin/ags.py research-pipeline update-stage literature_search completed --metadata '{"paper_count": N}'
```
