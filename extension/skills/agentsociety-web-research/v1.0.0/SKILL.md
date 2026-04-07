---
name: agentsociety-web-research
version: 1.0.0
description: Use when supplementary web sources are needed beyond academic literature, such as current events, documentation, or recent non-academic developments.
---

# Web Research

## Overview
Perform web research through the external Miro MCP service. Returns synthesized summaries from multiple web sources, complementing academic literature search with broader web context.

## When to Use
- User needs current events, recent developments, or news beyond academic scope
- Searching for documentation, examples, or non-academic sources
- `literature-search` has covered academic sources but broader web context is also needed
- Comparing approaches or gathering background for hypotheses where academic papers are insufficient

**Do NOT use when:**
- Academic literature is the primary need (use `literature-search` instead)
- The information is available in local codebase or project files

## Quick Reference
| Command | Description |
|---------|-------------|
| `$PYTHON_PATH .agentsociety/bin/ags.py web-research "query"` | Run web research with a query |
| `$PYTHON_PATH .agentsociety/bin/ags.py web-research "query" --llm MODEL` | Use a specific LLM model |
| `$PYTHON_PATH .agentsociety/bin/ags.py web-research "query" --agent NAME` | Use a specific agent configuration |

Use the Python interpreter from `.env`. See `CLAUDE.md` for setup.

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| query | string | Yes | Research query (positional argument) |
| --llm | string | No | LLM model name to use |
| --agent | string | No | Agent configuration name |

## What It Does
1. Searches the web using Miro MCP service
2. Synthesizes findings from multiple sources
3. Returns a concise summary

## Use Cases
- Research recent developments in a field
- Compare different approaches or technologies
- Find documentation or examples
- Gather background information for hypotheses

## Prerequisites
Requires Miro MCP service to be accessible.

## Common Mistakes
| Mistake | Fix |
|------|-----|
| Using this for academic literature search | Use `literature-search` for academic papers and citations |
| Not checking Miro MCP service availability first | Verify the service is running before invoking research |
| Expecting structured academic citations | This returns web summaries, not formatted bibliographic entries |

## Pipeline Position
**Predecessors:** None (supplementary skill, can run independently)
**Successors:** `hypothesis`, `analysis` (feeds supplementary context)
**Supplementary to:** `literature-search`
