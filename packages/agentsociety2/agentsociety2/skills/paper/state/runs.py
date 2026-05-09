"""Per-run record management under ``runs/<TS>/``.

Each invocation of the orchestrator (or sub-skill called via ``ags``) opens
a timestamped run directory.  Inside it:

- ``envelope.json`` - the final returned envelope from the run
- ``dispatch_<NNN>.json`` - one record per dispatched subagent

This module provides the path/CRUD helpers; counters relevant to a run
live on :class:`PaperState`, not on disk per-run.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from agentsociety2.skills.paper.models import DispatchRecord, Envelope
from agentsociety2.skills.paper.paths import (
    PathLike,
    dispatch_record_path,
    envelope_path,
    make_timestamp,
    run_dir,
    runs_dir,
)


def open_run(
    workspace_path: PathLike, *, timestamp: Optional[str] = None
) -> tuple[str, Path]:
    """Create a fresh ``runs/<TS>/`` directory and return ``(timestamp, path)``."""

    base_ts = timestamp or make_timestamp()
    ts = base_ts
    rd = run_dir(workspace_path, ts)
    suffix = 1
    while rd.exists():
        ts = f"{base_ts}_{suffix:02d}"
        rd = run_dir(workspace_path, ts)
        suffix += 1
    rd.mkdir(parents=True, exist_ok=False)
    return ts, rd


def list_runs(workspace_path: PathLike) -> List[str]:
    """Return run timestamps (sorted ascending) under ``<ws>/paper/runs/``."""

    directory = runs_dir(workspace_path)
    if not directory.exists():
        return []
    return sorted(
        d.name for d in directory.iterdir() if d.is_dir()
    )


def latest_run(workspace_path: PathLike) -> Optional[str]:
    runs = list_runs(workspace_path)
    return runs[-1] if runs else None


def write_envelope(
    workspace_path: PathLike, timestamp: str, envelope: Envelope
) -> Path:
    """Persist the run-final envelope as JSON."""

    path = envelope_path(workspace_path, timestamp)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(envelope.model_dump(mode="json"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path


def read_envelope(workspace_path: PathLike, timestamp: str) -> Optional[Envelope]:
    path = envelope_path(workspace_path, timestamp)
    if not path.exists():
        return None
    return Envelope.model_validate_json(path.read_text(encoding="utf-8"))


def append_dispatch(
    workspace_path: PathLike,
    timestamp: str,
    record: DispatchRecord,
) -> Path:
    """Persist a single dispatch record under ``runs/<TS>/dispatch_<NNN>.json``.

    ``record.dispatch_num`` controls the filename; the caller assigns it
    (typically via :func:`next_dispatch_num`).
    """

    path = dispatch_record_path(workspace_path, timestamp, record.dispatch_num)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(record.model_dump(mode="json"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path


def list_dispatches(
    workspace_path: PathLike, timestamp: str
) -> List[DispatchRecord]:
    """Return all dispatch records in a run, sorted by dispatch_num."""

    rd = run_dir(workspace_path, timestamp)
    if not rd.exists():
        return []
    records: list[DispatchRecord] = []
    for entry in sorted(rd.iterdir()):
        if not entry.is_file():
            continue
        if not entry.name.startswith("dispatch_") or not entry.name.endswith(".json"):
            continue
        records.append(
            DispatchRecord.model_validate_json(entry.read_text(encoding="utf-8"))
        )
    records.sort(key=lambda r: r.dispatch_num)
    return records


def next_dispatch_num(workspace_path: PathLike, timestamp: str) -> int:
    """Return the next dispatch number to use (1-based)."""

    existing = list_dispatches(workspace_path, timestamp)
    if not existing:
        return 1
    return existing[-1].dispatch_num + 1


def new_dispatch(
    workspace_path: PathLike,
    timestamp: str,
    *,
    target_skill: str,
    target_subagent: Optional[str] = None,
    notes: Optional[str] = None,
) -> DispatchRecord:
    """Create + persist a fresh dispatch record in ``pending`` state."""

    record = DispatchRecord(
        dispatch_num=next_dispatch_num(workspace_path, timestamp),
        target_skill=target_skill,
        target_subagent=target_subagent,
        notes=notes,
    )
    append_dispatch(workspace_path, timestamp, record)
    return record


def complete_dispatch(
    workspace_path: PathLike,
    timestamp: str,
    record: DispatchRecord,
    *,
    envelope: Optional[Envelope] = None,
    failed: bool = False,
) -> DispatchRecord:
    """Mark an existing dispatch as completed/failed and persist updates."""

    record.completed_at = datetime.utcnow()
    record.status = "failed" if failed else "completed"
    if envelope is not None:
        record.envelope = envelope
    append_dispatch(workspace_path, timestamp, record)
    return record


__all__ = [
    "append_dispatch",
    "complete_dispatch",
    "latest_run",
    "list_dispatches",
    "list_runs",
    "new_dispatch",
    "next_dispatch_num",
    "open_run",
    "read_envelope",
    "write_envelope",
]
