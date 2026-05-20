from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

from agentsociety2.skills.analysis.harness.json_io import load_model_from_file

from agentsociety2.skills.analysis.harness.models import (
    AnalysisPlan,
    ClaimsDocument,
    HypothesisAnalysisState,
    SynthesisAnalysisState,
)
from agentsociety2.skills.analysis.harness.paths import (
    hypothesis_analysis_dir,
    hypothesis_claims_path,
    hypothesis_plan_path,
    hypothesis_state_path,
    synthesis_analysis_dir,
    synthesis_state_path,
)


def _load_yaml(path: Path, model: type) -> Any:
    if not path.exists():
        return model()
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return model.model_validate(raw)


def _save_yaml(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = obj.model_dump(mode="json")
    path.write_text(
        yaml.safe_dump(payload, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )


def load_hypothesis_state(
    workspace: Path, hypothesis_id: str
) -> HypothesisAnalysisState:
    state = _load_yaml(
        hypothesis_state_path(workspace, hypothesis_id), HypothesisAnalysisState
    )
    if not state.hypothesis_id:
        state.hypothesis_id = hypothesis_id
    return state


def save_hypothesis_state(
    workspace: Path,
    hypothesis_id: str,
    state: HypothesisAnalysisState,
) -> None:
    state.updated_at = datetime.now(UTC)
    _save_yaml(hypothesis_state_path(workspace, hypothesis_id), state)


def load_plan(workspace: Path, hypothesis_id: str) -> AnalysisPlan:
    return _load_yaml(hypothesis_plan_path(workspace, hypothesis_id), AnalysisPlan)


def save_plan(workspace: Path, hypothesis_id: str, plan: AnalysisPlan) -> None:
    _save_yaml(hypothesis_plan_path(workspace, hypothesis_id), plan)


def load_claims(workspace: Path, hypothesis_id: str) -> ClaimsDocument:
    path = hypothesis_claims_path(workspace, hypothesis_id)
    if not path.exists():
        return ClaimsDocument(hypothesis_id=hypothesis_id, claims=[])
    doc = load_model_from_file(path, ClaimsDocument)
    if not doc.hypothesis_id:
        doc.hypothesis_id = hypothesis_id
    return doc


def save_claims(workspace: Path, hypothesis_id: str, doc: ClaimsDocument) -> None:
    import json

    path = hypothesis_claims_path(workspace, hypothesis_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    doc.hypothesis_id = hypothesis_id
    path.write_text(
        json.dumps(doc.model_dump(mode="json"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def parse_payload_dict(payload: str) -> Dict[str, Any]:
    from agentsociety2.skills.analysis.harness.json_io import load_dict_payload

    return load_dict_payload(payload)


def load_synthesis_state(workspace: Path) -> SynthesisAnalysisState:
    return _load_yaml(synthesis_state_path(workspace), SynthesisAnalysisState)


def save_synthesis_state(workspace: Path, state: SynthesisAnalysisState) -> None:
    state.updated_at = datetime.now(UTC)
    _save_yaml(synthesis_state_path(workspace), state)


def merge_plan_payload(plan: AnalysisPlan, payload: Dict[str, Any]) -> AnalysisPlan:
    merged = plan.model_dump()
    merged.update({k: v for k, v in payload.items() if v is not None})
    return AnalysisPlan.model_validate(merged)
