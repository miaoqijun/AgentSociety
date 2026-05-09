#!/usr/bin/env python3
"""Paper-orchestrator CLI (entry script invoked by ``ags.py paper-orchestrator``).

Subcommands (each emits a single-line JSON envelope on stdout):

    init-meta     Write paper_meta.yaml from JSON args supplied by Claude.
    intake        Initialize <workspace>/paper/ tree + state machine.
    build-pack    Run the adapter -> ResearchPack json.
    framing       Stub: persists Storyline output produced by Claude.
    evidence      Stub: persists EvidenceBacklog output produced by Claude.
    architecture  Stub: persists Claim/Figure/Section artifacts produced by Claude.
    review        Stub: persists ReviewRound output produced by Claude.
    compile       Build LaTeX tree from manuscript markdown + figures and run latexmk.
    run-loop      Drive the produce -> compose -> compile pipeline.
    status        Dump current paper_state.yaml + summary counts.

Every subcommand returns exit code 0 on success, 1 on caller-fixable
error, 2 on missing prerequisites, and prints a JSON envelope last so
Claude / the orchestrator script can parse the outcome programmatically.

The CLI runs no LLM calls itself, so ``main()`` sets sentinel
``AGENTSOCIETY_LLM_API_KEY`` / ``_API_BASE`` defaults *before* triggering
the ``agentsociety2`` package import cascade, allowing direct
``python -m agentsociety2.skills.paper.cli.generate_paper ...`` invocation
without provisioning a real API key.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime
from functools import wraps
import json
import os
import re
import shutil
import sys
import traceback
from pathlib import Path
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Lazy-loaded agentsociety2 imports
# ---------------------------------------------------------------------------


_paper_paths = None
_bib_writer = None
_adapter_research_pack_builder = None
_interactive_meta = None
_compiler = None
_figure_packer = None
_latex_assembly = None
_md_to_tex = None
_envelope = None
_models = None
_state = None  # namespace bag for state submodules

_RE_CITE = re.compile(r"\[CITE:([^\]]+)\]")
_RE_REF_FIG = re.compile(r"(?:\[FIG:|\\ref\{fig:)([^}\]]+)")


def _ensure_paper_imports() -> None:
    """Load every agentsociety2.skills.paper.* module lazily.

    The CLI never calls an LLM, so we pre-seed sentinel env vars *before*
    importing anything from ``agentsociety2`` (whose ``__init__.py``
    validates ``AGENTSOCIETY_LLM_API_KEY`` / ``_API_BASE`` at module-load
    time).  This keeps ``python -m`` invocation cheap for paper-skill
    users who haven't configured an LLM.
    """

    global _paper_paths, _bib_writer, _adapter_research_pack_builder
    global _interactive_meta, _compiler, _figure_packer, _latex_assembly
    global _md_to_tex, _envelope, _models, _state

    if _paper_paths is not None:
        return

    os.environ.setdefault("MEM0_TELEMETRY", "False")
    os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")
    os.environ.setdefault("AGENTSOCIETY_LLM_API_KEY", "paper-orchestrator-cli")
    os.environ.setdefault("AGENTSOCIETY_LLM_API_BASE", "https://api.openai.com/v1")

    from agentsociety2.skills.paper import paths as paper_paths_mod
    from agentsociety2.skills.paper.adapter import bib_writer as bib_writer_mod
    from agentsociety2.skills.paper.adapter import (
        research_pack_builder as research_pack_builder_mod,
    )
    from agentsociety2.skills.paper.cli import interactive_meta as interactive_meta_mod
    from agentsociety2.skills.paper.compose import (
        compiler as compiler_mod,
    )
    from agentsociety2.skills.paper.compose import (
        figure_packer as figure_packer_mod,
    )
    from agentsociety2.skills.paper.compose import (
        latex_assembly as latex_assembly_mod,
    )
    from agentsociety2.skills.paper.compose import (
        md_to_tex as md_to_tex_mod,
    )
    from agentsociety2.skills.paper import envelope as envelope_mod
    from agentsociety2.skills.paper import models as models_mod
    from agentsociety2.skills.paper.state import (
        claim_ledger as st_claim_ledger,
    )
    from agentsociety2.skills.paper.state import (
        evidence_backlog as st_evidence_backlog,
    )
    from agentsociety2.skills.paper.state import (
        figure_argument as st_figure_argument,
    )
    from agentsociety2.skills.paper.state import (
        human_gates as st_human_gates,
    )
    from agentsociety2.skills.paper.state import (
        paper_state as st_paper_state,
    )
    from agentsociety2.skills.paper.state import (
        research_pack as st_research_pack,
    )
    from agentsociety2.skills.paper.state import (
        reviews as st_reviews,
    )
    from agentsociety2.skills.paper.state import (
        runs as st_runs,
    )
    from agentsociety2.skills.paper.state import (
        storyline as st_storyline,
    )

    _paper_paths = paper_paths_mod
    _bib_writer = bib_writer_mod
    _adapter_research_pack_builder = research_pack_builder_mod
    _interactive_meta = interactive_meta_mod
    _compiler = compiler_mod
    _figure_packer = figure_packer_mod
    _latex_assembly = latex_assembly_mod
    _md_to_tex = md_to_tex_mod
    _envelope = envelope_mod
    _models = models_mod

    class _StateBag:
        pass

    _state = _StateBag()
    _state.claim_ledger = st_claim_ledger
    _state.evidence_backlog = st_evidence_backlog
    _state.figure_argument = st_figure_argument
    _state.human_gates = st_human_gates
    _state.paper_state = st_paper_state
    _state.research_pack = st_research_pack
    _state.reviews = st_reviews
    _state.runs = st_runs
    _state.storyline = st_storyline


# ---------------------------------------------------------------------------
# Envelope plumbing  (legacy ``_emit`` shape preserved for ags.py consumers)
# ---------------------------------------------------------------------------


def _emit(payload: Dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
    sys.stdout.write("\n")
    sys.stdout.flush()


def _ok(envelope_kwargs: Optional[Dict[str, Any]] = None, **payload: Any) -> int:
    env = _envelope.build_envelope("DONE", **(envelope_kwargs or {}))
    _emit({"success": True, "envelope": json.loads(_envelope.envelope_to_json(env)), **payload})
    return 0


def _error(message: str, *, status: str = "BLOCKED", **payload: Any) -> int:
    env = _envelope.build_envelope(status, blocking_reason=message, severity="fatal")
    _emit({"success": False, "error": message, "envelope": json.loads(_envelope.envelope_to_json(env)), **payload})
    return 1


def _missing_prereq(message: str, **payload: Any) -> int:
    env = _envelope.build_envelope(
        "NEEDS_CONTEXT",
        blocking_reason=message,
        recommended_next_step=payload.get("recommended_next_step"),
        severity="warning",
    )
    _emit({"success": False, "error": message, "envelope": json.loads(_envelope.envelope_to_json(env)), **payload})
    return 2


def _human_gate_required(message: str, **payload: Any) -> int:
    env = _envelope.build_envelope(
        "HUMAN_GATE_REQUIRED",
        blocking_reason=message,
        recommended_next_step=payload.get("recommended_next_step"),
        severity="fatal",
        key_findings=payload.get("key_findings"),
        artifacts_written=payload.get("artifacts_written"),
    )
    _emit(
        {
            "success": False,
            "error": message,
            "envelope": json.loads(_envelope.envelope_to_json(env)),
            **payload,
        }
    )
    return 1


def _ensure_run_timestamp(workspace: Path) -> str:
    timestamp = _state.runs.latest_run(workspace)
    if timestamp is not None:
        return timestamp
    timestamp, _ = _state.runs.open_run(workspace)
    return timestamp


def _record_dispatch_plan(
    workspace: Path,
    *,
    target_skill: str,
    target_subagent: Optional[str],
    notes: str,
    recommended_next_step: Optional[str] = None,
    severity: str = "info",
) -> str:
    timestamp = _ensure_run_timestamp(workspace)
    record = _state.runs.new_dispatch(
        workspace,
        timestamp,
        target_skill=target_skill,
        target_subagent=target_subagent,
        notes=notes,
    )
    envelope = _envelope.build_envelope(
        "DONE",
        key_findings=[notes],
        recommended_next_step=recommended_next_step,
        severity=severity,
    )
    _state.runs.complete_dispatch(
        workspace,
        timestamp,
        record,
        envelope=envelope,
        failed=False,
    )
    path = _paper_paths.dispatch_record_path(workspace, timestamp, record.dispatch_num)
    return str(path)


# ---------------------------------------------------------------------------
# Path / workspace helpers
# ---------------------------------------------------------------------------


def _resolve_workspace(raw: str) -> Path:
    return Path(raw).expanduser().resolve()


@contextmanager
def _workspace_cwd(workspace: Path):
    previous = Path.cwd()
    changed = False
    try:
        if workspace.exists():
            os.chdir(workspace)
            changed = True
        yield workspace
    finally:
        if changed:
            os.chdir(previous)


def _workspace_command(func):
    @wraps(func)
    def wrapper(args: argparse.Namespace) -> int:
        workspace = _resolve_workspace(args.workspace)
        with _workspace_cwd(workspace):
            return func(args)

    return wrapper


def _read_payload(raw: str) -> Any:
    candidate = Path(raw).expanduser()
    if candidate.exists():
        return json.loads(candidate.read_text(encoding="utf-8"))
    return json.loads(raw)


# ---------------------------------------------------------------------------
# Subcommand: init-meta
# ---------------------------------------------------------------------------


@_workspace_command
def cmd_init_meta(args: argparse.Namespace) -> int:
    workspace = _resolve_workspace(args.workspace)
    if not args.payload:
        return _missing_prereq(
            "init-meta requires --payload <json | json-file> with title/authors/affils.",
            recommended_next_step="Conduct paper_meta intake per stages/intake.md and re-run with --payload.",
        )
    try:
        payload = _read_payload(args.payload)
        out_path = _interactive_meta.write_meta_from_json(workspace, payload=payload)
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        return _error(f"failed to write paper_meta.yaml: {exc}")

    return _ok(
        {
            "artifacts_written": [str(out_path)],
            "key_findings": ["paper_meta.yaml initialized"],
            "recommended_next_step": "run `paper-orchestrator intake`",
        },
        meta_path=str(out_path),
    )


# ---------------------------------------------------------------------------
# Subcommand: intake
# ---------------------------------------------------------------------------


@_workspace_command
def cmd_intake(args: argparse.Namespace) -> int:
    workspace = _resolve_workspace(args.workspace)
    if not _paper_paths.paper_meta_path(workspace).exists():
        return _missing_prereq(
            "paper_meta.yaml missing; run `paper-orchestrator init-meta` first.",
            recommended_next_step="paper-orchestrator init-meta --workspace . --payload ...",
        )

    state = _state.paper_state.initialize(workspace)
    return _ok(
        {
            "artifacts_written": [str(_paper_paths.paper_state_path(workspace))],
            "key_findings": [f"paper_state initialized at phase={state.current_phase.value}"],
            "recommended_next_step": "run `paper-orchestrator build-pack` (paper-adapter)",
        },
        current_phase=state.current_phase.value,
    )


# ---------------------------------------------------------------------------
# Subcommand: build-pack  (adapter wrapper)
# ---------------------------------------------------------------------------


@_workspace_command
def cmd_build_pack(args: argparse.Namespace) -> int:
    workspace = _resolve_workspace(args.workspace)
    if not _state.paper_state.exists(workspace):
        return _missing_prereq(
            "paper_state.yaml missing; run `paper-orchestrator intake` first.",
            recommended_next_step="paper-orchestrator intake --workspace .",
        )
    try:
        pack = _adapter_research_pack_builder.build_research_pack(
            workspace,
            research_objective=args.research_objective or None,
        )
        _state.research_pack.save(workspace, pack)
    except Exception as exc:
        return _error(f"failed to build research pack: {exc}", traceback=traceback.format_exc())

    state = _state.paper_state.load(workspace)
    if state.current_phase == _models.PaperPhase.intake:
        _state.paper_state.advance_phase(state, target=_models.PaperPhase.framing)
        _state.paper_state.save(workspace, state)

    return _ok(
        {
            "artifacts_read": [str(workspace)],
            "artifacts_written": [str(_paper_paths.research_pack_path(workspace))],
            "key_findings": [
                f"hypotheses={len(pack.hypotheses)}",
                f"experiments={len(pack.experiments)}",
                f"figures={len(pack.figures)}",
                f"literature={len(pack.literature)}",
            ],
            "recommended_next_step": "dispatch paper-framing producer subagent",
        },
        pack_path=str(_paper_paths.research_pack_path(workspace)),
        counts={
            "hypotheses": len(pack.hypotheses),
            "experiments": len(pack.experiments),
            "analyses": len(pack.analyses),
            "figures": len(pack.figures),
            "literature": len(pack.literature),
        },
        current_phase=state.current_phase.value,
    )


# ---------------------------------------------------------------------------
# Generic "persist artifact" command (framing / evidence / architecture / review)
# ---------------------------------------------------------------------------


def _artifact_registry() -> Dict[str, Dict[str, Any]]:
    return {
        "storyline": {
            "model": _models.StorylineMap,
            "exists": lambda ws: _state.storyline.exists(ws),
            "save": lambda ws, m: _state.storyline.save(ws, m),
            "json_path": _paper_paths.storyline_json_path,
            "advance_to": _models.PaperPhase.evidence_audit,
        },
        "evidence_backlog": {
            "model": _models.EvidenceBacklog,
            "exists": lambda ws: _state.evidence_backlog.exists(ws),
            "save": lambda ws, m: _state.evidence_backlog.save(ws, m),
            "json_path": _paper_paths.evidence_backlog_json_path,
            "advance_to": _models.PaperPhase.expansion_plan,
        },
        "claim_ledger": {
            "model": _models.ClaimLedger,
            "exists": lambda ws: _state.claim_ledger.exists(ws),
            "save": lambda ws, m: _state.claim_ledger.save(ws, m),
            "json_path": _paper_paths.claim_ledger_json_path,
            "advance_to": _models.PaperPhase.manuscript_build,
        },
        "figure_argument_map": {
            "model": _models.FigureArgumentMap,
            "exists": lambda ws: _state.figure_argument.exists(ws),
            "save": lambda ws, m: _state.figure_argument.save(ws, m),
            "json_path": _paper_paths.figure_argument_json_path,
            "advance_to": _models.PaperPhase.manuscript_build,
        },
    }


def _persist_artifact(workspace: Path, artifact: str, payload: Any) -> int:
    spec = _artifact_registry().get(artifact)
    if spec is None:
        return _error(f"unknown artifact: {artifact}")
    if not isinstance(payload, dict):
        return _error(f"{artifact} payload must be a JSON object")
    try:
        model = spec["model"].model_validate(payload)
    except Exception as exc:
        return _error(f"{artifact} payload failed validation: {exc}")
    spec["save"](workspace, model)
    out_path = spec["json_path"](workspace)

    state = _state.paper_state.load(workspace)
    target = spec["advance_to"]
    if target is not None and target.value != state.current_phase.value:
        try:
            _state.paper_state.advance_phase(state, target=target)
            _state.paper_state.save(workspace, state)
        except ValueError:
            pass

    return _ok(
        {
            "artifacts_written": [str(out_path)],
            "key_findings": [f"{artifact} persisted"],
            "recommended_next_step": "advance to next stage per phase_diagram",
        },
        artifact=artifact,
        path=str(out_path),
        current_phase=state.current_phase.value,
    )


def _ensure_review_round_started(
    state: "_models.PaperState",
    round_num: int,
) -> "_models.PaperState":
    if round_num <= 0:
        round_num = 1
    while state.round < round_num:
        _state.paper_state.begin_round(state)
    return state


def _mark_review_in_progress(
    workspace: Path,
    state: "_models.PaperState",
    round_num: int,
) -> "_models.PaperState":
    _ensure_review_round_started(state, round_num)
    state.current_phase = _models.PaperPhase.skeptical_review
    if state.release_status not in {
        _models.ReleaseStatus.ready,
        _models.ReleaseStatus.released,
    }:
        state.release_status = _models.ReleaseStatus.in_review
    _state.paper_state.save(workspace, state)
    return state


def _route_from_review_round(
    review_round: "_models.ReviewRound",
) -> "_models.PaperPhase":
    if review_round.reviews and not review_round.unresolved_fatal and all(
        review.verdict == "accept" for review in review_round.reviews
    ):
        return _models.PaperPhase.release_gate
    return _models.PaperPhase.revision_router


def _phase_recommended_next_step(phase: "_models.PaperPhase") -> str:
    mapping = {
        _models.PaperPhase.framing: "dispatch paper-framing producer subagent",
        _models.PaperPhase.evidence_audit: "dispatch paper-evidence-expansion audit subagent",
        _models.PaperPhase.expansion_plan: "persist evidence backlog, then dispatch paper-architecture",
        _models.PaperPhase.manuscript_build: "dispatch paper-architecture claim_ledger / figure_argument_map / draft_section",
        _models.PaperPhase.skeptical_review: "dispatch paper-skeptical-review reviewers",
        _models.PaperPhase.revision_router: "run revision-router against the latest review round",
        _models.PaperPhase.release_gate: "compile and check final release blockers",
    }
    return mapping.get(phase, "advance the paper orchestrator to the next phase")


def _manuscript_exists(workspace: Path) -> bool:
    return bool(
        _read_manuscript_section(workspace, _paper_paths.MANUSCRIPT_ABSTRACT_FILENAME)
        or _read_manuscript_section(workspace, _paper_paths.MANUSCRIPT_MAIN_FILENAME)
        or _read_manuscript_results(workspace)
        or _read_manuscript_section(workspace, _paper_paths.MANUSCRIPT_DISCUSSION_FILENAME)
    )


def _latest_review_round(
    workspace: Path,
) -> tuple[int, Optional["_models.ReviewRound"]]:
    latest_round = _state.reviews.latest_round_num(workspace)
    if latest_round == 0:
        return 0, None
    return latest_round, _state.reviews.load_round(workspace, latest_round)


def _open_review_round(
    workspace: Path,
) -> tuple[int, Optional["_models.ReviewRound"]]:
    latest_round, review_round = _latest_review_round(workspace)
    if latest_round == 0 or review_round is None or review_round.completed_at is not None:
        return 0, None
    return latest_round, review_round


def _review_target_phase(review: "_models.Review") -> Optional["_models.PaperPhase"]:
    route = (review.reroute_target or "").strip() or (_state.reviews.route_for(review.verdict) or "")
    route = route.strip()
    if route in {"human_gate"} or review.human_gate_flag:
        return None
    if route in {"wording", "paragraph", "section", "figure-plan"}:
        return _models.PaperPhase.manuscript_build
    if route in {"evidence"}:
        return _models.PaperPhase.evidence_audit
    if route in {"framing"}:
        return _models.PaperPhase.framing
    return _models.PaperPhase.manuscript_build


def _research_pack_source_text(pack: "_models.ResearchPack") -> str:
    chunks: List[str] = [
        pack.topic,
        pack.research_objective,
        pack.synthesis_report,
    ]
    chunks.extend(h.text for h in pack.hypotheses)
    chunks.extend(exp.design for exp in pack.experiments)
    chunks.extend(analysis.summary for analysis in pack.analyses)
    return "\n".join(chunk for chunk in chunks if chunk)


def _platform_mentions(text: str) -> set[str]:
    lowered = text.lower()
    mentions: set[str] = set()
    if re.search(r"\bfacebook\b", lowered):
        mentions.add("facebook")
    if re.search(r"\btwitter\b", lowered):
        mentions.add("twitter")
    return mentions


def _source_consistency_problems(
    pack: "_models.ResearchPack",
    *texts: str,
) -> List[str]:
    source_text = _research_pack_source_text(pack)
    if not source_text.strip():
        return []

    manuscript_text = "\n".join(texts)
    source_platforms = _platform_mentions(source_text)
    manuscript_platforms = _platform_mentions(manuscript_text)
    source_lower = source_text.lower()
    manuscript_lower = manuscript_text.lower()
    problems: List[str] = []

    if "facebook" in source_platforms and "twitter" in manuscript_platforms:
        problems.append(
            "source materials describe a Facebook-based study, but the manuscript describes a Twitter-based study"
        )
    if "twitter" in source_platforms and "facebook" in manuscript_platforms:
        problems.append(
            "source materials describe a Twitter-based study, but the manuscript describes a Facebook-based study"
        )

    source_subscription = re.search(r"\bsubscrib(?:e|ed|ing|ers?|tion)\b", source_lower)
    manuscript_subscription = re.search(r"\bsubscrib(?:e|ed|ing|ers?|tion)\b", manuscript_lower)
    manuscript_follow_accounts = re.search(
        r"\bfollow(?:ing|ed|s)?\s+(?:accounts?|outlets?)\b",
        manuscript_lower,
    )
    if source_subscription and manuscript_follow_accounts and not manuscript_subscription:
        problems.append(
            "source materials describe a subscription intervention, but the manuscript describes a follow-based intervention"
        )

    return problems


def _coerce_phase_value(raw: Optional[str]) -> Optional["_models.PaperPhase"]:
    if not raw:
        return None
    normalized = raw.strip().lower().replace("_", "-")
    for phase in _models.PaperPhase:
        if phase.value == normalized:
            return phase
    return None


def _phase_from_gate(gate: "_models.HumanGate") -> "_models.PaperPhase":
    accepted = _coerce_phase_value(gate.accepted_version)
    if accepted is not None:
        return accepted

    proposed = (gate.proposed_pivot or "").strip().lower().replace("_", "-")
    if proposed in {"framing"}:
        return _models.PaperPhase.framing
    if proposed in {"evidence", "evidence-audit", "expansion-plan"}:
        return _models.PaperPhase.evidence_audit
    if proposed in {"wording", "paragraph", "section", "figure-plan", "manuscript-build"}:
        return _models.PaperPhase.manuscript_build
    if proposed in {"release-gate"}:
        return _models.PaperPhase.release_gate
    return _models.PaperPhase.framing


def _is_literature_issue(review: "_models.Review") -> bool:
    issue = (review.issue_type or "").strip().lower().replace("-", "_")
    return "literature" in issue or "citation" in issue or "reference" in issue


def _is_figure_issue(review: "_models.Review") -> bool:
    target = (review.target_layer or "").strip().lower().replace("-", "_")
    reroute = (review.reroute_target or "").strip().lower().replace("-", "_")
    return target == "figure_plan" or reroute == "figure_plan"


def _open_gate_from_review(
    workspace: Path,
    review: "_models.Review",
    *,
    round_num: int,
) -> "_models.HumanGate":
    pending = _state.human_gates.pending(workspace)
    marker = f"{review.reviewer_profile}:{review.target_artifact}:{review.issue_type}:{round_num}"
    for gate in pending:
        if gate.note == marker:
            return gate
    return _state.human_gates.open_gate(
        workspace,
        triggering_issue=review.issue_type or "review escalation",
        proposed_pivot=review.reroute_target or review.target_layer,
        severity="major" if review.verdict in {"pivot_major", "fatal"} else "moderate",
        rationale=review.raw_text or "",
        note=marker,
    )


def _route_revision_round(
    workspace: Path,
    state: "_models.PaperState",
    review_round: "_models.ReviewRound",
) -> tuple[Optional["_models.PaperPhase"], List[str], List[str], List[str]]:
    next_phases: List[_models.PaperPhase] = []
    findings: List[str] = []
    gate_ids: List[str] = []
    dispatch_paths: List[str] = []

    for review in review_round.reviews:
        if review.resolved_state == "resolved":
            continue
        cap_exceeded = False

        if _is_figure_issue(review):
            if state.counters.figure_regenerations >= 2:
                cap_exceeded = True
            else:
                state.counters.figure_regenerations += 1

        if review.target_layer == "evidence" and _is_literature_issue(review):
            if state.counters.citation_augmentations >= 2:
                cap_exceeded = True
            else:
                state.counters.citation_augmentations += 1

        target_phase = _review_target_phase(review)
        if target_phase is None or cap_exceeded:
            gate = _open_gate_from_review(
                workspace,
                review,
                round_num=review_round.round_num,
            )
            gate_ids.append(gate.gate_id)
            finding = (
                f"issue={review.issue_type or 'unspecified'} verdict={review.verdict} -> human_gate:{gate.gate_id}"
                + (" cap_exceeded=true" if cap_exceeded else "")
            )
            findings.append(finding)
            dispatch_paths.append(
                _record_dispatch_plan(
                    workspace,
                    target_skill="human-gate",
                    target_subagent=None,
                    notes=finding,
                    recommended_next_step="review and decide the pending human gate entry",
                    severity="fatal",
                )
            )
            continue
        next_phases.append(target_phase)
        finding = (
            f"issue={review.issue_type or 'unspecified'} verdict={review.verdict} -> {target_phase.value}"
        )
        findings.append(finding)
        skill_map = {
            _models.PaperPhase.framing: ("agentsociety-paper-framing", "producer"),
            _models.PaperPhase.evidence_audit: ("agentsociety-paper-evidence-expansion", "producer"),
            _models.PaperPhase.manuscript_build: ("agentsociety-paper-architecture", "producer"),
        }
        target_skill, target_subagent = skill_map.get(
            target_phase,
            ("paper-orchestrator", None),
        )
        dispatch_paths.append(
            _record_dispatch_plan(
                workspace,
                target_skill=target_skill,
                target_subagent=target_subagent,
                notes=finding,
                recommended_next_step=_phase_recommended_next_step(target_phase),
            )
        )

    if gate_ids:
        state.pending_human_gate = gate_ids[-1]
        state.last_blocker = "human gate required by revision-router"
        state.release_status = _models.ReleaseStatus.blocked
        _state.paper_state.save(workspace, state)
        return None, findings, gate_ids, dispatch_paths

    if not next_phases:
        dispatch_paths.append(
            _record_dispatch_plan(
                workspace,
                target_skill="paper-orchestrator",
                target_subagent="release-gate-judge",
                notes="all unresolved issues cleared; route to release-gate",
                recommended_next_step=_phase_recommended_next_step(_models.PaperPhase.release_gate),
            )
        )
        return _models.PaperPhase.release_gate, findings, gate_ids, dispatch_paths

    if _models.PaperPhase.framing in next_phases:
        _state.paper_state.save(workspace, state)
        return _models.PaperPhase.framing, findings, gate_ids, dispatch_paths
    if _models.PaperPhase.evidence_audit in next_phases:
        _state.paper_state.save(workspace, state)
        return _models.PaperPhase.evidence_audit, findings, gate_ids, dispatch_paths
    _state.paper_state.save(workspace, state)
    return _models.PaperPhase.manuscript_build, findings, gate_ids, dispatch_paths


def _release_gate_verdict(
    workspace: Path,
) -> tuple[str, List[str], Optional[str]]:
    findings: List[str] = []

    meta = _interactive_meta.load_meta(workspace)
    criterion_1 = bool(meta.title.strip() and meta.affils and any(a.corresponding for a in meta.authors))
    findings.append(f"criterion_1={'pass' if criterion_1 else 'fail'}")
    if not criterion_1:
        return "BLOCKED", findings, "paper_meta.yaml does not satisfy release-gate criterion_1"

    storyline = _state.storyline.load(workspace) if _state.storyline.exists(workspace) else None
    criterion_2 = bool(
        storyline
        and storyline.current_angle.strip()
        and storyline.contribution_statement.strip()
    )
    findings.append(f"criterion_2={'pass' if criterion_2 else 'fail'}")
    if not criterion_2:
        return "BLOCKED", findings, "storyline_map.json does not satisfy release-gate criterion_2"

    claim_ledger = _state.claim_ledger.load(workspace) if _state.claim_ledger.exists(workspace) else None
    criterion_3 = True
    bad_claim = None
    if claim_ledger is None:
        criterion_3 = False
    else:
        for claim in claim_ledger.claims:
            if not claim.evidence_support and claim.unsupported_gaps:
                criterion_3 = False
                bad_claim = claim.claim_id
                break
    findings.append(
        "criterion_3=pass" if criterion_3 else f"criterion_3=fail: claim {bad_claim or 'unknown'} lacks evidence support"
    )
    if not criterion_3:
        return "BLOCKED", findings, "claim_ledger.json does not satisfy release-gate criterion_3"

    fmap = _state.figure_argument.load(workspace) if _state.figure_argument.exists(workspace) else None
    criterion_4 = fmap is not None
    bad_figure = None
    if fmap is not None:
        for figure in fmap.figures:
            if figure.claim_supported and not figure.panels and figure.status not in {"rendered", "final"}:
                criterion_4 = False
                bad_figure = figure.figure_id
                break
    findings.append(
        "criterion_4=pass" if criterion_4 else f"criterion_4=fail: figure {bad_figure or 'unknown'} lacks panels/status"
    )
    if not criterion_4:
        return "BLOCKED", findings, "figure_argument_map.json does not satisfy release-gate criterion_4"

    closed_rounds = [
        rd
        for num in _state.reviews.list_rounds(workspace)
        if (rd := _state.reviews.load_round(workspace, num)) is not None and rd.completed_at is not None
    ]
    criterion_5 = any(not rd.unresolved_fatal for rd in closed_rounds)
    findings.append(f"criterion_5={'pass' if criterion_5 else 'fail'}")
    if not criterion_5:
        return "BLOCKED", findings, "no closed review round satisfies release-gate criterion_5"

    pending_gates = _state.human_gates.pending(workspace)
    criterion_6 = not pending_gates
    findings.append(f"criterion_6={'pass' if criterion_6 else 'fail'}")
    if not criterion_6:
        return "HUMAN_GATE_REQUIRED", findings, "pending human gates remain open"

    latest_run = _state.runs.latest_run(workspace)
    latest_pdf = _paper_paths.pdf_output_path(workspace, latest_run) if latest_run else None
    criterion_7 = bool(latest_pdf and latest_pdf.exists() and latest_pdf.stat().st_size >= 10 * 1024)
    findings.append(f"criterion_7={'pass' if criterion_7 else 'fail'}")
    if not criterion_7:
        return "BLOCKED", findings, "latest compiled PDF does not satisfy release-gate criterion_7"

    return "DONE", findings, None


@_workspace_command
def cmd_framing(args: argparse.Namespace) -> int:
    workspace = _resolve_workspace(args.workspace)
    if not args.payload:
        return _missing_prereq(
            "framing requires --payload <storyline_map JSON> produced by paper-framing producer.",
            recommended_next_step="dispatch paper-framing producer + reviewer subagents",
        )
    try:
        payload = _read_payload(args.payload)
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        return _error(f"invalid framing payload: {exc}")
    return _persist_artifact(workspace, "storyline", payload)


@_workspace_command
def cmd_evidence(args: argparse.Namespace) -> int:
    workspace = _resolve_workspace(args.workspace)
    if not args.payload:
        return _missing_prereq("evidence requires --payload <evidence_backlog JSON>.")
    try:
        payload = _read_payload(args.payload)
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        return _error(f"invalid evidence payload: {exc}")
    return _persist_artifact(workspace, "evidence_backlog", payload)


@_workspace_command
def cmd_architecture(args: argparse.Namespace) -> int:
    workspace = _resolve_workspace(args.workspace)
    artifact = (args.artifact or "").strip()
    if artifact not in {"claim_ledger", "figure_argument_map"}:
        return _error(
            "architecture requires --artifact claim_ledger | figure_argument_map.",
        )
    if not args.payload:
        return _missing_prereq(f"architecture --artifact {artifact} requires --payload <JSON>.")
    try:
        payload = _read_payload(args.payload)
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        return _error(f"invalid architecture payload: {exc}")
    return _persist_artifact(workspace, artifact, payload)


@_workspace_command
def cmd_review(args: argparse.Namespace) -> int:
    workspace = _resolve_workspace(args.workspace)
    if not args.payload:
        return _missing_prereq("review requires --payload <Review JSON> | <ReviewRound JSON>.")
    try:
        payload = _read_payload(args.payload)
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        return _error(f"invalid review payload: {exc}")

    state = _state.paper_state.load(workspace)
    round_num = args.round if args.round is not None else max(state.round, 1)
    state = _mark_review_in_progress(workspace, state, round_num)

    if isinstance(payload, dict) and "reviews" in payload:
        try:
            rd = _models.ReviewRound.model_validate(payload)
        except Exception as exc:
            return _error(f"ReviewRound validation failed: {exc}")
        rd.round_num = round_num
        if rd.completed_at is None:
            rd.completed_at = datetime.utcnow()
        _state.reviews.save_round(workspace, rd)
        state.current_phase = _route_from_review_round(rd)
        if state.current_phase == _models.PaperPhase.release_gate:
            state.release_status = _models.ReleaseStatus.ready
            state.last_blocker = None
        else:
            state.release_status = _models.ReleaseStatus.in_review
            state.last_blocker = "latest review round requires rerouting"
        _state.paper_state.save(workspace, state)
        out_path = _paper_paths.review_round_path(workspace, round_num)
        return _ok(
            {
                "artifacts_written": [str(out_path)],
                "key_findings": [f"review_round_{round_num:03d} saved with {len(rd.reviews)} entries"],
            },
            round_num=round_num,
            path=str(out_path),
            current_phase=state.current_phase.value,
        )

    try:
        from agentsociety2.skills.paper.models import Review as _Review

        review = _Review.model_validate(payload)
    except Exception as exc:
        return _error(f"Review validation failed: {exc}")
    rd = _state.reviews.append_review(workspace, round_num, review)
    out_path = _paper_paths.review_round_path(workspace, round_num)
    return _ok(
        {
            "artifacts_written": [str(out_path)],
            "key_findings": [f"review appended to round {round_num}"],
        },
        round_num=round_num,
        path=str(out_path),
        reviewer=review.reviewer_profile,
        verdict=review.verdict,
        current_phase=state.current_phase.value,
    )


@_workspace_command
def cmd_human_gate_decide(args: argparse.Namespace) -> int:
    workspace = _resolve_workspace(args.workspace)
    gate_id = (args.gate_id or "").strip()
    if not gate_id:
        return _missing_prereq(
            "human-gate-decide requires --gate-id.",
            recommended_next_step="inspect pending gates via `paper-orchestrator status`",
        )

    decision = (args.decision or "").strip().lower()
    if decision not in {"accept", "reject", "modify"}:
        return _error("human-gate-decide requires --decision accept|reject|modify.")

    accepted_version = getattr(args, "accepted_version", None)
    note = getattr(args, "note", None)

    try:
        gate = _state.human_gates.decide(
            workspace,
            gate_id,
            decision,
            accepted_version=accepted_version,
            note=note,
        )
    except KeyError as exc:
        return _missing_prereq(
            str(exc),
            recommended_next_step="inspect current gate ids under paper/state/human_gates.yaml",
        )

    state = _state.paper_state.load(workspace)
    if decision in {"accept", "modify"}:
        next_phase = _phase_from_gate(gate)
        _state.paper_state.reset_phase(state, target=next_phase)
        state.release_status = _models.ReleaseStatus.in_review
        state.last_blocker = None
    else:
        state.release_status = _models.ReleaseStatus.blocked
        state.last_blocker = f"human gate {gate_id} was rejected"

    if state.pending_human_gate == gate_id and decision in {"accept", "modify"}:
        state.pending_human_gate = None

    _state.paper_state.save(workspace, state)
    return _ok(
        {
            "artifacts_written": [str(_paper_paths.human_gates_path(workspace))],
            "key_findings": [f"human gate {gate_id} decided as {decision}"],
            "recommended_next_step": _phase_recommended_next_step(state.current_phase),
        },
        gate_id=gate_id,
        decision=decision,
        current_phase=state.current_phase.value,
        release_status=state.release_status.value,
    )


@_workspace_command
def cmd_release(args: argparse.Namespace) -> int:
    workspace = _resolve_workspace(args.workspace)
    if not _state.paper_state.exists(workspace):
        return _missing_prereq(
            "paper_state.yaml missing; run intake first.",
            recommended_next_step="paper-orchestrator intake --workspace .",
        )

    state = _state.paper_state.load(workspace)
    if state.release_status != _models.ReleaseStatus.ready:
        return _missing_prereq(
            f"paper is not ready for release; current release_status={state.release_status.value}.",
            recommended_next_step="run `paper-orchestrator run-loop` until release-gate passes",
        )
    latest_round, latest_review = _latest_review_round(workspace)
    if latest_round == 0 or latest_review is None or latest_review.completed_at is None:
        return _missing_prereq(
            "release requires a completed latest review round.",
            recommended_next_step="close the latest review round before releasing",
        )
    if _state.human_gates.has_pending(workspace):
        state.release_status = _models.ReleaseStatus.blocked
        state.last_blocker = "pending human gates remain open"
        _state.paper_state.save(workspace, state)
        return _human_gate_required(
            "pending human gates remain open",
            recommended_next_step="resolve pending entries in human_gates.yaml before releasing",
        )

    state.release_status = _models.ReleaseStatus.released
    state.last_blocker = None
    _state.paper_state.save(workspace, state)
    return _ok(
        {
            "artifacts_written": [str(_paper_paths.paper_state_path(workspace))],
            "key_findings": ["paper release_status advanced to released"],
            "recommended_next_step": "paper has been marked released",
        },
        current_phase=state.current_phase.value,
        release_status=state.release_status.value,
    )


# ---------------------------------------------------------------------------
# Subcommand: compile
# ---------------------------------------------------------------------------


def _read_manuscript_section(workspace: Path, name: str) -> str:
    path = _paper_paths.manuscript_dir(workspace) / name
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def _iter_manuscript_result_files(workspace: Path) -> List[Path]:
    files: List[Path] = []
    seen: set[str] = set()

    results_dir = _paper_paths.manuscript_results_dir(workspace)
    if results_dir.exists():
        for entry in sorted(results_dir.iterdir()):
            if not entry.is_file() or entry.suffix != ".md":
                continue
            resolved = str(entry.resolve())
            if resolved in seen:
                continue
            seen.add(resolved)
            files.append(entry)

    # Backward-compatibility for early draft_section runs that wrote result
    # blocks directly under ``manuscript/`` as ``results_*.md``.
    manuscript_dir = _paper_paths.manuscript_dir(workspace)
    if manuscript_dir.exists():
        for entry in sorted(manuscript_dir.glob("results_*.md")):
            if not entry.is_file() or entry.suffix != ".md":
                continue
            resolved = str(entry.resolve())
            if resolved in seen:
                continue
            seen.add(resolved)
            files.append(entry)

    return files


def _read_manuscript_results(workspace: Path) -> str:
    chunks: List[str] = []
    for entry in _iter_manuscript_result_files(workspace):
        chunks.append(entry.read_text(encoding="utf-8"))
    return "\n\n".join(chunks)


def _normalize_manuscript_markdown(section: str, text: str) -> str:
    lines = (text or "").splitlines()
    while lines and not lines[0].strip():
        lines.pop(0)
    if not lines:
        return ""

    first = lines[0].strip()
    lowered = first.lstrip("#").strip().lower()
    expected_headings = {
        "abstract": {"abstract"},
        "discussion": {"discussion"},
        "main": {"main"},
        "results": {"results"},
    }
    if lowered in expected_headings.get(section, set()):
        lines = lines[1:]
        while lines and not lines[0].strip():
            lines.pop(0)
    return "\n".join(lines).strip()


def _extract_citation_keys(*texts: str) -> List[str]:
    keys: set[str] = set()
    for text in texts:
        for raw_keys in _RE_CITE.findall(text or ""):
            for key in raw_keys.split(","):
                cleaned = key.strip()
                if cleaned:
                    keys.add(cleaned)
    return sorted(keys)


def _invalid_citation_keys(workspace: Path, *texts: str) -> List[str]:
    used_keys = _extract_citation_keys(*texts)
    if not used_keys:
        return []
    if not _state.research_pack.exists(workspace):
        return []
    allowed = {
        entry.cite_key
        for entry in _state.research_pack.load(workspace).literature
        if entry.cite_key
    }
    return sorted(key for key in used_keys if key not in allowed)


def _extract_figure_ids(*texts: str) -> List[str]:
    figure_ids: set[str] = set()
    for text in texts:
        for raw in _RE_REF_FIG.findall(text or ""):
            cleaned = raw.strip()
            if cleaned:
                figure_ids.add(cleaned)
    return sorted(figure_ids)


def _load_compile_research_pack(workspace: Path) -> "_models.ResearchPack":
    if not _state.research_pack.exists(workspace):
        raise FileNotFoundError(
            "research_pack.json missing; run `paper-orchestrator build-pack` first."
        )
    pack = _state.research_pack.load(workspace)
    pack_workspace = Path(pack.workspace_path).expanduser().resolve()
    if pack_workspace != workspace:
        raise ValueError(
            "research_pack.json was built for a different workspace: "
            f"{pack_workspace}"
        )
    return pack


def _write_compile_bibliography(
    workspace: Path,
    timestamp: str,
    pack: "_models.ResearchPack",
) -> int:
    refs = [entry.bibtex for entry in pack.literature if entry.bibtex]
    return _bib_writer.write_bibtex_strings(
        _paper_paths.references_bib_path(workspace, timestamp),
        refs,
    )


def _validate_figures_for_compile(
    workspace: Path,
    figure_ids_in_text: List[str],
) -> List[str]:
    fmap = _state.figure_argument.load(workspace)
    if fmap is None:
        return []

    problems: List[str] = []
    by_id = {fig.figure_id: fig for fig in fmap.figures}

    for fig in fmap.figures:
        if fig.status in {"rendered", "final"} and not fig.file_path:
            problems.append(
                f"figure {fig.figure_id} is marked {fig.status} but has no file_path"
            )
        if fig.status in {"rendered", "final"} and not (fig.title or "").strip():
            problems.append(
                f"figure {fig.figure_id} is marked {fig.status} but has no title"
            )
        if fig.status in {"rendered", "final"} and not (fig.question_answered or "").strip():
            problems.append(
                f"figure {fig.figure_id} is marked {fig.status} but has no question_answered"
            )
        if fig.status in {"rendered", "final"} and not fig.panels:
            problems.append(
                f"figure {fig.figure_id} is marked {fig.status} but has no panels"
            )

    for figure_id in figure_ids_in_text:
        fig = by_id.get(figure_id)
        if fig is None:
            continue
        if not fig.file_path:
            problems.append(
                f"figure {figure_id} is referenced in manuscript but has no file_path"
            )

    deduped: List[str] = []
    seen: set[str] = set()
    for item in problems:
        if item in seen:
            continue
        seen.add(item)
        deduped.append(item)
    return deduped


def _copy_compose_artifact(src_path: Optional[str], dest_path: Path) -> Optional[str]:
    if not src_path:
        return None
    src = Path(src_path)
    if not src.exists():
        return None
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest_path)
    return str(dest_path)


def _stabilize_compile_outputs(
    workspace: Path,
    timestamp: str,
    result: "_models.CompileResult",
) -> "_models.CompileResult":
    alias_pdf = _copy_compose_artifact(
        result.pdf_path,
        _paper_paths.pdf_output_path(workspace, timestamp),
    )
    if alias_pdf:
        result.pdf_path = alias_pdf

    alias_log = _copy_compose_artifact(
        result.log_path,
        _paper_paths.pdf_log_path(workspace, timestamp),
    )
    if alias_log:
        result.log_path = alias_log

    return result


@_workspace_command
def cmd_compile(args: argparse.Namespace) -> int:
    workspace = _resolve_workspace(args.workspace)
    meta_path = _paper_paths.paper_meta_path(workspace)
    if not meta_path.exists():
        return _missing_prereq(
            "paper_meta.yaml missing; run `paper-orchestrator init-meta` first."
        )
    meta = _interactive_meta.load_meta(workspace)
    if not (meta.data_availability_url or "").strip():
        return _missing_prereq(
            "paper_meta.yaml missing data_availability_url.",
            recommended_next_step="populate paper_meta.yaml with a data availability statement or URL",
        )
    if not (meta.code_availability_url or "").strip():
        return _missing_prereq(
            "paper_meta.yaml missing code_availability_url.",
            recommended_next_step="populate paper_meta.yaml with a code availability statement or URL",
        )

    abstract_md = _read_manuscript_section(workspace, _paper_paths.MANUSCRIPT_ABSTRACT_FILENAME)
    main_md = _read_manuscript_section(workspace, _paper_paths.MANUSCRIPT_MAIN_FILENAME)
    discussion_md = _read_manuscript_section(workspace, _paper_paths.MANUSCRIPT_DISCUSSION_FILENAME)
    results_md = _read_manuscript_results(workspace)

    abstract_md = _normalize_manuscript_markdown("abstract", abstract_md)
    main_md = _normalize_manuscript_markdown("main", main_md)
    discussion_md = _normalize_manuscript_markdown("discussion", discussion_md)
    results_md = _normalize_manuscript_markdown("results", results_md)

    if not (abstract_md or main_md or results_md or discussion_md):
        return _missing_prereq(
            "no manuscript markdown found under <ws>/paper/artifacts/manuscript/.",
            recommended_next_step="dispatch paper-architecture draft_section subagent",
        )

    try:
        research_pack = _load_compile_research_pack(workspace)
    except FileNotFoundError as exc:
        return _missing_prereq(
            str(exc),
            recommended_next_step="paper-orchestrator build-pack --workspace .",
        )
    except ValueError as exc:
        return _missing_prereq(
            str(exc),
            recommended_next_step="re-run `paper-orchestrator build-pack` in the current workspace",
        )

    open_round_num, _ = _open_review_round(workspace)
    if open_round_num:
        return _missing_prereq(
            f"review_round_{open_round_num:03d} is still open.",
            recommended_next_step="close the latest review round before compiling a release candidate",
        )

    invalid_citations = _invalid_citation_keys(
        workspace,
        abstract_md,
        main_md,
        results_md,
        discussion_md,
    )
    if invalid_citations:
        invalid_preview = ", ".join(invalid_citations[:8])
        return _missing_prereq(
            f"unknown citation keys in manuscript: {invalid_preview}",
            recommended_next_step=(
                "replace [CITE:key] markers with cite_key values from "
                "paper/state/research_pack.json"
            ),
        )

    source_conflicts = _source_consistency_problems(
        research_pack,
        abstract_md,
        main_md,
        results_md,
        discussion_md,
    )
    if source_conflicts:
        return _missing_prereq(
            source_conflicts[0],
            recommended_next_step=(
                "revise the manuscript so the platform and intervention match paper/state/research_pack.json"
            ),
        )

    figure_ids_in_text = _extract_figure_ids(
        abstract_md,
        main_md,
        results_md,
        discussion_md,
    )
    figure_problems = _validate_figures_for_compile(workspace, figure_ids_in_text)
    if figure_problems:
        return _missing_prereq(
            figure_problems[0],
            recommended_next_step=(
                "update figure_argument_map with real file_path values for rendered figures"
            ),
        )

    abstract = _md_to_tex.md_to_tex(abstract_md)
    body_main = _md_to_tex.md_to_tex(main_md)
    body_results = _md_to_tex.md_to_tex(results_md)
    body_discussion = _md_to_tex.md_to_tex(discussion_md)

    timestamp = _paper_paths.make_timestamp()
    _, _ = _state.runs.open_run(workspace, timestamp=timestamp)
    compose_dir = _paper_paths.compose_dir(workspace, timestamp)
    compose_dir.mkdir(parents=True, exist_ok=True)

    written_refs = _write_compile_bibliography(workspace, timestamp, research_pack)
    if _extract_citation_keys(abstract_md, main_md, results_md, discussion_md) and written_refs == 0:
        return _missing_prereq(
            "manuscript contains citations, but research_pack literature is empty.",
            recommended_next_step="re-run `paper-orchestrator build-pack` after literature intake",
        )

    figures_block = ""
    fmap = _state.figure_argument.load(workspace)
    if fmap is not None and fmap.figures:
        _, figures_block = _figure_packer.pack_figures(
            list(fmap.figures), compose_dir, skip_missing=True
        )

    _latex_assembly.assemble_compose_tree(
        meta=meta,
        abstract=abstract,
        body_main=body_main,
        body_results=body_results,
        body_discussion=body_discussion,
        compose_dir=compose_dir,
        data_availability=meta.data_availability_url or "",
        code_availability=meta.code_availability_url or "",
        figures_block=figures_block,
    )

    try:
        result = _compiler.compile(compose_dir)
    except _compiler.CompileError as exc:
        env = _envelope.build_envelope(
            "BLOCKED",
            artifacts_written=[str(_paper_paths.main_tex_path(workspace, timestamp))],
            blocking_reason=str(exc),
            severity="fatal",
        )
        _state.runs.write_envelope(workspace, timestamp, env)
        _emit(
            {
                "success": False,
                "error": str(exc),
                "envelope": json.loads(_envelope.envelope_to_json(env)),
                "timestamp": timestamp,
            }
        )
        return 1

    result = _stabilize_compile_outputs(workspace, timestamp, result)

    artifacts_written = [
        str(_paper_paths.main_tex_path(workspace, timestamp)),
        str(_paper_paths.references_bib_path(workspace, timestamp)),
    ]
    if result.log_path:
        artifacts_written.append(result.log_path)
    if result.pdf_path:
        artifacts_written.append(result.pdf_path)

    if not result.success:
        env = _envelope.build_envelope(
            "BLOCKED",
            artifacts_written=artifacts_written,
            blocking_reason="latexmk failed; see log",
            severity="fatal",
            key_findings=result.errors[:5],
        )
        _state.runs.write_envelope(workspace, timestamp, env)
        _emit(
            {
                "success": False,
                "envelope": json.loads(_envelope.envelope_to_json(env)),
                "compile_result": result.model_dump(mode="json"),
                "timestamp": timestamp,
            }
        )
        return 1

    state = _state.paper_state.load(workspace)
    if state.current_phase == _models.PaperPhase.release_gate:
        state.release_status = _models.ReleaseStatus.ready
        state.last_blocker = None
    elif state.release_status == _models.ReleaseStatus.not_started:
        state.release_status = _models.ReleaseStatus.draft
    elif state.release_status == _models.ReleaseStatus.in_review:
        state.last_blocker = None
    _state.paper_state.save(workspace, state)

    env = _envelope.build_envelope(
        "DONE",
        artifacts_written=artifacts_written,
        key_findings=[
            f"pdf={result.pdf_path}",
            f"timestamp={timestamp}",
        ],
        recommended_next_step="advance to skeptical-review or release-gate",
    )
    _state.runs.write_envelope(workspace, timestamp, env)
    _emit(
        {
            "success": True,
            "envelope": json.loads(_envelope.envelope_to_json(env)),
            "compile_result": result.model_dump(mode="json"),
            "timestamp": timestamp,
        }
    )
    return 0


@_workspace_command
def cmd_run_loop(args: argparse.Namespace) -> int:
    workspace = _resolve_workspace(args.workspace)
    if not _paper_paths.paper_meta_path(workspace).exists():
        return _missing_prereq("paper_meta.yaml missing; run init-meta first.")

    if getattr(args, "max_rounds", 0) not in (None, 0):
        return _missing_prereq(
            "review-loop automation is not implemented in the CLI yet; max_rounds>0 is unsupported.",
            recommended_next_step="run `paper-orchestrator compile` for a smoke build, then drive review explicitly",
        )

    if not _state.paper_state.exists(workspace):
        _state.paper_state.initialize(workspace)

    if not _state.research_pack.exists(workspace):
        try:
            pack = _adapter_research_pack_builder.build_research_pack(workspace)
            _state.research_pack.save(workspace, pack)
        except Exception as exc:
            return _error(f"failed to build research pack: {exc}")
        st = _state.paper_state.load(workspace)
        if st.current_phase == _models.PaperPhase.intake:
            _state.paper_state.advance_phase(st, target=_models.PaperPhase.framing)
            _state.paper_state.save(workspace, st)
    else:
        try:
            _load_compile_research_pack(workspace)
        except ValueError as exc:
            return _missing_prereq(
                str(exc),
                recommended_next_step="re-run `paper-orchestrator build-pack` in the current workspace",
            )

    state = _state.paper_state.load(workspace)

    if state.current_phase == _models.PaperPhase.intake:
        return _missing_prereq(
            "paper is still in intake phase.",
            recommended_next_step="paper-orchestrator build-pack --workspace .",
        )

    if state.current_phase == _models.PaperPhase.framing:
        if not _state.storyline.exists(workspace):
            return _missing_prereq(
                "storyline_map.json missing for framing phase.",
                recommended_next_step=_phase_recommended_next_step(state.current_phase),
            )
        _state.paper_state.advance_phase(state, target=_models.PaperPhase.evidence_audit)
        _state.paper_state.save(workspace, state)

    if state.current_phase in {
        _models.PaperPhase.evidence_audit,
        _models.PaperPhase.expansion_plan,
    }:
        if not _state.evidence_backlog.exists(workspace):
            return _missing_prereq(
                "evidence_backlog.json missing for evidence planning.",
                recommended_next_step=_phase_recommended_next_step(state.current_phase),
            )
        if state.current_phase == _models.PaperPhase.evidence_audit:
            _state.paper_state.advance_phase(state, target=_models.PaperPhase.expansion_plan)
            _state.paper_state.save(workspace, state)
        state = _state.paper_state.load(workspace)

    if state.current_phase == _models.PaperPhase.manuscript_build:
        if not _state.claim_ledger.exists(workspace):
            return _missing_prereq(
                "claim_ledger.json missing for manuscript-build phase.",
                recommended_next_step=_phase_recommended_next_step(state.current_phase),
            )
        if not _state.figure_argument.exists(workspace):
            return _missing_prereq(
                "figure_argument_map.json missing for manuscript-build phase.",
                recommended_next_step=_phase_recommended_next_step(state.current_phase),
            )
        if not _manuscript_exists(workspace):
            return _missing_prereq(
                "manuscript markdown missing for manuscript-build phase.",
                recommended_next_step=_phase_recommended_next_step(state.current_phase),
            )
        return cmd_compile(args)

    if state.current_phase == _models.PaperPhase.skeptical_review:
        latest_round = _state.reviews.latest_round_num(workspace)
        if latest_round == 0:
            return _missing_prereq(
                "no review rounds recorded yet for skeptical-review phase.",
                recommended_next_step=_phase_recommended_next_step(state.current_phase),
            )
        review_round = _state.reviews.load_round(workspace, latest_round)
        if review_round is None or review_round.completed_at is None:
            return _missing_prereq(
                f"review_round_{latest_round:03d} is still open.",
                recommended_next_step="persist a completed ReviewRound payload via `paper-orchestrator review`",
            )
        state.current_phase = _route_from_review_round(review_round)
        _state.paper_state.save(workspace, state)
        state = _state.paper_state.load(workspace)

    if state.current_phase == _models.PaperPhase.revision_router:
        latest_round = _state.reviews.latest_round_num(workspace)
        if latest_round == 0:
            return _missing_prereq(
                "revision-router phase has no review round to route from.",
                recommended_next_step="persist a completed review round before rerouting",
            )
        review_round = _state.reviews.load_round(workspace, latest_round)
        if review_round is None:
            return _missing_prereq(
                f"review_round_{latest_round:03d} could not be loaded.",
                recommended_next_step="recreate the latest review round file",
            )
        next_phase, findings, gate_ids, dispatch_paths = _route_revision_round(workspace, state, review_round)
        if gate_ids:
            return _human_gate_required(
                "revision-router opened human gates for unresolved major issues.",
                recommended_next_step="review and decide the pending human gate entries",
                key_findings=findings,
                gate_ids=gate_ids,
                artifacts_written=dispatch_paths,
            )
        if next_phase is None:
            return _missing_prereq(
                "revision-router did not produce a next phase.",
                recommended_next_step=_phase_recommended_next_step(state.current_phase),
            )
        _state.paper_state.reset_phase(state, target=next_phase)
        if state.release_status == _models.ReleaseStatus.blocked:
            state.release_status = _models.ReleaseStatus.in_review
        state.pending_human_gate = None
        state.last_blocker = None
        _state.paper_state.save(workspace, state)
        return _ok(
            {
                "artifacts_read": [
                    str(_paper_paths.paper_state_path(workspace)),
                    str(_paper_paths.review_round_path(workspace, latest_round)),
                ],
                "artifacts_written": dispatch_paths,
                "key_findings": findings,
                "recommended_next_step": _phase_recommended_next_step(next_phase),
            },
            current_phase=state.current_phase.value,
            round_num=latest_round,
        )

    if state.current_phase == _models.PaperPhase.release_gate:
        latest_run = _state.runs.latest_run(workspace)
        latest_pdf = _paper_paths.pdf_output_path(workspace, latest_run) if latest_run else None
        if latest_pdf is None or not latest_pdf.exists():
            compile_rc = cmd_compile(args)
            if compile_rc != 0:
                return compile_rc
        verdict, findings, blocker = _release_gate_verdict(workspace)
        if verdict == "DONE":
            state.release_status = _models.ReleaseStatus.ready
            state.last_blocker = None
            state.pending_human_gate = None
            _state.paper_state.save(workspace, state)
            return _ok(
                {
                    "artifacts_read": [str(_paper_paths.paper_state_path(workspace))],
                    "key_findings": findings,
                    "recommended_next_step": "paper is ready for serious human review",
                },
                current_phase=state.current_phase.value,
            )
        if verdict == "HUMAN_GATE_REQUIRED":
            state.release_status = _models.ReleaseStatus.blocked
            state.last_blocker = blocker
            _state.paper_state.save(workspace, state)
            return _human_gate_required(
                blocker or "release-gate requires human decision",
                recommended_next_step="resolve pending entries in human_gates.yaml",
                key_findings=findings,
            )
        state.release_status = _models.ReleaseStatus.blocked
        state.last_blocker = blocker
        _state.paper_state.save(workspace, state)
        return _missing_prereq(
            blocker or "release-gate criteria not met",
            recommended_next_step="route back through revision-router after fixing the failed criterion",
            key_findings=findings,
        )

    return _missing_prereq(
        f"unsupported run-loop phase: {state.current_phase.value}",
        recommended_next_step=_phase_recommended_next_step(state.current_phase),
    )


@_workspace_command
def cmd_status(args: argparse.Namespace) -> int:
    workspace = _resolve_workspace(args.workspace)
    if not _state.paper_state.exists(workspace):
        return _missing_prereq("paper_state.yaml missing; run intake first.")

    state = _state.paper_state.load(workspace)
    artifacts: Dict[str, bool] = {
        "research_pack.json": _state.research_pack.exists(workspace),
        "storyline_map.json": _state.storyline.exists(workspace),
        "claim_ledger.json": _state.claim_ledger.exists(workspace),
        "evidence_backlog.json": _state.evidence_backlog.exists(workspace),
        "figure_argument_map.json": _state.figure_argument.exists(workspace),
    }
    rounds = _state.reviews.list_rounds(workspace)
    runs = _state.runs.list_runs(workspace)
    pending_gates = _state.human_gates.pending(workspace)

    return _ok(
        {
            "artifacts_read": [str(_paper_paths.paper_state_path(workspace))],
            "key_findings": [
                f"phase={state.current_phase.value}",
                f"release_status={state.release_status.value}",
                f"reviews={len(rounds)}",
                f"runs={len(runs)}",
                f"pending_human_gates={len(pending_gates)}",
            ],
        },
        state=state.model_dump(mode="json"),
        artifacts=artifacts,
        review_rounds=rounds,
        runs=runs,
        pending_human_gates=[gate.model_dump(mode="json") for gate in pending_gates],
    )


# ---------------------------------------------------------------------------
# Argparse glue
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="paper-orchestrator",
        description="Paper-orchestrator CLI (Phase 3 of the paper-skill replacement)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    def _add_workspace(p: argparse.ArgumentParser) -> None:
        p.add_argument(
            "--workspace",
            default=".",
            help="Workspace root containing TOPIC.md, hypothesis_*/, ...",
        )

    p_init = sub.add_parser("init-meta", help="Write paper_meta.yaml from JSON args.")
    _add_workspace(p_init)
    p_init.add_argument("--payload", help="JSON object or path to JSON file with title/authors/affils.")
    p_init.set_defaults(func=cmd_init_meta)

    p_intake = sub.add_parser("intake", help="Initialize <ws>/paper/ tree and state machine.")
    _add_workspace(p_intake)
    p_intake.set_defaults(func=cmd_intake)

    p_pack = sub.add_parser("build-pack", help="Run paper-adapter -> research_pack.json.")
    _add_workspace(p_pack)
    p_pack.add_argument(
        "--research-objective",
        help="Optional override for ResearchPack.research_objective.",
    )
    p_pack.set_defaults(func=cmd_build_pack)

    p_framing = sub.add_parser("framing", help="Persist a storyline_map produced by paper-framing.")
    _add_workspace(p_framing)
    p_framing.add_argument("--payload", help="storyline_map JSON | JSON file.")
    p_framing.set_defaults(func=cmd_framing)

    p_evidence = sub.add_parser("evidence", help="Persist an evidence_backlog produced by paper-evidence-expansion.")
    _add_workspace(p_evidence)
    p_evidence.add_argument("--payload", help="evidence_backlog JSON | JSON file.")
    p_evidence.set_defaults(func=cmd_evidence)

    p_arch = sub.add_parser("architecture", help="Persist claim_ledger or figure_argument_map.")
    _add_workspace(p_arch)
    p_arch.add_argument(
        "--artifact",
        choices=["claim_ledger", "figure_argument_map"],
        required=True,
    )
    p_arch.add_argument("--payload", help="JSON | JSON file.")
    p_arch.set_defaults(func=cmd_architecture)

    p_review = sub.add_parser("review", help="Append a Review entry (or full ReviewRound) to a round.")
    _add_workspace(p_review)
    p_review.add_argument("--payload", help="Review or ReviewRound JSON.")
    p_review.add_argument("--round", type=int, default=None, help="Round number (defaults to current).")
    p_review.set_defaults(func=cmd_review)

    p_gate = sub.add_parser(
        "human-gate-decide",
        help="Record a decision for a pending human gate and route state forward.",
    )
    _add_workspace(p_gate)
    p_gate.add_argument("--gate-id", required=True, help="Gate id from paper/state/human_gates.yaml.")
    p_gate.add_argument("--decision", required=True, help="accept | reject | modify")
    p_gate.add_argument(
        "--accepted-version",
        help="Optional phase value to resume from after accept/modify, e.g. framing or manuscript-build.",
    )
    p_gate.add_argument("--note", help="Optional decision note.")
    p_gate.set_defaults(func=cmd_human_gate_decide)

    p_compile = sub.add_parser("compile", help="Build LaTeX and run latexmk -> paper.pdf.")
    _add_workspace(p_compile)
    p_compile.set_defaults(func=cmd_compile)

    p_run = sub.add_parser("run-loop", help="Smoke pipeline: adapter -> compose -> compile (no review).")
    _add_workspace(p_run)
    p_run.add_argument(
        "--max-rounds",
        type=int,
        default=0,
        help="Phase 3: 0 = no review loop. Phase 4 will honour higher values.",
    )
    p_run.set_defaults(func=cmd_run_loop)

    p_status = sub.add_parser("status", help="Dump paper_state + artifact summary.")
    _add_workspace(p_status)
    p_status.set_defaults(func=cmd_status)

    p_release = sub.add_parser("release", help="Mark a ready paper as released.")
    _add_workspace(p_release)
    p_release.set_defaults(func=cmd_release)

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    _ensure_paper_imports()
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except SystemExit:
        raise
    except Exception as exc:
        return _error(
            f"unhandled error: {exc}",
            traceback=traceback.format_exc(),
        )


if __name__ == "__main__":
    raise SystemExit(main())
