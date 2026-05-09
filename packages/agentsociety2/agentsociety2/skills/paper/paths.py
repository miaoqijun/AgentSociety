"""Single source of truth for paper-skill workspace paths.

All other modules in :mod:`agentsociety2.skills.paper` import path helpers
from here so that the on-disk layout described in the M1 plan is consistent
across producer, reviewer, adapter, and orchestrator code.

Workspace layout::

    <workspace>/paper/
        paper_meta.yaml
        state/
            research_pack.json
            paper_state.yaml
            human_gates.yaml
        artifacts/
            storyline_map.{md,json}
            claim_ledger.{md,json}
            evidence_backlog.{md,json}
            figure_argument_map.{md,json}
            manuscript/
                abstract.md
                main.md
                results/01_*.md ...
                discussion.md
        reviews/
            review_round_001.yaml ...
        runs/
            <YYYYMMDD_HHMMSS>/
                envelope.json
                dispatch_*.json
                compose/
                    main.tex
                    references.bib
                    Figure/<id>.<ext>
                    out/paper.pdf
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Union

PathLike = Union[str, Path]

PAPER_DIR_NAME = "paper"
STATE_DIR_NAME = "state"
ARTIFACTS_DIR_NAME = "artifacts"
REVIEWS_DIR_NAME = "reviews"
RUNS_DIR_NAME = "runs"
MANUSCRIPT_DIR_NAME = "manuscript"
RESULTS_DIR_NAME = "results"
COMPOSE_DIR_NAME = "compose"
FIGURE_DIR_NAME = "Figure"
OUT_DIR_NAME = "out"

PAPER_META_FILENAME = "paper_meta.yaml"
PAPER_STATE_FILENAME = "paper_state.yaml"
RESEARCH_PACK_FILENAME = "research_pack.json"
HUMAN_GATES_FILENAME = "human_gates.yaml"

STORYLINE_MD_FILENAME = "storyline_map.md"
STORYLINE_JSON_FILENAME = "storyline_map.json"
CLAIM_LEDGER_MD_FILENAME = "claim_ledger.md"
CLAIM_LEDGER_JSON_FILENAME = "claim_ledger.json"
EVIDENCE_BACKLOG_MD_FILENAME = "evidence_backlog.md"
EVIDENCE_BACKLOG_JSON_FILENAME = "evidence_backlog.json"
FIGURE_ARGUMENT_MD_FILENAME = "figure_argument_map.md"
FIGURE_ARGUMENT_JSON_FILENAME = "figure_argument_map.json"

MANUSCRIPT_ABSTRACT_FILENAME = "abstract.md"
MANUSCRIPT_MAIN_FILENAME = "main.md"
MANUSCRIPT_DISCUSSION_FILENAME = "discussion.md"

ENVELOPE_FILENAME = "envelope.json"
PDF_FILENAME = "paper.pdf"
PDF_LOG_FILENAME = "paper.log"
MAIN_TEX_FILENAME = "main.tex"
REFERENCES_BIB_FILENAME = "references.bib"

TIMESTAMP_FORMAT = "%Y%m%d_%H%M%S"


def _resolve_workspace(workspace_path: PathLike) -> Path:
    return Path(workspace_path).expanduser().resolve()


def paper_root(workspace_path: PathLike) -> Path:
    """Return ``<workspace>/paper``."""

    return _resolve_workspace(workspace_path) / PAPER_DIR_NAME


def paper_meta_path(workspace_path: PathLike) -> Path:
    """Un-namespaced user identity file (title/authors/affils/...)."""

    return paper_root(workspace_path) / PAPER_META_FILENAME


# --- state/ ----------------------------------------------------------------


def state_dir(workspace_path: PathLike) -> Path:
    return paper_root(workspace_path) / STATE_DIR_NAME


def paper_state_path(workspace_path: PathLike) -> Path:
    return state_dir(workspace_path) / PAPER_STATE_FILENAME


def research_pack_path(workspace_path: PathLike) -> Path:
    return state_dir(workspace_path) / RESEARCH_PACK_FILENAME


def human_gates_path(workspace_path: PathLike) -> Path:
    return state_dir(workspace_path) / HUMAN_GATES_FILENAME


# --- artifacts/ ------------------------------------------------------------


def artifacts_dir(workspace_path: PathLike) -> Path:
    return paper_root(workspace_path) / ARTIFACTS_DIR_NAME


def storyline_md_path(workspace_path: PathLike) -> Path:
    return artifacts_dir(workspace_path) / STORYLINE_MD_FILENAME


def storyline_json_path(workspace_path: PathLike) -> Path:
    return artifacts_dir(workspace_path) / STORYLINE_JSON_FILENAME


def claim_ledger_md_path(workspace_path: PathLike) -> Path:
    return artifacts_dir(workspace_path) / CLAIM_LEDGER_MD_FILENAME


def claim_ledger_json_path(workspace_path: PathLike) -> Path:
    return artifacts_dir(workspace_path) / CLAIM_LEDGER_JSON_FILENAME


def evidence_backlog_md_path(workspace_path: PathLike) -> Path:
    return artifacts_dir(workspace_path) / EVIDENCE_BACKLOG_MD_FILENAME


def evidence_backlog_json_path(workspace_path: PathLike) -> Path:
    return artifacts_dir(workspace_path) / EVIDENCE_BACKLOG_JSON_FILENAME


def figure_argument_md_path(workspace_path: PathLike) -> Path:
    return artifacts_dir(workspace_path) / FIGURE_ARGUMENT_MD_FILENAME


def figure_argument_json_path(workspace_path: PathLike) -> Path:
    return artifacts_dir(workspace_path) / FIGURE_ARGUMENT_JSON_FILENAME


def manuscript_dir(workspace_path: PathLike) -> Path:
    return artifacts_dir(workspace_path) / MANUSCRIPT_DIR_NAME


def manuscript_abstract_path(workspace_path: PathLike) -> Path:
    return manuscript_dir(workspace_path) / MANUSCRIPT_ABSTRACT_FILENAME


def manuscript_main_path(workspace_path: PathLike) -> Path:
    return manuscript_dir(workspace_path) / MANUSCRIPT_MAIN_FILENAME


def manuscript_discussion_path(workspace_path: PathLike) -> Path:
    return manuscript_dir(workspace_path) / MANUSCRIPT_DISCUSSION_FILENAME


def manuscript_results_dir(workspace_path: PathLike) -> Path:
    return manuscript_dir(workspace_path) / RESULTS_DIR_NAME


# --- reviews/ --------------------------------------------------------------


def reviews_dir(workspace_path: PathLike) -> Path:
    return paper_root(workspace_path) / REVIEWS_DIR_NAME


def review_round_path(workspace_path: PathLike, round_num: int) -> Path:
    """Return ``<workspace>/paper/reviews/review_round_NNN.yaml``."""

    return reviews_dir(workspace_path) / f"review_round_{round_num:03d}.yaml"


# --- runs/<TS>/ ------------------------------------------------------------


def runs_dir(workspace_path: PathLike) -> Path:
    return paper_root(workspace_path) / RUNS_DIR_NAME


def run_dir(workspace_path: PathLike, timestamp: str) -> Path:
    return runs_dir(workspace_path) / timestamp


def envelope_path(workspace_path: PathLike, timestamp: str) -> Path:
    return run_dir(workspace_path, timestamp) / ENVELOPE_FILENAME


def dispatch_record_path(
    workspace_path: PathLike, timestamp: str, dispatch_num: int
) -> Path:
    return run_dir(workspace_path, timestamp) / f"dispatch_{dispatch_num:03d}.json"


def compose_dir(workspace_path: PathLike, timestamp: str) -> Path:
    return run_dir(workspace_path, timestamp) / COMPOSE_DIR_NAME


def out_dir(workspace_path: PathLike, timestamp: str) -> Path:
    return compose_dir(workspace_path, timestamp) / OUT_DIR_NAME


def figure_dir(workspace_path: PathLike, timestamp: str) -> Path:
    return compose_dir(workspace_path, timestamp) / FIGURE_DIR_NAME


def main_tex_path(workspace_path: PathLike, timestamp: str) -> Path:
    return compose_dir(workspace_path, timestamp) / MAIN_TEX_FILENAME


def references_bib_path(workspace_path: PathLike, timestamp: str) -> Path:
    return compose_dir(workspace_path, timestamp) / REFERENCES_BIB_FILENAME


def pdf_output_path(workspace_path: PathLike, timestamp: str) -> Path:
    return out_dir(workspace_path, timestamp) / PDF_FILENAME


def pdf_log_path(workspace_path: PathLike, timestamp: str) -> Path:
    return out_dir(workspace_path, timestamp) / PDF_LOG_FILENAME


# --- skill-packaged templates ----------------------------------------------


def templates_dir() -> Path:
    """Return the skill-packaged ``templates`` directory."""

    return Path(__file__).resolve().parent / "templates"


def nature_template_dir() -> Path:
    return templates_dir() / "nature"


# --- helpers ---------------------------------------------------------------


def make_timestamp(now: datetime | None = None) -> str:
    """Generate a run-folder timestamp ``YYYYMMDD_HHMMSS``.

    ``now`` is injectable for deterministic tests.
    """

    return (now or datetime.now()).strftime(TIMESTAMP_FORMAT)


__all__ = [
    "ARTIFACTS_DIR_NAME",
    "CLAIM_LEDGER_JSON_FILENAME",
    "CLAIM_LEDGER_MD_FILENAME",
    "COMPOSE_DIR_NAME",
    "ENVELOPE_FILENAME",
    "EVIDENCE_BACKLOG_JSON_FILENAME",
    "EVIDENCE_BACKLOG_MD_FILENAME",
    "FIGURE_ARGUMENT_JSON_FILENAME",
    "FIGURE_ARGUMENT_MD_FILENAME",
    "FIGURE_DIR_NAME",
    "HUMAN_GATES_FILENAME",
    "MAIN_TEX_FILENAME",
    "MANUSCRIPT_ABSTRACT_FILENAME",
    "MANUSCRIPT_DIR_NAME",
    "MANUSCRIPT_DISCUSSION_FILENAME",
    "MANUSCRIPT_MAIN_FILENAME",
    "OUT_DIR_NAME",
    "PAPER_DIR_NAME",
    "PAPER_META_FILENAME",
    "PAPER_STATE_FILENAME",
    "PDF_FILENAME",
    "PDF_LOG_FILENAME",
    "REFERENCES_BIB_FILENAME",
    "RESEARCH_PACK_FILENAME",
    "RESULTS_DIR_NAME",
    "REVIEWS_DIR_NAME",
    "RUNS_DIR_NAME",
    "STATE_DIR_NAME",
    "STORYLINE_JSON_FILENAME",
    "STORYLINE_MD_FILENAME",
    "TIMESTAMP_FORMAT",
    "PathLike",
    "artifacts_dir",
    "claim_ledger_json_path",
    "claim_ledger_md_path",
    "compose_dir",
    "dispatch_record_path",
    "envelope_path",
    "evidence_backlog_json_path",
    "evidence_backlog_md_path",
    "figure_argument_json_path",
    "figure_argument_md_path",
    "figure_dir",
    "human_gates_path",
    "main_tex_path",
    "make_timestamp",
    "manuscript_abstract_path",
    "manuscript_dir",
    "manuscript_discussion_path",
    "manuscript_main_path",
    "manuscript_results_dir",
    "nature_template_dir",
    "out_dir",
    "paper_meta_path",
    "paper_root",
    "paper_state_path",
    "pdf_log_path",
    "pdf_output_path",
    "references_bib_path",
    "research_pack_path",
    "review_round_path",
    "reviews_dir",
    "run_dir",
    "runs_dir",
    "state_dir",
    "storyline_json_path",
    "storyline_md_path",
    "templates_dir",
]
