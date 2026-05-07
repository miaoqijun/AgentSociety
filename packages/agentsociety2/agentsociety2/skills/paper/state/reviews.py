"""Append-only review-round logs at ``reviews/review_round_NNN.yaml``.

The orchestrator opens a new round file on every cycle, accumulates
reviewer entries inside it, then closes the round when revisions land.
The router consults :func:`route_for` to map a verdict onto an action.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

import yaml

from agentsociety2.skills.paper.models import Review, ReviewRound, Verdict
from agentsociety2.skills.paper.paths import (
    PathLike,
    review_round_path,
    reviews_dir,
)


# Verdict -> orchestrator routing target (high-level).  ``None`` means the
# orchestrator should leave the artifact alone (verdict=accept) or escalate
# (verdict=fatal -> human gate).
VERDICT_ROUTING: dict[Verdict, Optional[str]] = {
    "accept": None,
    "revise_local": "wording",
    "revise_structural": "section",
    "pivot_conceptual": "framing",
    "pivot_major": "human_gate",
    "fatal": "human_gate",
}


def round_path(workspace_path: PathLike, round_num: int):
    return review_round_path(workspace_path, round_num)


def load_round(workspace_path: PathLike, round_num: int) -> Optional[ReviewRound]:
    """Load a specific review round file. Returns None if absent."""

    path = review_round_path(workspace_path, round_num)
    if not path.exists():
        return None
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return ReviewRound.model_validate(raw)


def save_round(workspace_path: PathLike, review_round: ReviewRound) -> None:
    """Persist (or overwrite) a single round file."""

    reviews_dir(workspace_path).mkdir(parents=True, exist_ok=True)
    path = review_round_path(workspace_path, review_round.round_num)
    payload = review_round.model_dump(mode="json")
    path.write_text(
        yaml.safe_dump(payload, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )


def open_round(workspace_path: PathLike, round_num: int) -> ReviewRound:
    """Create a new empty round on disk if not yet present."""

    existing = load_round(workspace_path, round_num)
    if existing is not None:
        return existing
    new_round = ReviewRound(round_num=round_num)
    save_round(workspace_path, new_round)
    return new_round


def append_review(
    workspace_path: PathLike,
    round_num: int,
    review: Review,
) -> ReviewRound:
    """Append a reviewer entry to the round (creating the round if needed)."""

    rd = load_round(workspace_path, round_num) or ReviewRound(round_num=round_num)
    rd.reviews.append(review)
    if review.severity == "fatal" and review.resolved_state != "resolved":
        marker = f"{review.reviewer_profile}:{review.target_artifact}:{review.issue_type}"
        if marker and marker not in rd.unresolved_fatal:
            rd.unresolved_fatal.append(marker)
    save_round(workspace_path, rd)
    return rd


def close_round(workspace_path: PathLike, round_num: int) -> ReviewRound:
    """Mark a round as completed (sets ``completed_at``)."""

    rd = load_round(workspace_path, round_num)
    if rd is None:
        raise FileNotFoundError(f"review_round_{round_num:03d}.yaml not found")
    rd.completed_at = datetime.utcnow()
    save_round(workspace_path, rd)
    return rd


def list_rounds(workspace_path: PathLike) -> List[int]:
    """Return all round numbers found on disk, sorted ascending."""

    directory = reviews_dir(workspace_path)
    if not directory.exists():
        return []
    nums: list[int] = []
    for entry in sorted(directory.iterdir()):
        if not entry.is_file():
            continue
        if not entry.name.startswith("review_round_") or not entry.name.endswith(".yaml"):
            continue
        try:
            num_str = entry.stem.removeprefix("review_round_")
            nums.append(int(num_str))
        except ValueError:
            continue
    return sorted(nums)


def latest_round_num(workspace_path: PathLike) -> int:
    """Return the highest round number on disk, or 0 if none exist."""

    nums = list_rounds(workspace_path)
    return nums[-1] if nums else 0


def route_for(verdict: Verdict) -> Optional[str]:
    """Map a verdict to the orchestrator's routing target keyword.

    Returns ``None`` for ``accept`` (no action). The human-gate routing
    is signaled with the literal ``"human_gate"`` so the caller can branch
    cleanly without importing internal enum types.
    """

    return VERDICT_ROUTING.get(verdict)


def unresolved_fatal_count(review_round: ReviewRound) -> int:
    return len(review_round.unresolved_fatal)


__all__ = [
    "VERDICT_ROUTING",
    "round_path",
    "load_round",
    "save_round",
    "open_round",
    "append_review",
    "close_round",
    "list_rounds",
    "latest_round_num",
    "route_for",
    "unresolved_fatal_count",
]
