"""Paper-orchestrator harness package (M1).

Public surface for the Nature/Science-grade paper development OS.

All LLM work lives in the plugin skills under
``extension/skills/agentsociety-paper-*``; this package provides the
non-LLM logic those skills (and the orchestrator CLI) use:

- :mod:`paths` - on-disk layout helpers
- :mod:`models` - pydantic schemas (PaperState, ResearchPack, ...)
- :mod:`envelope` - skill return contract
- :mod:`state` - YAML/JSON CRUD over <workspace>/paper/state and artifacts
- :mod:`adapter` - workspace -> ResearchPack ingestion + reusable helpers
- :mod:`compose` - markdown -> LaTeX -> PDF
- :mod:`cli` - CLI entry points (init-meta, intake, build-pack, framing,
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
    "paths",
    "Envelope",
    "EnvelopeStatus",
    "Severity",
    "SkillEnvelope",
    "build_envelope",
    "envelope_to_json",
    "parse_envelope",
    "Affiliation",
    "Author",
    "Claim",
    "ClaimLedger",
    "CompileResult",
    "Confidence",
    "Counters",
    "DispatchRecord",
    "DispatchStatus",
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
    "ResolvedState",
    "Review",
    "ReviewRound",
    "SectionLogic",
    "StorylineMap",
    "TargetLayer",
    "Verdict",
    "WordingStrength",
]
