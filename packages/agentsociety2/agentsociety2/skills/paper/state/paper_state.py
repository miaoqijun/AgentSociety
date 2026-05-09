"""CRUD + phase-machine helpers for ``state/paper_state.yaml``."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

import yaml

from agentsociety2.skills.paper.models import PaperPhase, PaperState, ReleaseStatus
from agentsociety2.skills.paper.paths import (
    PathLike,
    paper_state_path,
    state_dir,
)

PHASE_ORDER: tuple[PaperPhase, ...] = (
    PaperPhase.intake,
    PaperPhase.framing,
    PaperPhase.evidence_audit,
    PaperPhase.expansion_plan,
    PaperPhase.manuscript_build,
    PaperPhase.skeptical_review,
    PaperPhase.revision_router,
    PaperPhase.release_gate,
)


def load(workspace_path: PathLike) -> PaperState:
    """Load PaperState from disk; return defaults if absent."""

    path = paper_state_path(workspace_path)
    if not path.exists():
        return PaperState()
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return PaperState.model_validate(raw)


def save(workspace_path: PathLike, state: PaperState) -> None:
    """Persist ``state`` to ``<ws>/paper/state/paper_state.yaml``."""

    state.updated_at = datetime.utcnow()
    state_dir(workspace_path).mkdir(parents=True, exist_ok=True)
    path = paper_state_path(workspace_path)
    payload = state.model_dump(mode="json")
    path.write_text(
        yaml.safe_dump(payload, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )


def exists(workspace_path: PathLike) -> bool:
    """Return True if the canonical init sentinel exists."""

    return paper_state_path(workspace_path).exists()


def initialize(
    workspace_path: PathLike,
    *,
    overwrite: bool = False,
) -> PaperState:
    """Create the initial paper_state.yaml if missing.

    Idempotent: returns the existing state untouched when one is on disk
    unless ``overwrite=True``.
    """

    if exists(workspace_path) and not overwrite:
        return load(workspace_path)
    state = PaperState()
    save(workspace_path, state)
    return state


def advance_phase(state: PaperState, *, target: Optional[PaperPhase] = None) -> PaperState:
    """Advance ``state.current_phase`` forward.

    With no target, moves to the next phase in ``PHASE_ORDER``.  With an
    explicit target, validates that the move is forward (or stays put) and
    raises :class:`ValueError` for backward jumps - phase regression must
    go through an explicit reset to keep state machine guarantees.
    """

    current = state.current_phase
    if target is None:
        idx = PHASE_ORDER.index(current)
        if idx + 1 >= len(PHASE_ORDER):
            return state  # already at terminal phase
        state.current_phase = PHASE_ORDER[idx + 1]
        return state

    if target == current:
        return state
    if PHASE_ORDER.index(target) < PHASE_ORDER.index(current):
        raise ValueError(
            f"advance_phase: cannot move backward from {current.value} to {target.value}; "
            "use reset_phase explicitly."
        )
    state.current_phase = target
    return state


def reset_phase(state: PaperState, target: PaperPhase) -> PaperState:
    """Force-set the phase regardless of direction. Use sparingly."""

    state.current_phase = target
    return state


def begin_round(state: PaperState) -> PaperState:
    """Increment the review round counter and reset per-round caps."""

    state.round += 1
    state.counters.figure_regenerations = 0
    state.counters.citation_augmentations = 0
    return state


def set_release_status(state: PaperState, status: ReleaseStatus) -> PaperState:
    state.release_status = status
    return state


def is_terminal(state: PaperState) -> bool:
    """True once release_status is ``ready`` or ``released``."""

    return state.release_status in (ReleaseStatus.ready, ReleaseStatus.released)


__all__ = [
    "PHASE_ORDER",
    "advance_phase",
    "begin_round",
    "exists",
    "initialize",
    "is_terminal",
    "load",
    "reset_phase",
    "save",
    "set_release_status",
]
