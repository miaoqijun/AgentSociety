from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class AnalysisPhase(str, Enum):
    frame = "frame"
    explore = "explore"
    claims = "claims"
    refine = "refine"
    produce = "produce"


class ReleaseStatus(str, Enum):
    not_started = "not_started"
    blocked = "blocked"
    ready = "ready"


class AttestationStatus(str, Enum):
    DONE = "DONE"
    DONE_WITH_CONCERNS = "DONE_WITH_CONCERNS"
    BLOCKED = "BLOCKED"


class GateLayer(str, Enum):
    structural = "structural"
    attestation = "attestation"


class ClaimMode(str, Enum):
    confirmatory = "confirmatory"
    exploratory = "exploratory"


EdaProfile = Literal["quick-stats", "ydata", "sweetviz", "missingno", "correlation"]
Severity = Literal["info", "warning", "fatal"]


HYPOTHESIS_PHASE_ORDER: tuple[AnalysisPhase, ...] = (
    AnalysisPhase.frame,
    AnalysisPhase.explore,
    AnalysisPhase.claims,
    AnalysisPhase.refine,
    AnalysisPhase.produce,
)


class TableCheck(BaseModel):
    model_config = ConfigDict(extra="ignore")

    table: str
    min_rows: int = 1
    columns: List[str] = Field(default_factory=list)


class AnalysisPlan(BaseModel):
    model_config = ConfigDict(extra="ignore")

    research_question: str = ""
    primary_metrics: List[str] = Field(default_factory=list)
    target_tables: List[str] = Field(default_factory=list)
    confirmatory_claims: List[str] = Field(default_factory=list)
    exploratory_notes: str = ""
    simulation_limitations: str = ""
    eda_profile: EdaProfile = "quick-stats"
    table_checks: List[TableCheck] = Field(default_factory=list)
    synthesis_scope_hypothesis_ids: List[str] = Field(default_factory=list)


class Claim(BaseModel):
    model_config = ConfigDict(extra="ignore")

    claim_id: str
    statement: str
    mode: ClaimMode = ClaimMode.confirmatory
    evidence: str = ""
    needs_chart: bool = False
    approved: bool = False


class FigureContract(BaseModel):
    model_config = ConfigDict(extra="ignore")

    contract_id: str
    claim_id: str = ""
    core_finding: str = ""
    output_files: List[str] = Field(default_factory=list)


class ValidationIssue(BaseModel):
    model_config = ConfigDict(extra="ignore")

    code: str
    severity: Severity = "fatal"
    phase: str = ""
    message: str = ""
    fix_hint: str = ""


class ValidationResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    status: Literal["PASS", "BLOCKED"] = "BLOCKED"
    issues: List[ValidationIssue] = Field(default_factory=list)
    recommended_next_step: str = ""


class ValidationRecord(BaseModel):
    model_config = ConfigDict(extra="ignore")

    phase: str
    status: Literal["PASS", "BLOCKED"]
    at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class PhaseAttestation(BaseModel):
    """LLM-filled stage completion record (judgment layer, schema-validated only)."""

    model_config = ConfigDict(extra="ignore")

    phase: str
    status: AttestationStatus = AttestationStatus.DONE
    key_findings: List[str] = Field(default_factory=list)
    artifacts_read: List[str] = Field(default_factory=list)
    artifacts_written: List[str] = Field(default_factory=list)
    blocking_reason: Optional[str] = None
    recommended_next_step: Optional[str] = None
    rubric: Dict[str, Any] = Field(default_factory=dict)
    completed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class PhaseCheckpoint(BaseModel):
    """Per-phase gate telemetry (structural + attestation)."""

    model_config = ConfigDict(extra="ignore")

    phase: str
    structural_pass: bool = False
    attestation_pass: bool = False
    attestation_required: bool = True
    gate_pass: bool = False
    structural_issues: List[str] = Field(default_factory=list)
    completed_at: Optional[datetime] = None


class GateReport(BaseModel):
    model_config = ConfigDict(extra="ignore")

    phase: str
    status: Literal["PASS", "BLOCKED"] = "BLOCKED"
    structural_pass: bool = False
    attestation_pass: bool = False
    structural_issues: List[ValidationIssue] = Field(default_factory=list)
    attestation_issues: List[ValidationIssue] = Field(default_factory=list)
    issues: List[ValidationIssue] = Field(default_factory=list)
    recommended_next_step: str = ""
    rubric_keys: List[str] = Field(default_factory=list)
    checkpoint: Optional[PhaseCheckpoint] = None


class HypothesisAnalysisState(BaseModel):
    model_config = ConfigDict(extra="ignore")

    hypothesis_id: str = ""
    experiment_id: str = ""
    db_path: str = ""
    current_phase: AnalysisPhase = AnalysisPhase.frame
    hypothesis_release: ReleaseStatus = ReleaseStatus.not_started
    chart_count: int = 0
    max_charts: int = Field(
        default=0,
        description="0 = no chart cap; set N>0 only when user requests a hard budget",
    )
    figure_contracts: List[FigureContract] = Field(default_factory=list)
    phase_attestations: Dict[str, PhaseAttestation] = Field(default_factory=dict)
    phase_checkpoints: Dict[str, PhaseCheckpoint] = Field(default_factory=dict)
    phase_artifacts: Dict[str, List[str]] = Field(default_factory=dict)
    validation_history: List[ValidationRecord] = Field(default_factory=list)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class SynthesisAnalysisState(BaseModel):
    model_config = ConfigDict(extra="ignore")

    current_phase: Literal["synthesis"] = "synthesis"
    synthesis_scope_hypothesis_ids: List[str] = Field(default_factory=list)
    synthesis_question: str = ""
    workspace_release: ReleaseStatus = ReleaseStatus.not_started
    phase_attestation: Optional[PhaseAttestation] = None
    validation_history: List[ValidationRecord] = Field(default_factory=list)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ClaimsDocument(BaseModel):
    model_config = ConfigDict(extra="ignore")

    hypothesis_id: str = ""
    claims: List[Claim] = Field(default_factory=list)
