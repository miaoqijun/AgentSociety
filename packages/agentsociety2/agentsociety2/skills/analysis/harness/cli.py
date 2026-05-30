from __future__ import annotations

import hashlib
import json
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
from agentsociety2.skills.analysis.harness.guidance import (
    get_chart_scaffold,
    get_harness_guidance,
    get_payload_template,
    list_payload_templates,
)
from agentsociety2.skills.analysis.harness.models import (
    HYPOTHESIS_PHASE_ORDER,
    AnalysisPhase,
    Claim,
    FigureContract,
    HypothesisAnalysisState,
    MethodRecipeCandidate,
    PhaseAttestation,
    PreferenceCandidate,
    ReflectionReview,
    ReleaseStatus,
    ReflectionItem,
    ReflectionReport,
    PromotedPreference,
    SynthesisAnalysisState,
    UserFeedback,
    ValidationRecord,
)
from agentsociety2.skills.analysis.harness.layout import (
    migrate_legacy_hypothesis_harness,
)
from agentsociety2.skills.analysis.harness.paths import (
    hypothesis_claims_path,
    hypothesis_harness_dir,
    hypothesis_plan_path,
    hypothesis_reflection_path,
    memory_dir,
    method_recipes_dir,
    project_lessons_path,
    synthesis_harness_dir,
    synthesis_reflection_path,
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
    issue,
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


def _iter_files(path: Path) -> List[Path]:
    if path.is_file():
        return [path]
    if path.is_dir():
        return sorted(p for p in path.rglob("*") if p.is_file())
    return []


def _fingerprint_paths(paths: List[Path]) -> str:
    digest = hashlib.sha256()
    for path in sorted({p.resolve() for p in paths}, key=lambda p: str(p)):
        digest.update(str(path).encode("utf-8", errors="replace"))
        if not path.exists():
            digest.update(b"\0MISSING")
            continue
        for file_path in _iter_files(path):
            digest.update(str(file_path).encode("utf-8", errors="replace"))
            try:
                digest.update(file_path.read_bytes())
            except OSError as exc:
                digest.update(f"\0READ_ERROR:{exc}".encode("utf-8", errors="replace"))
    return digest.hexdigest()[:24]


def _fingerprint_payload(payload: Any, paths: List[Path] | None = None) -> str:
    digest = hashlib.sha256()
    digest.update(
        json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str).encode(
            "utf-8", errors="replace"
        )
    )
    if paths:
        digest.update(_fingerprint_paths(paths).encode("utf-8"))
    return digest.hexdigest()[:24]


def _hypothesis_phase_fingerprint(
    workspace: Path,
    hypothesis_id: str,
    phase: str,
    st: HypothesisAnalysisState,
) -> str:
    exp_id = st.experiment_id or "1"
    pres = presentation_paths(workspace / DIR_PRESENTATION, hypothesis_id, exp_id)
    if phase == "frame":
        return _fingerprint_paths([hypothesis_plan_path(workspace, hypothesis_id)])
    if phase == "explore":
        paths = [pres.output_dir / DIR_DATA]
        paths.extend(
            workspace / p if not Path(p).is_absolute() else Path(p)
            for p in st.phase_artifacts.get("explore", [])
        )
        return _fingerprint_paths(paths)
    if phase == "claims":
        return _fingerprint_paths([hypothesis_claims_path(workspace, hypothesis_id)])
    if phase == "refine":
        paths = [Path(p) for p in st.phase_artifacts.get("refine_validated_charts", [])]
        return _fingerprint_payload(
            {
                "figure_contracts": [
                    c.model_dump(mode="json") for c in st.figure_contracts
                ],
                "validated_charts": sorted(
                    st.phase_artifacts.get("refine_validated_charts", [])
                ),
                "chart_count": st.chart_count,
            },
            paths,
        )
    if phase == "produce":
        return _fingerprint_paths(
            [
                pres.output_dir / "report_zh.md",
                pres.output_dir / "report_en.md",
                pres.output_dir / "report_zh.html",
                pres.output_dir / "report_en.html",
                pres.output_dir / "report_outline.json",
                pres.output_dir / "artifact_manifest.json",
                pres.output_dir / "data" / "analysis_summary.json",
                pres.output_dir / "data" / "evidence_index.json",
            ]
        )
    return ""


def _synthesis_fingerprint(workspace: Path) -> str:
    syn = synthesis_paths(workspace)
    return _fingerprint_paths(
        [
            syn.output_dir / "synthesis_report_zh.md",
            syn.output_dir / "synthesis_report_en.md",
            syn.output_dir / "synthesis_report_zh.html",
            syn.output_dir / "synthesis_report_en.html",
            syn.output_dir / "synthesis_brief.json",
        ]
    )


def _attestation_stale_result(structural, *, phase: str, att, current: str):
    if att is None or not getattr(att, "artifact_fingerprint", ""):
        return structural
    if att.artifact_fingerprint == current:
        return structural
    stale = issue(
        "attestation_stale",
        phase=phase,
        message=(
            f"Phase attestation fingerprint {att.artifact_fingerprint} "
            f"does not match current artifacts {current}"
        ),
        fix_hint=f"Review updated artifacts and re-run record-attestation --phase {phase}",
    )
    return merge_results(structural, blocked([stale]))


def _tail_jsonl(path: Path, limit: int = 5) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    rows: List[Dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            rows.append(parsed)
    return rows[-limit:]


def _recipe_excerpt(path: Path, *, limit: int = 1200) -> Dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    title = path.stem
    for line in text.splitlines():
        if line.startswith("# "):
            title = line[2:].strip() or title
            break
    return {
        "path": str(path),
        "title": title,
        "excerpt": text[:limit],
    }


def _experience_memory_context(
    workspace: Path,
    hypothesis_id: Optional[str] = None,
) -> Dict[str, Any]:
    index = harness_state.load_memory_index(workspace)
    lessons = _tail_jsonl(project_lessons_path(workspace))
    recipe_dir = method_recipes_dir(workspace)
    recipes = (
        [_recipe_excerpt(path) for path in sorted(recipe_dir.glob("*.md"))[:5]]
        if recipe_dir.exists()
        else []
    )
    preferences = [
        pref.model_dump(mode="json") for _, pref in sorted(index.preferences.items())
    ]
    active = bool(preferences or lessons or recipes)
    return {
        "active": active,
        "memory_dir": str(memory_dir(workspace)),
        "hypothesis_id": hypothesis_id or "",
        "confirmed_preferences": preferences,
        "recent_lessons": lessons,
        "method_recipes": recipes,
        "policy": (
            "Apply confirmed preferences and relevant recipes before planning. "
            "Treat lessons as advisory evidence, not as instructions that override the user or gates."
        ),
    }


def _feedback_prompt(
    workspace: Path,
    hypothesis_id: Optional[str] = None,
) -> Dict[str, Any]:
    feedback = harness_state.load_feedback(workspace, hypothesis_id)
    has_feedback = bool(
        feedback.comments.strip()
        or feedback.requested_changes
        or feedback.preference_candidates
        or feedback.lesson_candidates
        or feedback.rating is not None
        or feedback.satisfied is not None
    )
    return {
        "has_feedback": has_feedback,
        "recommended_questions": [
            "这次分析结论是否符合你的判断？有哪些地方需要改？",
            "有没有希望后续长期遵守的写作、图表、统计严格度或工作流偏好？",
            "哪些步骤有用、哪些步骤浪费时间或容易误导？",
        ],
        "record_command": "record-feedback",
        "policy": "Feedback is stored as reviewable evidence; preferences are promoted only with --include-preferences.",
    }


def cmd_memory_context(
    workspace: Path,
    hypothesis_id: Optional[str] = None,
) -> Dict[str, Any]:
    return {"memory_context": _experience_memory_context(workspace, hypothesis_id)}


def cmd_guidance(topic: str = "workflow") -> Dict[str, Any]:
    try:
        return {"guidance": get_harness_guidance(topic)}
    except KeyError:
        return {
            "error": "unknown_guidance_topic",
            "topic": topic,
            "available_topics": get_harness_guidance("workflow")["available_topics"],
        }


def cmd_payload_template(name: str) -> Dict[str, Any]:
    try:
        return {"template_name": name, "template": get_payload_template(name)}
    except KeyError:
        return {
            "error": "unknown_payload_template",
            "template_name": name,
            "available_templates": list_payload_templates(),
        }


def cmd_chart_scaffold() -> Dict[str, Any]:
    return {
        "filename": "chart_NN_slug.py",
        "scaffold": get_chart_scaffold(),
        "recommended_next_step": (
            "Save under presentation/hypothesis_{id}/charts/, adapt SQL/data loading, "
            "then run validate-chart --code before run-code."
        ),
    }


def cmd_record_feedback(
    workspace: Path,
    hypothesis_id: Optional[str],
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    feedback = UserFeedback.model_validate(payload)
    if hypothesis_id:
        feedback.hypothesis_id = feedback.hypothesis_id or hypothesis_id
    path = harness_state.save_feedback(workspace, feedback, hypothesis_id)
    return {
        "feedback_path": str(path),
        "feedback": feedback.model_dump(mode="json"),
        "recommended_next_step": "Run draft-reflection or review-reflection before promote-reflection.",
    }


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
            "memory_context": _experience_memory_context(workspace, hypothesis_id),
            "feedback_prompt": _feedback_prompt(workspace, hypothesis_id),
        }
    return {
        "state": st.model_dump(mode="json"),
        "db_path": str(paths.db_path),
        "db_ready": True,
        "presentation_dir": str(pres.output_dir),
        "harness_dir": str(harness_dir),
        "legacy_harness_migrated": migrated,
        "rubric_keys": PHASE_RUBRIC_KEYS.get("frame", []),
        "memory_context": _experience_memory_context(workspace, hypothesis_id),
        "feedback_prompt": _feedback_prompt(workspace, hypothesis_id),
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
        if not att.artifact_fingerprint:
            att.artifact_fingerprint = _synthesis_fingerprint(workspace)
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
    if not att.artifact_fingerprint:
        att.artifact_fingerprint = _hypothesis_phase_fingerprint(
            workspace, hypothesis_id, phase, st
        )
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


def _workspace_relative_paths(workspace: Path, paths: List[str]) -> List[str]:
    root = workspace.resolve()
    rel: List[str] = []
    for raw in paths:
        p = Path(raw)
        if not p.is_absolute():
            p = (workspace / p).resolve()
        else:
            p = p.resolve()
        try:
            rel.append(p.relative_to(root).as_posix())
        except ValueError:
            rel.append(str(p))
    return rel


def cmd_run_explore_eda(
    workspace: Path, hypothesis_id: str, experiment_id: str
) -> Dict[str, Any]:
    """Run EDA from analysis_plan and register explore phase artifacts."""
    from agentsociety2.skills.analysis.data import DataReader
    from agentsociety2.skills.analysis.output import EDAGenerator

    plan = harness_state.load_plan(workspace, hypothesis_id)
    st = harness_state.load_hypothesis_state(workspace, hypothesis_id)
    db = (
        Path(st.db_path)
        if st.db_path
        else experiment_paths(workspace, hypothesis_id, experiment_id).db_path
    )
    if not db.exists():
        return {
            "error": "db_missing",
            "db_path": str(db),
            "fix_hint": "Complete run-experiment before run-explore-eda",
        }

    pres = presentation_paths(
        workspace / DIR_PRESENTATION, hypothesis_id, experiment_id
    )
    data_dir = pres.output_dir / DIR_DATA
    data_dir.mkdir(parents=True, exist_ok=True)

    generator = EDAGenerator()
    reader = DataReader(db)
    requested = plan.target_tables or None
    _, selected, invalid = generator.resolve_table_selection(reader, requested)
    if requested and not selected:
        return {
            "error": "no_target_tables",
            "invalid_tables": invalid,
            "fix_hint": "Fix analysis_plan.target_tables or sqlite schema",
        }

    profile = plan.eda_profile
    files: List[str] = []
    hub: Optional[Path] = None

    if profile == "bundle":
        bundle_profiles = [
            p for p in plan.resolved_eda_profiles() if p not in ("bundle", "eda-hub")
        ]
        files, hub = generator.generate_eda_bundle(
            db,
            data_dir,
            profiles=bundle_profiles or None,
            tables=selected or None,
        )
    elif profile == "quick-stats":
        content = generator.generate_quick_stats(db, tables=selected)
        qs = data_dir / "eda_quick_stats.md"
        qs.write_text(content or "", encoding="utf-8")
        files = [str(qs)]
    elif profile == "eda-hub":
        hub = generator.generate_eda_hub(data_dir)
        files = [str(hub)]
    else:
        runners = {
            "ydata": lambda: generator.generate_ydata_profile(
                db, data_dir, tables=selected
            ),
            "sweetviz": lambda: generator.generate_sweetviz_profile(
                db, data_dir, tables=selected
            ),
            "missingno": lambda: generator.generate_missingno_report(
                db, data_dir, tables=selected
            ),
            "correlation": lambda: generator.generate_correlation_report(
                db, data_dir, tables=selected
            ),
            "pygwalker": lambda: generator.generate_pygwalker_profile(
                db, data_dir, tables=selected
            ),
            "datatable": lambda: generator.generate_datatable_profile(
                db, data_dir, tables=selected
            ),
            "plotly-profile": lambda: generator.generate_plotly_profile(
                db, data_dir, tables=selected
            ),
        }
        runner = runners.get(profile)
        if runner is None:
            return {"error": f"unsupported eda_profile: {profile}"}
        result = runner()
        if result is not None:
            files = [str(result)]

    rel_files = _workspace_relative_paths(workspace, files)
    registered = cmd_record_phase_artifacts(
        workspace, hypothesis_id, "explore", rel_files
    )
    return {
        "command": "run-explore-eda",
        "eda_profile": profile,
        "files": rel_files,
        "hub": _workspace_relative_paths(workspace, [str(hub)])[0] if hub else None,
        "selected_tables": selected,
        "invalid_tables": invalid,
        "registered": registered,
        "recommended_next_step": "Review EDA outputs; explain takeaways to user; then validate-explore",
    }


def cmd_prepare_produce(
    workspace: Path, hypothesis_id: str, experiment_id: str
) -> Dict[str, Any]:
    """Aggregate report context and sync chart/EDA assets before release validation."""
    context = cmd_build_report_context(workspace, hypothesis_id)
    assets = cmd_sync_report_assets(workspace, hypothesis_id, experiment_id)
    return {
        "command": "prepare-produce",
        "report_context": context,
        "sync_assets": assets,
        "recommended_next_step": "Dispatch report-producer with data/report_context.md",
    }


def _completion_epilogue(workspace: Path, hypothesis_id: str) -> Dict[str, Any]:
    """Optional post-pipeline user debrief — never blocks gates."""
    syn = harness_state.load_synthesis_state(workspace)
    st = harness_state.load_hypothesis_state(workspace, hypothesis_id)
    pipeline_ready = (
        st.hypothesis_release == ReleaseStatus.ready
        and syn.workspace_release == ReleaseStatus.ready
    )
    feedback = harness_state.load_feedback(workspace, hypothesis_id)
    has_feedback = bool(
        feedback.comments.strip()
        or feedback.requested_changes
        or feedback.preference_candidates
        or feedback.lesson_candidates
        or feedback.rating is not None
        or feedback.satisfied is not None
    )
    return {
        "active": pipeline_ready,
        "blocking": False,
        "skip_ok": True,
        "purpose": "Optional user debrief and experience capture after pipeline complete",
        "conversation_prompts": [
            "哪些结论最有说服力？哪些结论你还存疑？",
            "报告/图表里有什么希望下次固定或改掉的？",
            "有没有值得沉淀成项目经验的方法或踩坑？",
        ],
        "has_feedback": has_feedback,
        "suggested_flow": [
            "1. Chat with user (prompts above)",
            "2. record-feedback (if user answered)",
            "3. draft-reflection → user review → record-reflection",
            "4. review-reflection → promote-reflection",
            "5. promote-reflection --include-preferences only after explicit user OK",
            "6. memory-context (verify next intake injection)",
        ],
        "commands": {
            "record_feedback": "record-feedback",
            "draft_reflection": f"draft-reflection --hypothesis-id {hypothesis_id}",
            "promote": "promote-reflection",
            "memory_context": "memory-context",
        },
        "recommended_next_step": (
            "Pipeline complete. Optional: debrief with user, then record-feedback / draft-reflection / promote-reflection."
            if pipeline_ready
            else "Finish validate-synthesis and update research-pipeline before epilogue."
        ),
    }


def cmd_validate_plan(workspace: Path, hypothesis_id: str) -> Dict[str, Any]:
    st = harness_state.load_hypothesis_state(workspace, hypothesis_id)
    plan = harness_state.load_plan(workspace, hypothesis_id)
    structural = validate_plan(
        plan, plan_path=hypothesis_plan_path(workspace, hypothesis_id)
    )
    att = st.phase_attestations.get("frame")
    structural = _attestation_stale_result(
        structural,
        phase="frame",
        att=att,
        current=_hypothesis_phase_fingerprint(workspace, hypothesis_id, "frame", st),
    )
    gate = evaluate_hypothesis_gate(
        "frame",
        state=st,
        structural_result=structural,
        attestation=att,
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
    att = st.phase_attestations.get("explore")
    structural = _attestation_stale_result(
        structural,
        phase="explore",
        att=att,
        current=_hypothesis_phase_fingerprint(workspace, hypothesis_id, "explore", st),
    )
    gate = evaluate_hypothesis_gate(
        "explore",
        state=st,
        structural_result=structural,
        attestation=att,
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
    att = st.phase_attestations.get("claims")
    structural = _attestation_stale_result(
        structural,
        phase="claims",
        att=att,
        current=_hypothesis_phase_fingerprint(workspace, hypothesis_id, "claims", st),
    )
    gate = evaluate_hypothesis_gate(
        "claims",
        state=st,
        structural_result=structural,
        attestation=att,
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
    att = st.phase_attestations.get("refine")
    structural = _attestation_stale_result(
        structural,
        phase="refine",
        att=att,
        current=_hypothesis_phase_fingerprint(workspace, hypothesis_id, "refine", st),
    )
    gate = evaluate_hypothesis_gate(
        "refine",
        state=st,
        structural_result=structural,
        attestation=att,
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
        chart = Path(chart_path).resolve()
        validated = set(st.phase_artifacts.get("refine_validated_charts", []))
        structural = validate_chart_file(
            chart,
            max_charts=st.max_charts,
            current_count=len(validated),
        )
        if structural.status == "PASS":
            validated.add(str(chart))
            st.phase_artifacts["refine_validated_charts"] = sorted(validated)
            st.chart_count = len(validated)
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
    from agentsociety2.skills.analysis.harness.report_bundle import (
        cmd_embed_interactive_eda,
    )

    result = sync_report_assets_from_reports(pres.output_dir)
    result["interactive_eda"] = cmd_embed_interactive_eda(workspace, hypothesis_id)
    return result


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
    att = st.phase_attestations.get("produce")
    structural = _attestation_stale_result(
        structural,
        phase="produce",
        att=att,
        current=_hypothesis_phase_fingerprint(workspace, hypothesis_id, "produce", st),
    )
    gate = evaluate_hypothesis_gate(
        "produce",
        state=st,
        structural_result=structural,
        attestation=att,
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
    structural = _attestation_stale_result(
        structural,
        phase="synthesis",
        att=st.phase_attestation,
        current=_synthesis_fingerprint(workspace),
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
    syn_st = harness_state.load_synthesis_state(workspace)
    if hypothesis_id:
        st = harness_state.load_hypothesis_state(workspace, hypothesis_id)
        out["hypothesis"] = gate_status_hypothesis(st)
        out["memory_context"] = _experience_memory_context(workspace, hypothesis_id)
        out["feedback_prompt"] = _feedback_prompt(workspace, hypothesis_id)
        if (
            st.hypothesis_release == ReleaseStatus.ready
            and syn_st.workspace_release == ReleaseStatus.ready
        ):
            out["epilogue"] = _completion_epilogue(workspace, hypothesis_id)
    else:
        out["memory_context"] = _experience_memory_context(workspace)
        out["feedback_prompt"] = _feedback_prompt(workspace)
    out["synthesis"] = syn_st.model_dump(mode="json")
    return out


def cmd_status(workspace: Path, hypothesis_id: Optional[str] = None) -> Dict[str, Any]:
    return cmd_gate_status(workspace, hypothesis_id)


def cmd_run_loop(
    workspace: Path, hypothesis_id: str, experiment_id: str
) -> Dict[str, Any]:
    st = harness_state.load_hypothesis_state(workspace, hypothesis_id)
    syn_st = harness_state.load_synthesis_state(workspace)
    memory_context = _experience_memory_context(workspace, hypothesis_id)
    if (
        st.hypothesis_release == ReleaseStatus.ready
        and syn_st.workspace_release == ReleaseStatus.ready
    ):
        epilogue = _completion_epilogue(workspace, hypothesis_id)
        return {
            "current_phase": "complete",
            "hypothesis_release": st.hypothesis_release.value,
            "workspace_release": syn_st.workspace_release.value,
            "recommended_next_step": epilogue["recommended_next_step"],
            "epilogue": epilogue,
            "checkpoints": gate_status_hypothesis(st),
            "memory_context": memory_context,
            "feedback_prompt": _feedback_prompt(workspace, hypothesis_id),
        }
    phase = st.current_phase.value
    cp = st.phase_checkpoints.get(phase, {})
    rubric = PHASE_RUBRIC_KEYS.get(phase, [])
    llm_focus = {
        "frame": "Co-design analysis_plan with user; interpret hypothesis and experiment design",
        "explore": "Review run-explore-eda outputs; explain limitations — do not finalize claims yet",
        "claims": "Propose confirmatory vs exploratory claims; negotiate with user",
        "refine": "Figure contracts; validate-chart per file; validate-refine before attestation",
        "produce": "Dispatch report-producer with data/report_context.md from prepare-produce",
    }.get(phase, "")
    if phase == "explore":
        steps = [
            "1. Mechanical: run-explore-eda (EDA from analysis_plan + auto record-phase-artifacts)",
            f"2. LLM: {llm_focus}",
            "3. Mechanical: validate-explore",
            f"4. LLM: record-attestation --phase {phase} (rubric: {rubric})",
        ]
        advance_n = "5"
    elif phase == "produce":
        steps = [
            "1. Mechanical: prepare-produce (build-report-context + sync-report-assets)",
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
            "4. research-pipeline update-stage analysis completed",
            "5. Optional epilogue: user debrief → record-feedback / draft-reflection / promote-reflection (non-blocking)",
        ]
    if memory_context["active"]:
        steps.insert(
            0,
            "0. Memory: apply confirmed preferences and relevant method_recipes; treat recent_lessons as advisory",
        )
    return {
        "current_phase": phase,
        "hypothesis_release": st.hypothesis_release.value,
        "recommended_next_step": " | ".join(steps),
        "checkpoints": gate_status_hypothesis(st),
        "memory_context": memory_context,
        "feedback_prompt": _feedback_prompt(workspace, hypothesis_id),
    }


def _slugify_memory_key(text: str, fallback: str) -> str:
    raw = "".join(
        ch.lower() if ch.isalnum() else "_" for ch in (text or "").strip()
    ).strip("_")
    while "__" in raw:
        raw = raw.replace("__", "_")
    return raw[:80] or fallback


def _reflection_path_label(workspace: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(workspace.resolve()).as_posix()
    except ValueError:
        return str(path)


def _attestation_evidence(st: HypothesisAnalysisState) -> List[str]:
    evidence: List[str] = []
    for phase, att in sorted(st.phase_attestations.items()):
        evidence.extend(att.artifacts_read)
        evidence.extend(att.artifacts_written)
        if att.artifact_fingerprint:
            evidence.append(f"attestation:{phase}:{att.artifact_fingerprint[:12]}")
    return sorted(dict.fromkeys(str(item) for item in evidence if item))


def _checkpoint_failures(st: HypothesisAnalysisState) -> List[ReflectionItem]:
    failures: List[ReflectionItem] = []
    for phase, cp in sorted(st.phase_checkpoints.items()):
        if cp.gate_pass:
            continue
        issues = cp.structural_issues or ["gate did not pass"]
        failures.append(
            ReflectionItem(
                item_id=f"{phase}_gate_blocked",
                title=f"{phase} gate needed repair",
                content="; ".join(issues),
                evidence=[f"phase:{phase}"],
                confidence="medium",
            )
        )
    return failures


def _default_method_recipe(
    plan,
    claims_doc,
    st: HypothesisAnalysisState,
) -> MethodRecipeCandidate | None:
    if not plan.research_question and not claims_doc.claims:
        return None
    steps = [
        "Frame research question, metrics, target tables, and limitations before EDA.",
        f"Run {plan.eda_profile} EDA and register generated artifacts.",
        "Separate confirmatory claims from exploratory observations before plotting.",
        "Create figure contracts, validate each chart file, then build report context.",
    ]
    if st.hypothesis_release == ReleaseStatus.ready:
        steps.append("Use release-ready report artifacts as evidence for synthesis.")
    return MethodRecipeCandidate(
        item_id="analysis_protocol",
        recipe_id=_slugify_memory_key(plan.research_question, "analysis_protocol"),
        title="Reusable analysis protocol",
        content=plan.research_question or "Reusable analysis protocol from this run",
        evidence=_attestation_evidence(st),
        applies_when=plan.target_tables + plan.primary_metrics,
        recommended_steps=steps,
        pitfalls=[
            "Do not promote exploratory findings into confirmatory claims without user approval.",
            "Re-attest a phase after editing phase artifacts.",
        ],
        confidence="medium" if st.hypothesis_release != ReleaseStatus.ready else "high",
    )


def cmd_draft_reflection(
    workspace: Path, hypothesis_id: str, experiment_id: str
) -> Dict[str, Any]:
    st = harness_state.load_hypothesis_state(workspace, hypothesis_id)
    plan = harness_state.load_plan(workspace, hypothesis_id)
    claims_doc = harness_state.load_claims(workspace, hypothesis_id)

    what_worked: List[ReflectionItem] = []
    passed = [
        phase for phase, cp in sorted(st.phase_checkpoints.items()) if cp.gate_pass
    ]
    if passed:
        what_worked.append(
            ReflectionItem(
                item_id="passed_gates",
                title="Phase gates passed",
                content=", ".join(passed),
                evidence=[f"phase:{phase}" for phase in passed],
                confidence="high",
            )
        )
    approved_claims = [claim.statement for claim in claims_doc.claims if claim.approved]
    if approved_claims:
        what_worked.append(
            ReflectionItem(
                item_id="approved_claims",
                title="User-approved confirmatory claims",
                content=" | ".join(approved_claims),
                evidence=[f"claim:{claim.claim_id}" for claim in claims_doc.claims],
                confidence="high",
            )
        )

    recipe = _default_method_recipe(plan, claims_doc, st)
    reflection = ReflectionReport(
        hypothesis_id=hypothesis_id,
        experiment_id=experiment_id,
        source="hypothesis",
        what_worked=what_worked,
        what_failed=_checkpoint_failures(st),
        reusable_methods=[recipe] if recipe is not None else [],
        promotion_candidates=[
            "Promote reusable_methods only if the workflow should affect future analyses.",
            "Promote user_preferences_observed only when the user explicitly confirmed them.",
        ],
        caveats=[
            "This is a mechanical draft from harness state; review before promotion.",
            "Do not treat inferred preferences as durable user preferences without confirmation.",
        ],
    )
    path = harness_state.save_reflection(workspace, reflection, hypothesis_id)
    return {
        "reflection_path": str(path),
        "reflection": reflection.model_dump(mode="json"),
        "recommended_next_step": "Review/edit reflection, then run record-reflection or promote-reflection.",
    }


def cmd_record_reflection(
    workspace: Path,
    hypothesis_id: Optional[str],
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    reflection = ReflectionReport.model_validate(payload)
    if hypothesis_id:
        reflection.hypothesis_id = reflection.hypothesis_id or hypothesis_id
        reflection.source = "hypothesis"
    else:
        reflection.source = "synthesis"
    path = harness_state.save_reflection(workspace, reflection, hypothesis_id)
    return {
        "reflection_path": str(path),
        "reflection": reflection.model_dump(mode="json"),
    }


def _review_reflection_payload(
    reflection: ReflectionReport,
    feedback: UserFeedback,
    *,
    include_preferences: bool = False,
) -> ReflectionReview:
    issues = []
    recommendations: List[str] = []
    if not (
        reflection.what_worked
        or reflection.what_failed
        or reflection.reusable_methods
        or reflection.user_preferences_observed
    ):
        issues.append(
            issue(
                "reflection_empty",
                phase="memory",
                message="Reflection has no lessons, methods, or preferences",
                fix_hint="Run draft-reflection or record a reviewed reflection payload",
            )
        )
    for item in [*reflection.what_worked, *reflection.what_failed]:
        if not item.evidence:
            issues.append(
                issue(
                    "reflection_item_missing_evidence",
                    phase="memory",
                    message=f"Reflection item lacks evidence: {item.title}",
                    fix_hint="Add artifact paths, claim ids, attestation refs, or feedback refs",
                )
            )
    for recipe in reflection.reusable_methods:
        if not recipe.recommended_steps:
            issues.append(
                issue(
                    "recipe_missing_steps",
                    phase="memory",
                    message=f"Recipe has no recommended_steps: {recipe.title}",
                    fix_hint="Add concrete steps before promotion",
                )
            )
    if reflection.user_preferences_observed and not include_preferences:
        recommendations.append(
            "Preference candidates are present but will not be promoted without --include-preferences."
        )
    if include_preferences and reflection.user_preferences_observed:
        has_feedback = _has_feedback_record(feedback)
        confirmed = has_feedback and (
            feedback.satisfied is not None
            or feedback.rating is not None
            or bool(feedback.preference_candidates)
            or any(
                "user-confirmed" in e.lower()
                for pref in feedback.preference_candidates
                for e in pref.evidence
            )
        )
        if not confirmed:
            issues.append(
                issue(
                    "preference_confirmation_missing",
                    phase="memory",
                    message="Preference promotion requires record-feedback with rating, satisfaction, or user-confirmed preference candidates",
                    fix_hint="Run record-feedback before promote-reflection --include-preferences",
                )
            )
    if not feedback.comments and not feedback.requested_changes:
        recommendations.append(
            "Ask the user for post-analysis feedback before promoting durable memory."
        )
    verdict = "PASS" if not issues else "NEEDS_REVISION"
    return ReflectionReview(
        verdict=verdict,
        issues=issues,
        recommendations=recommendations,
    )


def cmd_review_reflection(
    workspace: Path,
    hypothesis_id: Optional[str] = None,
    include_preferences: bool = False,
) -> Dict[str, Any]:
    reflection = harness_state.load_reflection(workspace, hypothesis_id)
    feedback = harness_state.load_feedback(workspace, hypothesis_id)
    review = _review_reflection_payload(
        reflection,
        feedback,
        include_preferences=include_preferences,
    )
    path = harness_state.save_reflection_review(workspace, review, hypothesis_id)
    return {
        "review_path": str(path),
        "review": review.model_dump(mode="json"),
        "feedback_prompt": _feedback_prompt(workspace, hypothesis_id),
    }


def _append_jsonl(path: Path, records: List[Dict[str, Any]]) -> None:
    if not records:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True))
            handle.write("\n")


def _write_recipe_markdown(
    workspace: Path,
    recipe: MethodRecipeCandidate,
    source_reflection: str,
) -> str:
    recipe_id = recipe.recipe_id or _slugify_memory_key(recipe.title, "recipe")
    path = method_recipes_dir(workspace) / f"{recipe_id}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"# {recipe.title}",
        "",
        f"- Source reflection: `{source_reflection}`",
        f"- Confidence: `{recipe.confidence}`",
        "",
        "## Summary",
        recipe.content,
        "",
        "## Applies When",
        *(f"- {item}" for item in recipe.applies_when),
        "",
        "## Recommended Steps",
        *(
            f"{idx}. {step}"
            for idx, step in enumerate(recipe.recommended_steps, start=1)
        ),
        "",
        "## Pitfalls",
        *(f"- {item}" for item in recipe.pitfalls),
        "",
        "## Evidence",
        *(f"- `{item}`" for item in recipe.evidence),
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
    return str(path)


def _has_feedback_record(feedback: UserFeedback) -> bool:
    return bool(
        feedback.comments.strip()
        or feedback.requested_changes
        or feedback.preference_candidates
        or feedback.lesson_candidates
        or feedback.rating is not None
        or feedback.satisfied is not None
    )


def _reflection_source_path(workspace: Path, hypothesis_id: Optional[str]) -> Path:
    return (
        synthesis_reflection_path(workspace)
        if hypothesis_id is None
        else hypothesis_reflection_path(workspace, hypothesis_id)
    )


def _promote_preference(
    workspace: Path,
    preference: PreferenceCandidate,
    source_reflection: str,
) -> str:
    key = preference.item_id or _slugify_memory_key(
        f"{preference.category}_{preference.title}", "preference"
    )
    index = harness_state.load_memory_index(workspace)
    index.preferences[key] = PromotedPreference(
        key=key,
        category=preference.category,
        value=preference.value or preference.content,
        evidence=preference.evidence,
        confidence=preference.confidence,
        source_reflection=source_reflection,
    )
    if source_reflection not in index.promoted_reflections:
        index.promoted_reflections.append(source_reflection)
    harness_state.save_memory_index(workspace, index)
    return key


def cmd_promote_reflection(
    workspace: Path,
    hypothesis_id: Optional[str] = None,
    include_preferences: bool = False,
    include_recipes: bool = True,
    include_lessons: bool = True,
) -> Dict[str, Any]:
    reflection = harness_state.load_reflection(workspace, hypothesis_id)
    feedback = harness_state.load_feedback(workspace, hypothesis_id)
    review = _review_reflection_payload(
        reflection,
        feedback,
        include_preferences=include_preferences,
    )
    harness_state.save_reflection_review(workspace, review, hypothesis_id)
    if review.verdict != "PASS":
        return {
            "status": "BLOCKED",
            "error": "reflection_review_blocked",
            "review": review.model_dump(mode="json"),
            "feedback_prompt": _feedback_prompt(workspace, hypothesis_id),
            "recommended_next_step": "Revise reflection or record-feedback, then rerun promote-reflection.",
        }

    reflection_path = _reflection_source_path(workspace, hypothesis_id)
    if not reflection_path.exists():
        reflection_path = harness_state.save_reflection(
            workspace, reflection, hypothesis_id
        )
    source_reflection = _reflection_path_label(workspace, reflection_path)

    index = harness_state.load_memory_index(workspace)
    already_promoted = source_reflection in index.promoted_reflections
    if already_promoted and not include_preferences:
        return {
            "status": "SKIPPED",
            "reason": "reflection_already_promoted",
            "source_reflection": source_reflection,
            "lessons_promoted": 0,
            "recipe_paths": [],
            "preference_keys": [],
            "reflection_review": review.model_dump(mode="json"),
            "memory_dir": str(memory_dir(workspace).resolve()),
            "recommended_next_step": "Edit reflection and promote again, or use --include-preferences after record-feedback.",
        }

    lesson_records: List[Dict[str, Any]] = []
    if include_lessons and not already_promoted:
        for kind, items in (
            ("worked", reflection.what_worked),
            ("failed", reflection.what_failed),
        ):
            for item in items:
                lesson_records.append(
                    {
                        "kind": kind,
                        "title": item.title,
                        "content": item.content,
                        "evidence": item.evidence,
                        "confidence": item.confidence,
                        "source_reflection": source_reflection,
                        "promoted_at": datetime.now(UTC).isoformat(),
                    }
                )
        _append_jsonl(project_lessons_path(workspace), lesson_records)

    recipe_paths: List[str] = []
    if include_recipes and not already_promoted:
        recipe_paths = [
            _write_recipe_markdown(workspace, recipe, source_reflection)
            for recipe in reflection.reusable_methods
        ]

    preference_keys: List[str] = []
    if include_preferences:
        merged_by_key: Dict[str, PreferenceCandidate] = {}
        for pref in [
            *reflection.user_preferences_observed,
            *feedback.preference_candidates,
        ]:
            key = pref.item_id or _slugify_memory_key(
                f"{pref.category}_{pref.title}", "preference"
            )
            merged_by_key[key] = pref
        preference_keys = [
            _promote_preference(workspace, pref, source_reflection)
            for _, pref in sorted(merged_by_key.items())
        ]

    if source_reflection not in index.promoted_reflections:
        index.promoted_reflections.append(source_reflection)
        harness_state.save_memory_index(workspace, index)

    return {
        "status": "PROMOTED",
        "source_reflection": source_reflection,
        "already_promoted": already_promoted,
        "lessons_promoted": len(lesson_records),
        "recipe_paths": recipe_paths,
        "preference_keys": preference_keys,
        "reflection_review": review.model_dump(mode="json"),
        "memory_dir": str((workspace / ".agentsociety" / "memory").resolve()),
        "preference_policy": (
            "preferences promoted"
            if include_preferences
            else "preferences skipped; rerun with include_preferences=True after user confirmation"
        ),
    }


def cmd_build_report_context(workspace: Path, hypothesis_id: str) -> Dict[str, Any]:
    from agentsociety2.skills.analysis.harness.report_bundle import write_report_bundle

    return write_report_bundle(workspace, hypothesis_id)


def cmd_validate(
    workspace: Path, hypothesis_id: str, experiment_id: str
) -> Dict[str, Any]:
    return cmd_validate_synthesis(workspace)
