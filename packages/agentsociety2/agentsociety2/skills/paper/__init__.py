"""Paper-orchestrator harness package (M1).

Public surface for the Nature/Science-grade paper development OS.

All LLM work lives in the plugin skills under
``extension/skills/agentsociety-paper-*``; this package provides the
non-LLM logic those skills (and the orchestrator CLI) use:

- ``agentsociety2.skills.paper.paths`` - on-disk layout helpers
- ``agentsociety2.skills.paper.models`` - pydantic schemas (PaperState, ResearchPack, ...)
- ``agentsociety2.skills.paper.envelope`` - skill return contract
- ``agentsociety2.skills.paper.state`` - YAML/JSON CRUD over <workspace>/paper/state and artifacts
- ``agentsociety2.skills.paper.adapter`` - workspace -> ResearchPack ingestion + reusable helpers
- ``agentsociety2.skills.paper.compose`` - markdown -> LaTeX -> PDF
- ``agentsociety2.skills.paper.cli`` - CLI entry points (init-meta, intake, build-pack, framing,
  evidence, architecture, review, compile, run-loop, status)
"""

from __future__ import annotations

from agentsociety2.skills.paper import paths
from agentsociety2.skills.paper.envelope import (
    Envelope,
    EnvelopeStatus,
    Severity,
    SkillEnvelope,
    build_envelope,
    envelope_to_json,
    parse_envelope,
)
from agentsociety2.skills.paper.template_slots import (
    ParagraphTemplate,
    SlotType,
    TemplateSlot,
    build_template_fill_prompt,
    find_unfilled_slot_markers,
    parse_template_slots,
    render_filled_template,
)
from agentsociety2.skills.paper.models import (
    Affiliation,
    Author,
    Claim,
    ClaimLedger,
    CompileResult,
    Confidence,
    Counters,
    DispatchRecord,
    DispatchStatus,
    EvidenceBacklog,
    EvidenceCategory,
    EvidenceGap,
    FigureArgumentMap,
    FigureSpec,
    FigureStatus,
    HumanDecision,
    HumanGate,
    HumanGateSeverity,
    PaperMeta,
    PaperPhase,
    PaperState,
    Priority,
    ProvenanceEntry,
    ReleaseStatus,
    ResearchPack,
    ResearchPackAnalysis,
    ResearchPackExperiment,
    ResearchPackFigure,
    ResearchPackHypothesis,
    ResearchPackLiterature,
    ResearchPackReferencePool,
    ResolvedState,
    Review,
    ReviewRound,
    SectionLogic,
    StorylineMap,
    TargetLayer,
    Verdict,
    WordingStrength,
)


__all__ = [
    "Affiliation",
    "Author",
    "Claim",
    "ClaimLedger",
    "CompileResult",
    "Confidence",
    "Counters",
    "DispatchRecord",
    "DispatchStatus",
    "Envelope",
    "EnvelopeStatus",
    "ParagraphTemplate",
    "EvidenceBacklog",
    "EvidenceCategory",
    "EvidenceGap",
    "FigureArgumentMap",
    "FigureSpec",
    "FigureStatus",
    "HumanDecision",
    "HumanGate",
    "HumanGateSeverity",
    "PaperMeta",
    "PaperPhase",
    "PaperState",
    "Priority",
    "ProvenanceEntry",
    "ReleaseStatus",
    "ResearchPack",
    "ResearchPackAnalysis",
    "ResearchPackExperiment",
    "ResearchPackFigure",
    "ResearchPackHypothesis",
    "ResearchPackLiterature",
    "ResearchPackReferencePool",
    "ResolvedState",
    "Review",
    "ReviewRound",
    "SectionLogic",
    "SlotType",
    "Severity",
    "SkillEnvelope",
    "StorylineMap",
    "TemplateSlot",
    "TargetLayer",
    "Verdict",
    "WordingStrength",
    "build_template_fill_prompt",
    "build_envelope",
    "envelope_to_json",
    "find_unfilled_slot_markers",
    "parse_envelope",
    "parse_template_slots",
    "paths",
    "render_filled_template",
]
