"""Workspace -> :class:`ResearchPack` ingestion.

This is the single place that knows the AgentSociety workspace layout
(``TOPIC.md``, ``hypothesis_*/HYPOTHESIS.md``, ``hypothesis_*/experiment_*/EXPERIMENT.md``,
``presentation/hypothesis_*/{report*.md,data/analysis_summary.json,assets/*}``,
``synthesis/synthesis_report_*.md``, ``papers/literature_index.json``).

The function :func:`build_research_pack` is the generalized successor of
the legacy ``gather_workspace_paper_context``: it walks the workspace,
collects evidence, derives BibTeX-ready literature entries, and emits a
:class:`ResearchPack` plus :class:`ProvenanceEntry` records flagging
where each datum came from.  Confidence flags are conservative: ``high``
when the file exists and is non-empty; ``low`` when missing.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, List, Optional

from agentsociety2.skills.paper.adapter.bib_writer import build_reference_strings
from agentsociety2.skills.paper.adapter.summary import (
    collect_figure_paths_under,
    extract_heading,
    format_title_from_filename,
    read_text_safe,
    sanitize_bibtex_key,
    summarize_analysis_result_json,
    trim_text,
)
from agentsociety2.skills.paper.models import (
    Confidence,
    ProvenanceEntry,
    ResearchPack,
    ResearchPackAnalysis,
    ResearchPackExperiment,
    ResearchPackFigure,
    ResearchPackHypothesis,
    ResearchPackLiterature,
)


def _confidence(present_and_nonempty: bool) -> Confidence:
    return "high" if present_and_nonempty else "low"


def _discover_hypotheses(workspace: Path) -> List[str]:
    ids: List[str] = []
    for entry in sorted(workspace.iterdir()) if workspace.is_dir() else []:
        if not entry.is_dir():
            continue
        if entry.name.startswith("hypothesis_") and entry.name[len("hypothesis_"):].isdigit():
            ids.append(entry.name[len("hypothesis_"):])
    return ids


def _discover_experiments(hypothesis_dir: Path) -> List[str]:
    ids: List[str] = []
    if not hypothesis_dir.is_dir():
        return ids
    for entry in sorted(hypothesis_dir.iterdir()):
        if not entry.is_dir():
            continue
        if entry.name.startswith("experiment_") and entry.name[len("experiment_"):].isdigit():
            ids.append(entry.name[len("experiment_"):])
    return ids


def _read_first_existing(paths: Iterable[Path]) -> tuple[str, Optional[Path]]:
    """Return ``(text, source_path)`` for the first path that yields content."""

    for path in paths:
        text = read_text_safe(path)
        if text:
            return text, path
    return "", None


def _literature_to_models(
    entries: List[dict],
) -> List[ResearchPackLiterature]:
    """Convert raw literature_index entries to ResearchPackLiterature objects.

    Cite keys are derived with :func:`sanitize_bibtex_key` so they match
    what :func:`build_reference_strings` would emit, ensuring ``[CITE:key]``
    references in producer-emitted markdown resolve cleanly.
    """

    valid_entries: List[dict] = []
    for entry in entries:
        title = (entry.get("title") or "").strip()
        if not title:
            continue
        valid_entries.append(entry)

    bibtex_strings = build_reference_strings(valid_entries, limit=None)
    out: List[ResearchPackLiterature] = []
    for idx, (entry, bibtex) in enumerate(zip(valid_entries, bibtex_strings)):
        title = (entry.get("title") or "").strip()
        extra = entry.get("extra_fields") or {}
        year = extra.get("year") or entry.get("year") or ""
        if isinstance(year, (int, float)):
            year = str(int(year))
        authors = extra.get("authors") or entry.get("authors") or ""
        if isinstance(authors, list):
            authors = " and ".join(str(a) for a in authors)
        key = sanitize_bibtex_key(title, idx, year=str(year))
        out.append(
            ResearchPackLiterature(
                cite_key=key,
                title=title,
                authors=str(authors),
                year=str(year),
                doi=(entry.get("doi") or "").strip(),
                journal=(entry.get("journal") or "").strip(),
                bibtex=bibtex,
            )
        )
    return out


def build_research_pack(
    workspace_path: Path | str,
    *,
    research_objective: Optional[str] = None,
) -> ResearchPack:
    """Walk the workspace tree and assemble a :class:`ResearchPack`.

    ``research_objective`` is optional metadata supplied by the orchestrator
    intake stage; when omitted the topic file's first heading is used.
    """

    workspace = Path(workspace_path).expanduser().resolve()
    provenance: List[ProvenanceEntry] = []

    # --- Topic ---
    topic_path = workspace / "TOPIC.md"
    topic_text = read_text_safe(topic_path)
    objective = research_objective or extract_heading(topic_text) or ""
    provenance.append(
        ProvenanceEntry(
            artifact_id="topic",
            source_path=str(topic_path),
            confidence=_confidence(bool(topic_text)),
        )
    )

    # --- Hypotheses + experiments ---
    hypotheses: List[ResearchPackHypothesis] = []
    experiments: List[ResearchPackExperiment] = []
    analyses: List[ResearchPackAnalysis] = []
    figures: List[ResearchPackFigure] = []

    for hid in _discover_hypotheses(workspace):
        h_dir = workspace / f"hypothesis_{hid}"
        h_md_path = h_dir / "HYPOTHESIS.md"
        h_text = trim_text(read_text_safe(h_md_path), 4000)

        exp_ids = _discover_experiments(h_dir)
        for eid in exp_ids:
            exp_path = h_dir / f"experiment_{eid}" / "EXPERIMENT.md"
            exp_text = trim_text(read_text_safe(exp_path), 4000)
            experiments.append(
                ResearchPackExperiment(
                    experiment_id=eid,
                    hypothesis_id=hid,
                    design=exp_text,
                    confidence=_confidence(bool(exp_text)),
                )
            )
            provenance.append(
                ProvenanceEntry(
                    artifact_id=f"experiment:{hid}.{eid}",
                    source_path=str(exp_path),
                    confidence=_confidence(bool(exp_text)),
                )
            )

        hypotheses.append(
            ResearchPackHypothesis(
                hypothesis_id=hid,
                text=h_text,
                experiments=exp_ids,
                confidence=_confidence(bool(h_text)),
            )
        )
        provenance.append(
            ProvenanceEntry(
                artifact_id=f"hypothesis:{hid}",
                source_path=str(h_md_path),
                confidence=_confidence(bool(h_text)),
            )
        )

        # --- Per-hypothesis presentation report + analysis JSON ---
        pres_dir = workspace / "presentation" / f"hypothesis_{hid}"
        report_text, report_path = _read_first_existing(
            [
                pres_dir / "report_zh.md",
                pres_dir / "report.md",
                pres_dir / "report_en.md",
            ]
        )
        analysis_json_path = pres_dir / "data" / "analysis_summary.json"
        analysis_json_raw = read_text_safe(analysis_json_path)
        analysis_summary = trim_text(
            summarize_analysis_result_json(analysis_json_raw), 4000
        )

        if report_text or analysis_json_raw:
            raw_payload: Optional[dict] = None
            if analysis_json_raw:
                try:
                    raw_payload = json.loads(analysis_json_raw)
                    if not isinstance(raw_payload, dict):
                        raw_payload = None
                except json.JSONDecodeError:
                    raw_payload = None
            analyses.append(
                ResearchPackAnalysis(
                    analysis_id=f"hp{hid}_summary",
                    hypothesis_id=hid,
                    summary="\n\n".join(
                        block
                        for block in [trim_text(report_text, 6000), analysis_summary]
                        if block
                    ),
                    raw_json=raw_payload,
                )
            )
            provenance.append(
                ProvenanceEntry(
                    artifact_id=f"analysis:{hid}",
                    source_path=str(report_path or analysis_json_path),
                    confidence=_confidence(bool(report_text or analysis_json_raw)),
                )
            )

        # --- Figures (presentation/<hid>/assets) ---
        for fig_path in collect_figure_paths_under(pres_dir / "assets"):
            fpath = Path(fig_path)
            figure_id = f"hp{hid}_{fpath.stem}"
            figures.append(
                ResearchPackFigure(
                    figure_id=figure_id,
                    file_path=str(fpath),
                    source=str(fpath.relative_to(workspace))
                    if fpath.is_relative_to(workspace)
                    else str(fpath),
                    caption_hint=format_title_from_filename(fpath),
                )
            )
            provenance.append(
                ProvenanceEntry(
                    artifact_id=f"figure:{figure_id}",
                    source_path=str(fpath),
                    confidence="high",
                )
            )

    # --- Cross-hypothesis synthesis ---
    synth_dir = workspace / "synthesis"
    synth_text, synth_path = _read_first_existing(
        [
            synth_dir / "synthesis_report_zh.md",
            synth_dir / "synthesis_report_en.md",
            synth_dir / "synthesis_report.md",
        ]
    )
    if synth_text:
        provenance.append(
            ProvenanceEntry(
                artifact_id="synthesis",
                source_path=str(synth_path),
                confidence="high",
            )
        )

    for fig_path in collect_figure_paths_under(synth_dir / "assets"):
        fpath = Path(fig_path)
        figure_id = f"synth_{fpath.stem}"
        figures.append(
            ResearchPackFigure(
                figure_id=figure_id,
                file_path=str(fpath),
                source=str(fpath.relative_to(workspace))
                if fpath.is_relative_to(workspace)
                else str(fpath),
                caption_hint=format_title_from_filename(fpath),
            )
        )
        provenance.append(
            ProvenanceEntry(
                artifact_id=f"figure:{figure_id}",
                source_path=str(fpath),
                confidence="high",
            )
        )

    # --- Literature index ---
    literature: List[ResearchPackLiterature] = []
    lit_path = workspace / "papers" / "literature_index.json"
    if lit_path.exists():
        try:
            data = json.loads(lit_path.read_text(encoding="utf-8"))
            entries = data.get("entries") if isinstance(data, dict) else None
            if isinstance(entries, list):
                literature = _literature_to_models(entries)
        except (json.JSONDecodeError, OSError):
            literature = []
        provenance.append(
            ProvenanceEntry(
                artifact_id="literature_index",
                source_path=str(lit_path),
                confidence=_confidence(bool(literature)),
            )
        )

    return ResearchPack(
        workspace_path=str(workspace),
        topic=topic_text,
        research_objective=objective,
        hypotheses=hypotheses,
        experiments=experiments,
        analyses=analyses,
        figures=figures,
        literature=literature,
        synthesis_report=synth_text,
        provenance=provenance,
    )


# Legacy alias used by the orchestrator subagent prompt.
gather_workspace_paper_context = build_research_pack


__all__ = [
    "build_research_pack",
    "gather_workspace_paper_context",
]
