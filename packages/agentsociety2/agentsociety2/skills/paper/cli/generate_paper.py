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


# ---------------------------------------------------------------------------
# Path / workspace helpers
# ---------------------------------------------------------------------------


def _resolve_workspace(raw: str) -> Path:
    return Path(raw).expanduser().resolve()


def _read_payload(raw: str) -> Any:
    candidate = Path(raw).expanduser()
    if candidate.exists():
        return json.loads(candidate.read_text(encoding="utf-8"))
    return json.loads(raw)


# ---------------------------------------------------------------------------
# Subcommand: init-meta
# ---------------------------------------------------------------------------


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
    except Exception as exc:  # noqa: BLE001
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
    except Exception as exc:  # noqa: BLE001
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


def cmd_evidence(args: argparse.Namespace) -> int:
    workspace = _resolve_workspace(args.workspace)
    if not args.payload:
        return _missing_prereq("evidence requires --payload <evidence_backlog JSON>.")
    try:
        payload = _read_payload(args.payload)
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        return _error(f"invalid evidence payload: {exc}")
    return _persist_artifact(workspace, "evidence_backlog", payload)


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

    if isinstance(payload, dict) and "reviews" in payload:
        try:
            rd = _models.ReviewRound.model_validate(payload)
        except Exception as exc:  # noqa: BLE001
            return _error(f"ReviewRound validation failed: {exc}")
        rd.round_num = round_num
        _state.reviews.save_round(workspace, rd)
        out_path = _paper_paths.review_round_path(workspace, round_num)
        return _ok(
            {
                "artifacts_written": [str(out_path)],
                "key_findings": [f"review_round_{round_num:03d} saved with {len(rd.reviews)} entries"],
            },
            round_num=round_num,
            path=str(out_path),
        )

    try:
        from agentsociety2.skills.paper.models import Review as _Review

        review = _Review.model_validate(payload)
    except Exception as exc:  # noqa: BLE001
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


def cmd_compile(args: argparse.Namespace) -> int:
    workspace = _resolve_workspace(args.workspace)
    meta_path = _paper_paths.paper_meta_path(workspace)
    if not meta_path.exists():
        return _missing_prereq(
            "paper_meta.yaml missing; run `paper-orchestrator init-meta` first."
        )
    meta = _interactive_meta.load_meta(workspace)

    abstract_md = _read_manuscript_section(workspace, _paper_paths.MANUSCRIPT_ABSTRACT_FILENAME)
    main_md = _read_manuscript_section(workspace, _paper_paths.MANUSCRIPT_MAIN_FILENAME)
    discussion_md = _read_manuscript_section(workspace, _paper_paths.MANUSCRIPT_DISCUSSION_FILENAME)
    results_md = _read_manuscript_results(workspace)

    if not (abstract_md or main_md or results_md or discussion_md):
        return _missing_prereq(
            "no manuscript markdown found under <ws>/paper/artifacts/manuscript/.",
            recommended_next_step="dispatch paper-architecture draft_section subagent",
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

    abstract = _md_to_tex.md_to_tex(abstract_md)
    body_main = _md_to_tex.md_to_tex(main_md)
    body_results = _md_to_tex.md_to_tex(results_md)
    body_discussion = _md_to_tex.md_to_tex(discussion_md)

    timestamp = _paper_paths.make_timestamp()
    _, _ = _state.runs.open_run(workspace, timestamp=timestamp)
    compose_dir = _paper_paths.compose_dir(workspace, timestamp)
    compose_dir.mkdir(parents=True, exist_ok=True)

    lit_path = workspace / "papers" / "literature_index.json"
    _bib_writer.write_bibtex_file(
        lit_path,
        _paper_paths.references_bib_path(workspace, timestamp),
        limit=None,
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
    if state.release_status == _models.ReleaseStatus.not_started:
        state.release_status = _models.ReleaseStatus.draft
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


def cmd_run_loop(args: argparse.Namespace) -> int:
    workspace = _resolve_workspace(args.workspace)
    if not _paper_paths.paper_meta_path(workspace).exists():
        return _missing_prereq("paper_meta.yaml missing; run init-meta first.")

    if not _state.paper_state.exists(workspace):
        _state.paper_state.initialize(workspace)

    if not _state.research_pack.exists(workspace):
        try:
            pack = _adapter_research_pack_builder.build_research_pack(workspace)
            _state.research_pack.save(workspace, pack)
        except Exception as exc:  # noqa: BLE001
            return _error(f"failed to build research pack: {exc}")
        st = _state.paper_state.load(workspace)
        if st.current_phase == _models.PaperPhase.intake:
            _state.paper_state.advance_phase(st, target=_models.PaperPhase.framing)
            _state.paper_state.save(workspace, st)

    return cmd_compile(args)


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

    return _ok(
        {
            "artifacts_read": [str(_paper_paths.paper_state_path(workspace))],
            "key_findings": [
                f"phase={state.current_phase.value}",
                f"release_status={state.release_status.value}",
                f"reviews={len(rounds)}",
                f"runs={len(runs)}",
            ],
        },
        state=state.model_dump(mode="json"),
        artifacts=artifacts,
        review_rounds=rounds,
        runs=runs,
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

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    _ensure_paper_imports()
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001 - top-level guard
        return _error(
            f"unhandled error: {exc}",
            traceback=traceback.format_exc(),
        )


if __name__ == "__main__":
    raise SystemExit(main())
