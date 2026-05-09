# Full-Text Retrieval Guidance

The literature search command saves reliable metadata and local Markdown notes. Full-text PDF retrieval is a separate follow-up task because access differs by publisher, repository, license, and user credentials.

## When to Retrieve PDFs

Retrieve original PDFs only when one of these is true:

- The user explicitly asks for original papers or full texts.
- A downstream task needs exact wording, tables, figures, appendices, or methods details not present in the abstract.
- The search result is from an open repository such as arXiv and the PDF URL is straightforward.

Do not retrieve PDFs when the Markdown note and abstract are sufficient for screening or early ideation.

## Candidate Sources

Use the helper first:

```bash
$PYTHON_PATH .agentsociety/bin/ags.py literature-full-text candidates
$PYTHON_PATH .agentsociety/bin/ags.py literature-full-text candidates --entry 1
```

The helper inspects each `papers/literature_index.json` entry in this order:

1. `extra_fields.pdf_url`
2. `extra_fields.full_text_url`
3. `extra_fields.download_url`
4. `extra_fields.open_access`
5. `extra_fields.best_oa_location`
6. `extra_fields.primary_location`
7. `extra_fields.url`
8. `doi`

For arXiv:

- `https://arxiv.org/abs/2401.01234` -> `https://arxiv.org/pdf/2401.01234.pdf`
- `10.48550/arXiv.2401.01234` -> `https://arxiv.org/pdf/2401.01234.pdf`

For DOI:

- Treat DOI as a discovery link, not as a guaranteed PDF link.
- Follow redirects only when allowed and save the file only if the final response is a PDF.

## Storage Convention

Save original PDFs here:

```text
papers/full_texts/
```

Use a stable, filesystem-safe filename, ideally based on the Markdown note stem:

```text
papers/Article_Title_2026-05-09T12-00-00.md
papers/full_texts/Article_Title_2026-05-09T12-00-00.pdf
```

## Index Update

Prefer the helper so paths and status fields stay consistent:

```bash
$PYTHON_PATH .agentsociety/bin/ags.py literature-full-text download --entry 1
$PYTHON_PATH .agentsociety/bin/ags.py literature-full-text download --entry 1 --url https://arxiv.org/pdf/2401.01234.pdf
$PYTHON_PATH .agentsociety/bin/ags.py literature-full-text register --entry 1 --file /path/to/paper.pdf
$PYTHON_PATH .agentsociety/bin/ags.py literature-full-text mark --entry 1 --status no_candidate --reason "No open PDF URL was available."
```

After saving a PDF, the same entry in `papers/literature_index.json` should look like this.

Do:

```json
{
  "file_path": "papers/Article_Title_2026-05-09T12-00-00.md",
  "extra_fields": {
    "full_text": {
      "status": "downloaded",
      "file_path": "papers/full_texts/Article_Title_2026-05-09T12-00-00.pdf",
      "source_url": "https://arxiv.org/pdf/2401.01234.pdf"
    }
  }
}
```

Do not replace `file_path` with the PDF path. `file_path` is the stable Markdown note used for `@papers/...` references.

If no open PDF is available:

```json
{
  "extra_fields": {
    "full_text": {
      "status": "no_candidate",
      "reason": "No open PDF URL was available in the returned metadata."
    }
  }
}
```

If a download attempt fails:

```json
{
  "extra_fields": {
    "full_text": {
      "status": "failed",
      "reason": "The candidate URL returned HTML instead of PDF.",
      "source_url": "https://doi.org/10.xxxx/xxxx"
    }
  }
}
```

## Safety and Access Rules

- Do not bypass paywalls, login walls, CAPTCHAs, or publisher access controls.
- Do not save HTML landing pages with a `.pdf` extension.
- Prefer open repositories and explicit PDF URLs.
- If the user has institutional access or a local file, ask them to provide/upload the file instead of trying to circumvent access controls.

## Enriching Notes via Web Research

When a PDF is not available (paywall, no open access, connection failure), the Markdown note can still be enriched with substantive content gathered from the web.

### Why Enrich

The initial Markdown note only contains metadata (title, abstract, DOI). For papers whose PDFs cannot be downloaded, enriching the note ensures that downstream tasks (hypothesis generation, analysis, paper writing) still have useful information about the article's contributions, methods, and context.

### How to Enrich

1. **Identify candidates** — run `literature-full-text enrich --dry-run` to see entries with failed/no_candidate status that have not yet been enriched.

2. **Search the web** — for each candidate entry, use web search with queries like:
   - `"<article title>" summary` or `"<article title>" review`
   - `"<first author>" <article title>` 
   - `"<article title>" site:arxiv.org` (check for preprint versions)
   - `DOI <doi>` (check for open-access versions)

3. **Look for these sources** (in order of reliability):
   - Open-access preprint on arXiv, bioRxiv, SSRN, etc. → if found, download the PDF instead
   - Author's institutional page or Google Scholar profile
   - Blog posts or articles discussing the paper
   - Wikipedia or encyclopedia entries citing the paper
   - Conference presentation slides or videos

4. **Append to the Markdown note** — add a `## Web Research Notes` section to the file at `entry.file_path`:

```markdown
## Web Research Notes

*Enriched via web search on YYYY-MM-DD. Original PDF was not available: <reason>.*

### Key Findings
- (Main claims and results from secondary sources)

### Methodology Highlights
- (Experimental or analytical approach)

### Context and Impact
- (Relationship to the field, citations, follow-up work)

### Sources
- [Source 1 title](url)
- [Source 2 title](url)
```

5. **Mark as enriched** — after appending notes:
   ```bash
   $PYTHON_PATH .agentsociety/bin/ags.py literature-full-text enrich --entry N
   ```

### Rules

- Only include information actually found through web search. Do not fabricate or guess.
- Always cite web sources with URLs.
- If a preprint PDF is found during web search, download it instead of (or in addition to) enriching the note.
- If web search yields nothing useful, do not append an empty section.
