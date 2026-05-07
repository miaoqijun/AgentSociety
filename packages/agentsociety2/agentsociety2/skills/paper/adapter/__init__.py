"""Adapter package - workspace ingestion + reusable text/JSON helpers.

The adapter is the only paper-skill component that reads the raw
AgentSociety workspace tree (TOPIC.md, hypothesis_*/, presentation/, ...).
It produces a :class:`ResearchPack` consumed by every downstream LLM-driven
skill.

Submodules:

- :mod:`summary` - small text helpers + analysis-JSON summarization
- :mod:`bib_writer` - literature_index.json -> BibTeX
- :mod:`research_pack_builder` - workspace tree -> :class:`ResearchPack`
"""

from __future__ import annotations

from agentsociety2.skills.paper.adapter import (
    bib_writer,
    research_pack_builder,
    summary,
)

__all__ = [
    "bib_writer",
    "research_pack_builder",
    "summary",
]
