"""Typed paragraph-template slots for degraded paper generation.

This module provides a lightweight fallback representation for sections
or paragraphs that are too brittle for free-form drafting in one shot.
Writers can first emit a paragraph skeleton with typed placeholders, then
fill those placeholders with evidence-bound content before the markdown is
handed to the compose pipeline.

Slot markers intentionally use double brackets so they do not collide with
paper-skill sentinels such as ``[CITE:key]`` or ``[FIG:id]``:

    [[CLAIM_SLOT:s1]]
    [[METRIC_SLOT:s2]]
"""

from __future__ import annotations

import re
from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class SlotType(str, Enum):
    """Supported degraded-generation slot categories."""

    CLAIM = "CLAIM_SLOT"
    METRIC = "METRIC_SLOT"
    FIGURE = "FIGURE_SLOT"
    CITATION = "CITATION_SLOT"
    EVIDENCE = "EVIDENCE_SLOT"
    TRANSITION = "TRANSITION_SLOT"


class TemplateSlot(BaseModel):
    """One typed placeholder inside a degraded paragraph skeleton."""

    slot_type: SlotType
    slot_id: str
    evidence_id: str = ""
    constraints: str = ""
    filled_content: str = ""

    @property
    def marker(self) -> str:
        return f"[[{self.slot_type.value}:{self.slot_id}]]"


class ParagraphTemplate(BaseModel):
    """A paragraph skeleton plus its declared fillable slots."""

    skeleton: str = ""
    slots: List[TemplateSlot] = Field(default_factory=list)

    @property
    def is_fully_filled(self) -> bool:
        return all(slot.filled_content for slot in self.slots)

    @property
    def unfilled_slot_ids(self) -> List[str]:
        return [slot.slot_id for slot in self.slots if not slot.filled_content]


_SLOT_PATTERN = re.compile(
    r"\[\[("
    + "|".join(re.escape(slot_type.value) for slot_type in SlotType)
    + r"):([a-zA-Z0-9_]+)\]\]"
)


def parse_template_slots(skeleton: str) -> List[TemplateSlot]:
    """Extract typed slots from a paragraph skeleton."""

    slots: List[TemplateSlot] = []
    seen: set[str] = set()
    for match in _SLOT_PATTERN.finditer(skeleton):
        slot_type_str, slot_id = match.group(1), match.group(2)
        if slot_id in seen:
            continue
        seen.add(slot_id)
        slots.append(
            TemplateSlot(
                slot_type=SlotType(slot_type_str),
                slot_id=slot_id,
            )
        )
    return slots


def render_filled_template(template: ParagraphTemplate) -> str:
    """Render a paragraph template with all currently filled slots substituted."""

    rendered = template.skeleton
    for slot in template.slots:
        if slot.filled_content:
            rendered = rendered.replace(slot.marker, slot.filled_content)
    return rendered


def find_unfilled_slot_markers(text: str) -> List[str]:
    """Return all degraded-generation slot markers still present in text."""

    return [match.group(0) for match in _SLOT_PATTERN.finditer(text or "")]


def build_template_fill_prompt(
    template: ParagraphTemplate,
    *,
    evidence_snippets: Optional[Dict[str, str]] = None,
    valid_citation_keys: Optional[List[str]] = None,
) -> str:
    """Compile a fill-only prompt for a degraded paragraph skeleton."""

    evidence_snippets = evidence_snippets or {}
    valid_citation_keys = valid_citation_keys or []

    parts: List[str] = [
        "## Task",
        "Fill every degraded-generation slot in the paragraph skeleton.",
        "",
        "### Skeleton",
        "```text",
        template.skeleton,
        "```",
        "",
        "### Slots",
    ]

    for slot in template.slots:
        if slot.filled_content:
            continue
        parts.append(
            f"- {slot.marker}"
            f"\n  Type: {slot.slot_type.value}"
            f"\n  Evidence: {evidence_snippets.get(slot.evidence_id, '—')}"
            f"\n  Constraints: {slot.constraints or 'none'}"
        )

    if valid_citation_keys:
        parts.extend(
            [
                "",
                "### Valid Citation Keys",
                ", ".join(valid_citation_keys),
            ]
        )

    parts.extend(
        [
            "",
            "### Output Requirements",
            "- Return the complete paragraph with all slot markers replaced.",
            "- Keep existing [CITE:key] and [FIG:id] sentinels valid.",
            "- Do not leave any [[...]] slot marker in the final output.",
        ]
    )
    return "\n".join(parts)


__all__ = [
    "ParagraphTemplate",
    "SlotType",
    "TemplateSlot",
    "build_template_fill_prompt",
    "find_unfilled_slot_markers",
    "parse_template_slots",
    "render_filled_template",
]
