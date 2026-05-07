# Literature Search Data Sources

The service searches **all sources by default** when `sources` is not specified. Local knowledge base results are always displayed first.

| Source | Description | Content Type |
|--------|-------------|--------------|
| local | RAGFlow local knowledge base | Imported full-text documents |
| arxiv | arXiv preprint platform | Physics, Math, CS, etc. |
| crossref | DOI metadata database | Journal paper metadata |
| openalex | OpenAlex academic graph | 250M+ academic papers |

## API Response Fields

Each article in the response contains:

| Field | Type | Description |
|-------|------|-------------|
| title | string | Article title |
| authors | list | Author list |
| abstract | string | Article abstract |
| year | integer | Publication year |
| journal | string | Journal name |
| doi | string | DOI identifier |
| url | string | Original link |
| score | float | Relevance score |
| source | string | Data source (local/arxiv/crossref/openalex) |
