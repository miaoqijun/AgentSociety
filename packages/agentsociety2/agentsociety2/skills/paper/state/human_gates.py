"""Human-gate queue at ``state/human_gates.yaml``.

The queue is a list of :class:`HumanGate` records.  Decisions are recorded
in-place (``user_decision``, ``decided_at``, ``accepted_version``).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import List, Optional

import yaml

from agentsociety2.skills.paper.models import HumanDecision, HumanGate, HumanGateSeverity
from agentsociety2.skills.paper.paths import (
    PathLike,
    human_gates_path,
    state_dir,
)


def _read_raw(workspace_path: PathLike) -> List[dict]:
    path = human_gates_path(workspace_path)
    if not path.exists():
        return []
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if isinstance(payload, list):
        return payload
    return list(payload.get("gates", []) or [])


def _write_raw(workspace_path: PathLike, gates: List[dict]) -> None:
    state_dir(workspace_path).mkdir(parents=True, exist_ok=True)
    human_gates_path(workspace_path).write_text(
        yaml.safe_dump({"gates": gates}, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )


def load_all(workspace_path: PathLike) -> List[HumanGate]:
    return [HumanGate.model_validate(item) for item in _read_raw(workspace_path)]


def save_all(workspace_path: PathLike, gates: List[HumanGate]) -> None:
    _write_raw(workspace_path, [g.model_dump(mode="json") for g in gates])


def open_gate(
    workspace_path: PathLike,
    *,
    triggering_issue: str,
    proposed_pivot: str = "",
    severity: HumanGateSeverity = "moderate",
    rationale: str = "",
    note: Optional[str] = None,
    gate_id: Optional[str] = None,
) -> HumanGate:
    """Append a new pending gate.  Returns the persisted :class:`HumanGate`."""

    gate = HumanGate(
        gate_id=gate_id or f"gate-{uuid.uuid4().hex[:8]}",
        triggering_issue=triggering_issue,
        proposed_pivot=proposed_pivot,
        severity=severity,
        rationale=rationale,
        note=note,
    )
    gates = load_all(workspace_path)
    gates.append(gate)
    save_all(workspace_path, gates)
    return gate


def get(workspace_path: PathLike, gate_id: str) -> Optional[HumanGate]:
    for gate in load_all(workspace_path):
        if gate.gate_id == gate_id:
            return gate
    return None


def decide(
    workspace_path: PathLike,
    gate_id: str,
    decision: HumanDecision,
    *,
    accepted_version: Optional[str] = None,
    note: Optional[str] = None,
) -> HumanGate:
    """Record a user decision on an existing gate."""

    gates = load_all(workspace_path)
    for idx, gate in enumerate(gates):
        if gate.gate_id != gate_id:
            continue
        gate.user_decision = decision
        gate.accepted_version = accepted_version
        gate.decided_at = datetime.utcnow()
        if note is not None:
            gate.note = note
        gates[idx] = gate
        save_all(workspace_path, gates)
        return gate
    raise KeyError(f"human gate not found: {gate_id}")


def pending(workspace_path: PathLike) -> List[HumanGate]:
    return [g for g in load_all(workspace_path) if g.user_decision is None]


def has_pending(workspace_path: PathLike) -> bool:
    return any(g.user_decision is None for g in load_all(workspace_path))


__all__ = [
    "load_all",
    "save_all",
    "open_gate",
    "get",
    "decide",
    "pending",
    "has_pending",
]
