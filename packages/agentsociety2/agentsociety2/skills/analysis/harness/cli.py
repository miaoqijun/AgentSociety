from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from agentsociety2.skills.analysis.harness import state as harness_state
from agentsociety2.skills.analysis.harness.attestation import PHASE_RUBRIC_KEYS
from agentsociety2.skills.analysis.harness.gates import (
    evaluate_hypothesis_gate,
    evaluate_synthesis_gate,
    gate_status_hypothesis,
    prior_phase_gate_issues,
)
from agentsociety2.skills.analysis.harness.models import (
    HYPOTHESIS_PHASE_ORDER,
    AnalysisPhase,
    Claim,
    FigureContract,
    HypothesisAnalysisState,
    PhaseAttestation,
    ReleaseStatus,
    SynthesisAnalysisState,
    ValidationRecord,
)
from agentsociety2.skills.analysis.harness.layout import (
    migrate_legacy_hypothesis_harness,
)
from agentsociety2.skills.analysis.harness.paths import (
    hypothesis_harness_dir,
    hypothesis_plan_path,
    synthesis_harness_dir,
)
from agentsociety2.skills.analysis.harness.review import (
    report_content_fingerprint,
    save_report_review,
    save_synthesis_review,
    synthesis_content_fingerprint,
    validate_report_review,
    validate_synthesis_review,
)
from agentsociety2.skills.analysis.harness.schemas import (
    ReportQualityReview,
    SynthesisQualityReview,
)
from agentsociety2.skills.analysis.harness.validators import (
    validate_chart_file,
    validate_chart_script,
    validate_claims,
    validate_explore,
    validate_plan,
    validate_refine,
    validate_release,
    validate_report_quality,
    validate_synthesis,
)
from agentsociety2.skills.analysis.harness.validators._helpers import (
    blocked,
    merge_results,
)
from agentsociety2.skills.analysis.models import DIR_DATA, DIR_PRESENTATION
from agentsociety2.skills.analysis.utils import (
    experiment_paths,
    presentation_paths,
    synthesis_paths,
)


def _record_validation(
    state: HypothesisAnalysisState | SynthesisAnalysisState, phase: str, result
) -> None:
    state.validation_history.append(
        ValidationRecord(phase=phase, status=result.status, at=datetime.now(UTC))
    )


def _gate_payload(gate) -> Dict[str, Any]:
    return {
        "gate": gate.model_dump(mode="json"),
        "status": gate.status,
        "structural_pass": gate.structural_pass,
        "attestation_pass": gate.attestation_pass,
        "issues": [i.model_dump(mode="json") for i in gate.issues],
        "recommended_next_step": gate.recommended_next_step,
        "rubric_keys": gate.rubric_keys,
        "llm_action": (
            "record-attestation"
            if not gate.attestation_pass
            else "advance or continue narrative work"
        ),
    }


def _apply_gate_to_state(st: HypothesisAnalysisState, gate) -> None:
    if gate.checkpoint is not None:
        st.phase_checkpoints[gate.phase] = gate.checkpoint


def cmd_intake(
    workspace: Path,
    hypothesis_id: str,
    experiment_id: str,
) -> Dict[str, Any]:
    paths = experiment_paths(workspace, hypothesis_id, experiment_id)
    pres = presentation_paths(
        workspace / DIR_PRESENTATION, hypothesis_id, experiment_id
    )
    migrated = migrate_legacy_hypothesis_harness(workspace, hypothesis_id)
    harness_dir = hypothesis_harness_dir(workspace, hypothesis_id)
    harness_dir.mkdir(parents=True, exist_ok=True)
    synthesis_harness_dir(workspace).mkdir(parents=True, exist_ok=True)
    pres.output_dir.mkdir(parents=True, exist_ok=True)
    (pres.output_dir / DIR_DATA).mkdir(parents=True, exist_ok=True)
    pres.charts_dir.mkdir(parents=True, exist_ok=True)

    st = harness_state.load_hypothesis_state(workspace, hypothesis_id)
    st.hypothesis_id = hypothesis_id
    st.experiment_id = experiment_id
    st.db_path = str(paths.db_path)
    st.current_phase = AnalysisPhase.frame
    st.hypothesis_release = ReleaseStatus.not_started
    harness_state.save_hypothesis_state(workspace, hypothesis_id, st)

    if not paths.db_path.exists():
        return {
            "state": st.model_dump(mode="json"),
            "db_path": str(paths.db_path),
            "db_ready": False,
            "warning": "sqlite.db not found; complete run-experiment first",
        }
    return {
        "state": st.model_dump(mode="json"),
        "db_path": str(paths.db_path),
        "db_ready": True,
        "presentation_dir": str(pres.output_dir),
        "harness_dir": str(harness_dir),
        "legacy_harness_migrated": migrated,
        "rubric_keys": PHASE_RUBRIC_KEYS.get("frame", []),
    }


def cmd_write_plan(
    workspace: Path, hypothesis_id: str, payload: Dict[str, Any]
) -> Dict[str, Any]:
    if isinstance(payload, str):
        payload = harness_state.parse_payload_dict(payload)
    plan = harness_state.load_plan(workspace, hypothesis_id)
    plan = harness_state.merge_plan_payload(plan, payload)
    harness_state.save_plan(workspace, hypothesis_id, plan)
    return {
        "plan": plan.model_dump(mode="json"),
        "plan_path": str(hypothesis_plan_path(workspace, hypothesis_id)),
    }


def cmd_record_attestation(
    workspace: Path,
    hypothesis_id: Optional[str],
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    if isinstance(payload, str):
        payload = harness_state.parse_payload_dict(payload)
    att = PhaseAttestation.model_validate(payload)
    phase = att.phase.strip()
    if phase == "synthesis":
        st = harness_state.load_synthesis_state(workspace)
        st.phase_attestation = att
        harness_state.save_synthesis_state(workspace, st)
        return {"attestation": att.model_dump(mode="json"), "scope": "workspace"}
    if not hypothesis_id:
        return {"error": "hypothesis-id required unless phase is synthesis"}
    st = harness_state.load_hypothesis_state(workspace, hypothesis_id)
    try:
        target_phase = AnalysisPhase(phase)
    except ValueError:
        return {"error": f"unknown hypothesis phase: {phase}"}
    prior_issues = prior_phase_gate_issues(st, target_phase)
    if prior_issues:
        return {
            "error": "prior_phase_gate_blocked",
            "status": "BLOCKED",
            "issues": [i.model_dump(mode="json") for i in prior_issues],
            "recommended_next_step": prior_issues[0].fix_hint,
        }
    st.phase_attestations[phase] = att
    harness_state.save_hypothesis_state(workspace, hypothesis_id, st)
    return {"attestation": att.model_dump(mode="json"), "hypothesis_id": hypothesis_id}


def cmd_record_phase_artifacts(
    workspace: Path,
    hypothesis_id: str,
    phase: str,
    artifacts: List[str],
) -> Dict[str, Any]:
    st = harness_state.load_hypothesis_state(workspace, hypothesis_id)
    st.phase_artifacts[phase] = list(artifacts)
    harness_state.save_hypothesis_state(workspace, hypothesis_id, st)
    return {"phase": phase, "artifacts": artifacts}


def cmd_validate_plan(workspace: Path, hypothesis_id: str) -> Dict[str, Any]:
    st = harness_state.load_hypothesis_state(workspace, hypothesis_id)
    plan = harness_state.load_plan(workspace, hypothesis_id)
    structural = validate_plan(
        plan, plan_path=hypothesis_plan_path(workspace, hypothesis_id)
    )
    gate = evaluate_hypothesis_gate(
        "frame",
        state=st,
        structural_result=structural,
        attestation=st.phase_attestations.get("frame"),
    )
    _apply_gate_to_state(st, gate)
    harness_state.save_hypothesis_state(workspace, hypothesis_id, st)
    return _gate_payload(gate)


def cmd_validate_explore(
    workspace: Path, hypothesis_id: str, experiment_id: str
) -> Dict[str, Any]:
    st = harness_state.load_hypothesis_state(workspace, hypothesis_id)
    plan = harness_state.load_plan(workspace, hypothesis_id)
    db = (
        Path(st.db_path)
        if st.db_path
        else experiment_paths(workspace, hypothesis_id, experiment_id).db_path
    )
    pres = presentation_paths(
        workspace / DIR_PRESENTATION, hypothesis_id, experiment_id
    )
    data_dir = pres.output_dir / DIR_DATA
    structural = validate_explore(
        workspace,
        hypothesis_id,
        db_path=db,
        plan=plan,
        data_dir=data_dir,
        recorded_artifacts=st.phase_artifacts.get("explore"),
    )
    gate = evaluate_hypothesis_gate(
        "explore",
        state=st,
        structural_result=structural,
        attestation=st.phase_attestations.get("explore"),
    )
    _apply_gate_to_state(st, gate)
    _record_validation(st, "explore", structural)
    harness_state.save_hypothesis_state(workspace, hypothesis_id, st)
    return _gate_payload(gate)


def cmd_record_claim(
    workspace: Path, hypothesis_id: str, payload: Dict[str, Any]
) -> Dict[str, Any]:
    doc = harness_state.load_claims(workspace, hypothesis_id)
    claim = Claim.model_validate(payload)
    existing = {c.claim_id: i for i, c in enumerate(doc.claims)}
    if claim.claim_id in existing:
        doc.claims[existing[claim.claim_id]] = claim
    else:
        doc.claims.append(claim)
    harness_state.save_claims(workspace, hypothesis_id, doc)
    return {"claims": doc.model_dump(mode="json")}


def cmd_validate_claims(workspace: Path, hypothesis_id: str) -> Dict[str, Any]:
    st = harness_state.load_hypothesis_state(workspace, hypothesis_id)
    doc = harness_state.load_claims(workspace, hypothesis_id)
    structural = validate_claims(doc)
    gate = evaluate_hypothesis_gate(
        "claims",
        state=st,
        structural_result=structural,
        attestation=st.phase_attestations.get("claims"),
    )
    _apply_gate_to_state(st, gate)
    harness_state.save_hypothesis_state(workspace, hypothesis_id, st)
    return _gate_payload(gate)


def cmd_record_contract(
    workspace: Path, hypothesis_id: str, payload: Dict[str, Any]
) -> Dict[str, Any]:
    if isinstance(payload, str):
        payload = harness_state.parse_payload_dict(payload)
    st = harness_state.load_hypothesis_state(workspace, hypothesis_id)
    contract = FigureContract.model_validate(payload)
    st.figure_contracts = [
        c for c in st.figure_contracts if c.contract_id != contract.contract_id
    ]
    st.figure_contracts.append(contract)
    harness_state.save_hypothesis_state(workspace, hypothesis_id, st)
    if st.max_charts > 0 and st.chart_count > st.max_charts:
        return {
            "state": st.model_dump(mode="json"),
            "warning": f"chart_count {st.chart_count} exceeds max_charts cap {st.max_charts}",
        }
    return {"state": st.model_dump(mode="json")}


def cmd_validate_refine(workspace: Path, hypothesis_id: str) -> Dict[str, Any]:
    st = harness_state.load_hypothesis_state(workspace, hypothesis_id)
    prior = prior_phase_gate_issues(st, AnalysisPhase.refine)
    if prior:
        gate = evaluate_hypothesis_gate(
            "refine",
            state=st,
            structural_result=blocked(prior),
            attestation=st.phase_attestations.get("refine"),
        )
        _apply_gate_to_state(st, gate)
        harness_state.save_hypothesis_state(workspace, hypothesis_id, st)
        return _gate_payload(gate)
    structural = validate_refine(st, workspace, hypothesis_id)
    gate = evaluate_hypothesis_gate(
        "refine",
        state=st,
        structural_result=structural,
        attestation=st.phase_attestations.get("refine"),
    )
    _apply_gate_to_state(st, gate)
    _record_validation(st, "refine", gate)
    harness_state.save_hypothesis_state(workspace, hypothesis_id, st)
    return _gate_payload(gate)


def cmd_validate_chart(
    workspace: Path,
    hypothesis_id: str,
    *,
    chart_path: Optional[str] = None,
    code: Optional[str] = None,
) -> Dict[str, Any]:
    st = harness_state.load_hypothesis_state(workspace, hypothesis_id)
    if code:
        structural = validate_chart_script(code)
    elif chart_path:
        structural = validate_chart_file(
            Path(chart_path),
            max_charts=st.max_charts,
            current_count=st.chart_count,
        )
        if structural.status == "PASS":
            st.chart_count += 1
    else:
        return {"error": "provide --chart-path or --code"}
    gate = evaluate_hypothesis_gate(
        "refine",
        state=st,
        structural_result=structural,
        attestation=st.phase_attestations.get("refine"),
    )
    _apply_gate_to_state(st, gate)
    harness_state.save_hypothesis_state(workspace, hypothesis_id, st)
    out = _gate_payload(gate)
    out["chart_count"] = st.chart_count
    return out


def cmd_validate_report_quality(
    workspace: Path, hypothesis_id: str, experiment_id: str
) -> Dict[str, Any]:
    pres = presentation_paths(
        workspace / DIR_PRESENTATION, hypothesis_id, experiment_id
    )
    result = validate_report_quality(
        pres.output_dir,
        workspace=workspace,
        hypothesis_id=hypothesis_id,
    )
    return {
        "status": result.status,
        "issues": [i.model_dump(mode="json") for i in result.issues],
        "recommended_next_step": result.recommended_next_step,
    }


def cmd_record_report_review(
    workspace: Path, hypothesis_id: str, experiment_id: str, payload: Dict[str, Any]
) -> Dict[str, Any]:
    pres = presentation_paths(
        workspace / DIR_PRESENTATION, hypothesis_id, experiment_id
    )
    data = dict(payload)
    data.setdefault("hypothesis_id", hypothesis_id)
    data["report_fingerprint"] = report_content_fingerprint(pres.output_dir)
    review = ReportQualityReview.model_validate(data)
    path = save_report_review(workspace, hypothesis_id, review)
    return {
        "path": str(path),
        "verdict": review.verdict.value,
        "overall_score": review.overall_score,
        "report_fingerprint": review.report_fingerprint,
    }


def cmd_record_synthesis_review(
    workspace: Path, payload: Dict[str, Any]
) -> Dict[str, Any]:
    syn = synthesis_paths(workspace)
    data = dict(payload)
    data["report_fingerprint"] = synthesis_content_fingerprint(syn.output_dir)
    review = SynthesisQualityReview.model_validate(data)
    path = save_synthesis_review(workspace, review)
    return {
        "path": str(path),
        "verdict": review.verdict.value,
        "overall_score": review.overall_score,
    }


def cmd_sync_report_assets(
    workspace: Path, hypothesis_id: str, experiment_id: str
) -> Dict[str, Any]:
    pres = presentation_paths(
        workspace / DIR_PRESENTATION, hypothesis_id, experiment_id
    )
    from agentsociety2.skills.analysis.harness.report_assets import (
        sync_report_assets_from_reports,
    )

    return sync_report_assets_from_reports(pres.output_dir)


def cmd_validate_release(
    workspace: Path, hypothesis_id: str, experiment_id: str
) -> Dict[str, Any]:
    pres = presentation_paths(
        workspace / DIR_PRESENTATION, hypothesis_id, experiment_id
    )
    st = harness_state.load_hypothesis_state(workspace, hypothesis_id)
    prior = prior_phase_gate_issues(st, AnalysisPhase.produce)
    if prior:
        structural = blocked(prior)
    else:
        structural = merge_results(
            validate_release(pres.output_dir),
            validate_report_quality(
                pres.output_dir,
                workspace=workspace,
                hypothesis_id=hypothesis_id,
            ),
            validate_report_review(workspace, hypothesis_id, pres.output_dir),
        )
    gate = evaluate_hypothesis_gate(
        "produce",
        state=st,
        structural_result=structural,
        attestation=st.phase_attestations.get("produce"),
    )
    _apply_gate_to_state(st, gate)
    _record_validation(st, "produce", gate)
    if gate.status == "PASS":
        st.hypothesis_release = ReleaseStatus.ready
    else:
        st.hypothesis_release = ReleaseStatus.blocked
    harness_state.save_hypothesis_state(workspace, hypothesis_id, st)
    out = _gate_payload(gate)
    out["hypothesis_release"] = st.hypothesis_release.value
    return out


def cmd_validate_synthesis(workspace: Path) -> Dict[str, Any]:
    syn_paths = synthesis_paths(workspace)
    st = harness_state.load_synthesis_state(workspace)
    if not st.synthesis_scope_hypothesis_ids:
        pres_root = workspace / DIR_PRESENTATION
        if pres_root.exists():
            st.synthesis_scope_hypothesis_ids = [
                d.name.replace("hypothesis_", "", 1)
                for d in pres_root.iterdir()
                if d.is_dir() and d.name.startswith("hypothesis_")
            ]
    structural = merge_results(
        validate_synthesis(
            workspace,
            synthesis_dir=syn_paths.output_dir,
            scope_hypothesis_ids=st.synthesis_scope_hypothesis_ids,
        ),
        validate_synthesis_review(workspace, syn_paths.output_dir),
    )
    gate = evaluate_synthesis_gate(
        state=st,
        structural_result=structural,
        attestation=st.phase_attestation,
    )
    if gate.status == "PASS":
        st.workspace_release = ReleaseStatus.ready
    else:
        st.workspace_release = ReleaseStatus.blocked
    harness_state.save_synthesis_state(workspace, st)
    return _gate_payload(gate)


def _phase_index(phase: AnalysisPhase) -> int:
    return HYPOTHESIS_PHASE_ORDER.index(phase)


def _prior_phase(target: AnalysisPhase) -> Optional[AnalysisPhase]:
    idx = _phase_index(target)
    if idx == 0:
        return None
    return HYPOTHESIS_PHASE_ORDER[idx - 1]


def cmd_advance(
    workspace: Path,
    hypothesis_id: str,
    experiment_id: str,
    target: str,
) -> Dict[str, Any]:
    try:
        target_phase = AnalysisPhase(target)
    except ValueError:
        return {"error": f"unknown phase: {target}"}

    st = harness_state.load_hypothesis_state(workspace, hypothesis_id)
    if _phase_index(target_phase) <= _phase_index(st.current_phase):
        return {
            "error": f"cannot advance backward from {st.current_phase.value} to {target}"
        }

    prior = _prior_phase(target_phase)
    if prior is not None:
        cp = st.phase_checkpoints.get(prior.value)
        if cp is None or not cp.gate_pass:
            return {
                "error": f"prior phase {prior.value} gate not passed",
                "recommended_next_step": f"Run validate-{prior.value}, record-attestation --phase {prior.value}",
            }

    st.current_phase = target_phase
    harness_state.save_hypothesis_state(workspace, hypothesis_id, st)
    return {
        "current_phase": st.current_phase.value,
        "rubric_keys": PHASE_RUBRIC_KEYS.get(target_phase.value, []),
        "state": st.model_dump(mode="json"),
    }


def cmd_gate_status(
    workspace: Path, hypothesis_id: Optional[str] = None
) -> Dict[str, Any]:
    out: Dict[str, Any] = {"workspace": str(workspace.resolve())}
    if hypothesis_id:
        st = harness_state.load_hypothesis_state(workspace, hypothesis_id)
        out["hypothesis"] = gate_status_hypothesis(st)
    out["synthesis"] = harness_state.load_synthesis_state(workspace).model_dump(
        mode="json"
    )
    return out


def cmd_status(workspace: Path, hypothesis_id: Optional[str] = None) -> Dict[str, Any]:
    return cmd_gate_status(workspace, hypothesis_id)


def cmd_run_loop(
    workspace: Path, hypothesis_id: str, experiment_id: str
) -> Dict[str, Any]:
    st = harness_state.load_hypothesis_state(workspace, hypothesis_id)
    phase = st.current_phase.value
    cp = st.phase_checkpoints.get(phase, {})
    rubric = PHASE_RUBRIC_KEYS.get(phase, [])
    llm_focus = {
        "frame": "Co-design analysis_plan with user; interpret hypothesis and experiment design",
        "explore": "Inspect schema, run EDA, explain limitations — do not finalize claims yet",
        "claims": "Propose confirmatory vs exploratory claims; negotiate with user",
        "refine": "Figure contracts; validate-chart per file; validate-refine before attestation",
        "produce": "Run build-report-context; write bilingual narratives from data/report_context.md",
    }.get(phase, "")
    if phase == "produce":
        steps = [
            "1. Mechanical: build-report-context",
            "2. LLM: report-producer → bilingual reports + JSON metadata",
            "3. LLM: report-reviewer (independent) → record-report-review PASS",
            "4. Mechanical: validate-report-quality (optional pre-check)",
            "5. Mechanical: validate-release (structure + quality + review)",
            f"6. LLM: record-attestation --phase {phase} (rubric: {rubric})",
        ]
        advance_n = "7"
    else:
        steps = [
            f"1. LLM: {llm_focus}",
            f"2. Mechanical: validate-{phase}",
            f"3. LLM: record-attestation --phase {phase} (rubric: {rubric})",
        ]
        advance_n = "4"
    if not isinstance(cp, dict) and getattr(cp, "gate_pass", False):
        steps.append(
            f"{advance_n}. advance --phase {gate_status_hypothesis(st).get('next_phase')}"
        )
    else:
        steps.append(f"{advance_n}. advance after gate PASS")
    if st.hypothesis_release == ReleaseStatus.ready:
        steps = [
            "1. LLM: synthesis-producer → synthesis reports + brief",
            "2. LLM: synthesis-reviewer → record-synthesis-review PASS",
            "3. validate-synthesis + record-attestation --phase synthesis",
        ]
    return {
        "current_phase": phase,
        "hypothesis_release": st.hypothesis_release.value,
        "recommended_next_step": " | ".join(steps),
        "checkpoints": gate_status_hypothesis(st),
    }


def cmd_build_report_context(workspace: Path, hypothesis_id: str) -> Dict[str, Any]:
    from agentsociety2.skills.analysis.harness.report_bundle import write_report_bundle

    return write_report_bundle(workspace, hypothesis_id)


def cmd_validate(
    workspace: Path, hypothesis_id: str, experiment_id: str
) -> Dict[str, Any]:
    return cmd_validate_synthesis(workspace)
