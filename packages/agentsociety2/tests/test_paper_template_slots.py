from __future__ import annotations

from agentsociety2.skills.paper.template_slots import (
    ParagraphTemplate,
    SlotType,
    TemplateSlot,
    build_template_fill_prompt,
    find_unfilled_slot_markers,
    parse_template_slots,
    render_filled_template,
)


def test_parse_template_slots_uses_double_bracket_markers():
    skeleton = (
        "Claim [[CLAIM_SLOT:s1]] with metric [[METRIC_SLOT:s2]] and "
        "citation [[CITATION_SLOT:s3]]."
    )

    slots = parse_template_slots(skeleton)

    assert [(slot.slot_type, slot.slot_id) for slot in slots] == [
        (SlotType.CLAIM, "s1"),
        (SlotType.METRIC, "s2"),
        (SlotType.CITATION, "s3"),
    ]


def test_render_filled_template_replaces_filled_slots_only():
    template = ParagraphTemplate(
        skeleton="A [[CLAIM_SLOT:s1]] with [[METRIC_SLOT:s2]].",
        slots=[
            TemplateSlot(
                slot_type=SlotType.CLAIM,
                slot_id="s1",
                filled_content="supported mechanism",
            ),
            TemplateSlot(
                slot_type=SlotType.METRIC,
                slot_id="s2",
            ),
        ],
    )

    rendered = render_filled_template(template)

    assert rendered == "A supported mechanism with [[METRIC_SLOT:s2]]."


def test_find_unfilled_slot_markers_detects_remaining_placeholders():
    markers = find_unfilled_slot_markers(
        "Filled [CITE:Levy2021] but unresolved [[FIGURE_SLOT:s1]] and [[METRIC_SLOT:s2]]."
    )

    assert markers == ["[[FIGURE_SLOT:s1]]", "[[METRIC_SLOT:s2]]"]


def test_build_template_fill_prompt_lists_constraints_and_valid_keys():
    template = ParagraphTemplate(
        skeleton="[[CLAIM_SLOT:s1]] with [[CITATION_SLOT:s2]].",
        slots=[
            TemplateSlot(
                slot_type=SlotType.CLAIM,
                slot_id="s1",
                evidence_id="claim:C1",
                constraints="State the main result in one sentence.",
            ),
            TemplateSlot(
                slot_type=SlotType.CITATION,
                slot_id="s2",
                evidence_id="lit:Levy2021",
                constraints="Resolve to one valid cite sentinel.",
            ),
        ],
    )

    prompt = build_template_fill_prompt(
        template,
        evidence_snippets={
            "claim:C1": "Counter-attitudinal exposure reduces polarization.",
            "lit:Levy2021": "Primary field experiment reference.",
        },
        valid_citation_keys=["Levy2021"],
    )

    assert "[[CLAIM_SLOT:s1]]" in prompt
    assert "Counter-attitudinal exposure reduces polarization." in prompt
    assert "Levy2021" in prompt
