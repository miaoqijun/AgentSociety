"""Pydantic models for the paper-orchestrator harness (M1).

These data classes back the YAML/JSON files persisted under
``<workspace>/paper/`` (state, artifacts, reviews, runs).  All non-LLM logic
(state CRUD, adapter, compose) round-trips through these models so the
on-disk shape stays consistent with subagent prompts and tests.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Literal, Optional

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, model_validator


# ---------------------------------------------------------------------------
# Envelope (skill return contract)
# ---------------------------------------------------------------------------


EnvelopeStatus = Literal[
    "DONE",
    "DONE_WITH_CONCERNS",
    "NEEDS_CONTEXT",
    "BLOCKED",
    "PIVOT_RECOMMENDED",
    "HUMAN_GATE_REQUIRED",
]
"""Producer / reviewer subagent return states (per harness design §Producer Return States)."""

Severity = Literal["info", "warning", "fatal"]


class Envelope(BaseModel):
    """Common return shape for every paper-skill subagent dispatch.

    Fields mirror §"Unified Skill Return Contract" of the harness design doc.
    """

    model_config = ConfigDict(extra="ignore")

    status: EnvelopeStatus
    artifacts_read: List[str] = Field(default_factory=list)
    artifacts_written: List[str] = Field(default_factory=list)
    key_findings: List[str] = Field(default_factory=list)
    blocking_reason: Optional[str] = None
    recommended_next_step: Optional[str] = None
    severity: Optional[Severity] = None


# ---------------------------------------------------------------------------
# CompileResult (returned by compose.compiler)
# ---------------------------------------------------------------------------


class CompileResult(BaseModel):
    """Outcome of an ``latexmk`` invocation."""

    pdf_path: Optional[str] = None
    log_path: Optional[str] = None
    success: bool = False
    errors: List[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# PaperMeta (un-namespaced user identity at <ws>/paper/paper_meta.yaml)
# ---------------------------------------------------------------------------


class Affiliation(BaseModel):
    """Author affiliation entry."""

    id: int = Field(..., description="Numeric ID referenced from Author.affils")
    name: str


class Author(BaseModel):
    name: str
    affils: List[int] = Field(default_factory=list, description="Affiliation IDs")
    email: Optional[str] = None
    corresponding: bool = False


class PaperMeta(BaseModel):
    """Identity block written to ``<workspace>/paper/paper_meta.yaml``."""

    model_config = ConfigDict(extra="ignore")

    title: str
    authors: List[Author] = Field(default_factory=list)
    affils: List[Affiliation] = Field(default_factory=list)
    data_availability_url: Optional[str] = None
    code_availability_url: Optional[str] = None
    target_journal: Optional[str] = None


# ---------------------------------------------------------------------------
# Storyline map (paper-framing output)
# ---------------------------------------------------------------------------


class SectionLogic(BaseModel):
    section: str = Field(..., description="abstract / main / results / discussion / ...")
    purpose: str = ""
    key_points: List[str] = Field(default_factory=list)


class StorylineMap(BaseModel):
    """Story constitution; persists as storyline_map.{md,json}."""

    model_config = ConfigDict(extra="ignore")

    main_question: str = ""
    core_tension: str = ""
    why_now: str = ""
    contribution_statement: str = ""
    current_angle: str = ""
    rejected_angles: List[str] = Field(default_factory=list)
    kill_criteria: List[str] = Field(default_factory=list)
    section_logic: List[SectionLogic] = Field(default_factory=list)
    angle_version: int = 0


# ---------------------------------------------------------------------------
# Claim ledger
# ---------------------------------------------------------------------------


WordingStrength = Literal["weak", "moderate", "strong"]


class Claim(BaseModel):
    """Single row in the claim ledger."""

    model_config = ConfigDict(extra="ignore")

    claim_id: str = Field(..., description="Stable ID, e.g. 'C1' or 'C2.a'")
    claim_text: str
    claim_type: str = Field(default="factual", description="factual / causal / comparative / predictive / ...")
    evidence_support: List[str] = Field(default_factory=list, description="Pointers: figure IDs, [CITE:key], analysis IDs")
    linked_figures: List[str] = Field(default_factory=list)
    unsupported_gaps: List[str] = Field(default_factory=list)
    allowed_wording_strength: WordingStrength = "moderate"
    reviewer_objections: List[str] = Field(default_factory=list)


class ClaimLedger(BaseModel):
    """Canonical register of claims; persists as claim_ledger.{md,json}."""

    model_config = ConfigDict(extra="ignore")

    claims: List[Claim] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Evidence backlog
# ---------------------------------------------------------------------------


EvidenceCategory = Literal[
    "analysis",
    "control",
    "robustness",
    "figure",
    "experiment",
    "literature",
    "alternative",
]
Priority = Literal["high", "medium", "low"]
EvidenceGapType = Literal[
    "missing_analysis",
    "missing_control",
    "missing_robustness",
    "missing_figure",
    "missing_experiment",
    "missing_alternative",
    "missing_literature",
]
EvidenceTool = Literal[
    "agentsociety-analysis",
    "agentsociety-literature-search",
    "human",
]


_GAP_TYPE_TO_CATEGORY: dict[str, EvidenceCategory] = {
    "missing_analysis": "analysis",
    "missing_control": "control",
    "missing_robustness": "robustness",
    "missing_figure": "figure",
    "missing_experiment": "experiment",
    "missing_alternative": "alternative",
    "missing_literature": "literature",
}


def _normalize_gap_token(raw: Optional[str]) -> str:
    return (raw or "").strip().lower().replace("-", "_")


class EvidenceGap(BaseModel):
    """Single backlog item (missing analysis / control / figure / ...)."""

    model_config = ConfigDict(extra="ignore")

    gap_id: str
    description: str
    category: EvidenceCategory = "analysis"
    priority: Priority = "medium"
    auto_executable: bool = False
    human_gated: bool = False
    gap_type: Optional[EvidenceGapType] = None
    tool: Optional[EvidenceTool] = None
    claim_id: Optional[str] = None
    related_claim_ids: List[str] = Field(default_factory=list)
    suggested_approach: Optional[str] = None
    evidence_impact: Optional[str] = None
    notes: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def _coerce_gap_shape(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data

        payload = dict(data)
        gap_type = _normalize_gap_token(payload.get("gap_type"))
        category = _normalize_gap_token(payload.get("category"))
        tool = (payload.get("tool") or "").strip().lower()

        if not category:
            inferred_category = _GAP_TYPE_TO_CATEGORY.get(gap_type)
            if inferred_category is not None:
                payload["category"] = inferred_category
            elif tool == "agentsociety-literature-search":
                payload["category"] = "literature"
            elif tool == "agentsociety-analysis":
                payload["category"] = "analysis"

        if payload.get("claim_id") and not payload.get("related_claim_ids"):
            payload["related_claim_ids"] = [payload["claim_id"]]

        if tool == "human" and "human_gated" not in payload:
            payload["human_gated"] = True

        return payload


class EvidenceBacklog(BaseModel):
    """Backlog persisted as evidence_backlog.{md,json}."""

    model_config = ConfigDict(extra="ignore")

    items: List[EvidenceGap] = Field(
        default_factory=list,
        validation_alias=AliasChoices("items", "gaps"),
    )
    summary: Optional[Dict[str, Any]] = None


# ---------------------------------------------------------------------------
# Figure-argument map
# ---------------------------------------------------------------------------


FigureStatus = Literal["planned", "drafted", "rendered", "final"]


class FigureSpec(BaseModel):
    """One row in figure_argument_map: figure -> claim/section roles."""

    model_config = ConfigDict(extra="ignore")

    figure_id: str
    title: str = ""
    question_answered: str = ""
    claim_supported: List[str] = Field(default_factory=list)
    alternative_explanation_addressed: List[str] = Field(default_factory=list)
    target_section: str = ""
    status: FigureStatus = "planned"
    file_path: Optional[str] = None
    panels: List[str] = Field(default_factory=list, description="Per-panel description lines")


class FigureArgumentMap(BaseModel):
    """Persists as figure_argument_map.{md,json}."""

    model_config = ConfigDict(extra="ignore")

    figures: List[FigureSpec] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Review round
# ---------------------------------------------------------------------------


Verdict = Literal[
    "accept",
    "revise_local",
    "revise_structural",
    "pivot_conceptual",
    "pivot_major",
    "fatal",
]
TargetLayer = Literal[
    "wording",
    "paragraph",
    "section",
    "figure_plan",
    "evidence",
    "framing",
]
ResolvedState = Literal["open", "resolved", "deferred"]


class Review(BaseModel):
    """Single reviewer entry inside a review round."""

    model_config = ConfigDict(extra="ignore")

    reviewer_profile: str = Field(..., description="e.g. angle-critic / evidence-skeptic / precision-editor")
    verdict: Verdict
    severity: Severity = "warning"
    target_artifact: str = ""
    target_layer: TargetLayer = "wording"
    issue_type: str = ""
    reroute_target: Optional[str] = None
    human_gate_flag: bool = False
    resolved_state: ResolvedState = "open"
    resolution_note: Optional[str] = None
    raw_text: Optional[str] = Field(default=None, description="Free-form reviewer text")


class ReviewRound(BaseModel):
    """Persisted as reviews/review_round_NNN.yaml (append-only)."""

    model_config = ConfigDict(extra="ignore")

    round_num: int
    started_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    reviews: List[Review] = Field(default_factory=list)
    unresolved_fatal: List[str] = Field(default_factory=list, description="Review IDs / descriptions of unresolved fatal items")


# ---------------------------------------------------------------------------
# Human gate queue
# ---------------------------------------------------------------------------


HumanGateSeverity = Literal["minor", "moderate", "major"]
HumanDecision = Literal["accept", "reject", "modify"]


class HumanGate(BaseModel):
    """One entry in human_gates.yaml."""

    model_config = ConfigDict(extra="ignore")

    gate_id: str
    triggering_issue: str
    proposed_pivot: str = ""
    severity: HumanGateSeverity = "moderate"
    rationale: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)
    user_decision: Optional[HumanDecision] = None
    accepted_version: Optional[str] = None
    decided_at: Optional[datetime] = None
    note: Optional[str] = None


# ---------------------------------------------------------------------------
# Dispatch records (runs/<TS>/dispatch_NNN.json)
# ---------------------------------------------------------------------------


DispatchStatus = Literal["pending", "running", "completed", "failed"]


class DispatchRecord(BaseModel):
    """One subagent dispatch + its returned envelope."""

    model_config = ConfigDict(extra="ignore")

    dispatch_num: int
    target_skill: str
    target_subagent: Optional[str] = None
    dispatched_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    status: DispatchStatus = "pending"
    envelope: Optional[Envelope] = None
    notes: Optional[str] = None


# ---------------------------------------------------------------------------
# Paper-state machine (state/paper_state.yaml)
# ---------------------------------------------------------------------------


class PaperPhase(str, Enum):
    intake = "intake"
    framing = "framing"
    evidence_audit = "evidence-audit"
    expansion_plan = "expansion-plan"
    manuscript_build = "manuscript-build"
    skeptical_review = "skeptical-review"
    revision_router = "revision-router"
    release_gate = "release-gate"


class ReleaseStatus(str, Enum):
    not_started = "not-started"
    draft = "draft"
    in_review = "in-review"
    ready = "ready"
    released = "released"
    blocked = "blocked"


class Counters(BaseModel):
    """Per-round dispatch caps (figure regen / citation aug)."""

    figure_regenerations: int = 0
    citation_augmentations: int = 0


DraftGenerationMode = Literal["freeform", "template_slots"]


class RoundConstraint(BaseModel):
    """Machine-readable instruction carried into the next paper round."""

    model_config = ConfigDict(extra="ignore")

    constraint_id: str
    applies_to_phase: PaperPhase = PaperPhase.manuscript_build
    target_artifact: str = "draft_section"
    target_layer: TargetLayer = "paragraph"
    generation_mode: DraftGenerationMode = "freeform"
    issue_type: str = ""
    rationale: str = ""
    source_round: Optional[int] = None
    source_reviewer: Optional[str] = None
    block_id: Optional[str] = None
    target_paths: List[str] = Field(default_factory=list)
    required_slot_types: List[str] = Field(default_factory=list)
    required_anchors: List[str] = Field(default_factory=list)


class PaperState(BaseModel):
    """Kernel state persisted as ``state/paper_state.yaml``."""

    model_config = ConfigDict(extra="ignore")

    current_phase: PaperPhase = PaperPhase.intake
    round: int = 0
    angle_version: int = 0
    outline_version: int = 0
    draft_version: int = 0
    pending_human_gate: Optional[str] = None
    last_blocker: Optional[str] = None
    release_status: ReleaseStatus = ReleaseStatus.not_started
    counters: Counters = Field(default_factory=Counters)
    round_constraints: List[RoundConstraint] = Field(default_factory=list)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# ---------------------------------------------------------------------------
# Research pack (paper-adapter output)
# ---------------------------------------------------------------------------


Confidence = Literal["high", "medium", "low"]


class ResearchPackHypothesis(BaseModel):
    hypothesis_id: str
    text: str = ""
    experiments: List[str] = Field(default_factory=list, description="experiment_id refs")
    confidence: Confidence = "medium"


class ResearchPackExperiment(BaseModel):
    experiment_id: str
    hypothesis_id: str
    design: str = ""
    confidence: Confidence = "medium"


class ResearchPackAnalysis(BaseModel):
    analysis_id: str
    hypothesis_id: str
    summary: str = ""
    raw_json: Optional[Dict[str, Any]] = None


class ResearchPackFigure(BaseModel):
    figure_id: str
    file_path: str
    source: str = ""
    caption_hint: str = ""


class ResearchPackLiterature(BaseModel):
    cite_key: str
    title: str
    authors: str = ""
    year: str = ""
    doi: str = ""
    journal: str = ""
    bibtex: str = ""


class ResearchPackReferencePool(BaseModel):
    """Incremental literature pool for paper-stage citation growth."""

    workspace_refs: List[ResearchPackLiterature] = Field(default_factory=list)
    supplemental_refs: List[ResearchPackLiterature] = Field(default_factory=list)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ProvenanceEntry(BaseModel):
    artifact_id: str = Field(..., description="e.g. 'hypothesis:1' or 'figure:fig:foo'")
    source_path: str
    confidence: Confidence
    notes: str = ""


class ResearchPack(BaseModel):
    """Standardized intake produced by ``agentsociety-paper-adapter``."""

    model_config = ConfigDict(extra="ignore")

    workspace_path: str
    topic: str = ""
    research_objective: str = ""
    hypotheses: List[ResearchPackHypothesis] = Field(default_factory=list)
    experiments: List[ResearchPackExperiment] = Field(default_factory=list)
    analyses: List[ResearchPackAnalysis] = Field(default_factory=list)
    figures: List[ResearchPackFigure] = Field(default_factory=list)
    literature: List[ResearchPackLiterature] = Field(default_factory=list)
    reference_pool: Optional[ResearchPackReferencePool] = None
    synthesis_report: str = ""
    draft_inputs: Dict[str, str] = Field(default_factory=dict)
    provenance: List[ProvenanceEntry] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=datetime.utcnow)


__all__ = [
    # Paper meta (identity)
    "Affiliation",
    "Author",
    "Claim",
    "ClaimLedger",
    # Compile
    "CompileResult",
    # Research pack
    "Confidence",
    "Counters",
    "DispatchRecord",
    # Dispatch record
    "DispatchStatus",
    "Envelope",
    # Envelope
    "EnvelopeStatus",
    "EvidenceBacklog",
    # Evidence backlog
    "EvidenceCategory",
    "EvidenceGap",
    "FigureArgumentMap",
    "FigureSpec",
    # Figure argument
    "FigureStatus",
    "HumanDecision",
    "HumanGate",
    # Human gate
    "HumanGateSeverity",
    "PaperMeta",
    # Paper state
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
    "RoundConstraint",
    "ResolvedState",
    "Review",
    "ReviewRound",
    # Storyline
    "SectionLogic",
    "Severity",
    "StorylineMap",
    "TargetLayer",
    "DraftGenerationMode",
    # Review
    "Verdict",
    # Claim ledger
    "WordingStrength",
]
