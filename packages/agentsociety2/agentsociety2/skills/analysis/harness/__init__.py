"""Analysis harness: state, validators, and CLI helpers for staged experiment analysis."""

from .attestation import PHASE_RUBRIC_KEYS
from .guidance import (
    get_chart_scaffold,
    get_harness_guidance,
    get_payload_template,
    list_payload_templates,
)
from .models import (
    AnalysisPhase,
    AnalysisPlan,
    AttestationStatus,
    Claim,
    ClaimMode,
    FigureContract,
    GateReport,
    HypothesisAnalysisState,
    PhaseAttestation,
    PhaseCheckpoint,
    ReleaseStatus,
    SynthesisAnalysisState,
    TableCheck,
    ValidationIssue,
    ValidationResult,
)
from .paths import (
    hypothesis_analysis_dir,
    hypothesis_claims_path,
    hypothesis_plan_path,
    hypothesis_state_path,
    synthesis_analysis_dir,
    synthesis_state_path,
)

__all__ = [
    "PHASE_RUBRIC_KEYS",
    "get_chart_scaffold",
    "get_harness_guidance",
    "get_payload_template",
    "list_payload_templates",
    "AnalysisPhase",
    "AnalysisPlan",
    "AttestationStatus",
    "Claim",
    "ClaimMode",
    "FigureContract",
    "GateReport",
    "HypothesisAnalysisState",
    "PhaseAttestation",
    "PhaseCheckpoint",
    "ReleaseStatus",
    "SynthesisAnalysisState",
    "TableCheck",
    "ValidationIssue",
    "ValidationResult",
    "hypothesis_analysis_dir",
    "hypothesis_claims_path",
    "hypothesis_plan_path",
    "hypothesis_state_path",
    "synthesis_analysis_dir",
    "synthesis_state_path",
]
