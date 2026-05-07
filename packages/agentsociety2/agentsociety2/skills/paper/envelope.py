"""Skill envelope schema + helpers.

Every paper-skill subagent dispatched by ``paper-orchestrator`` returns a
common envelope (per harness design §"Unified Skill Return Contract").  The
envelope schema itself lives in :mod:`agentsociety2.skills.paper.models`
under :class:`Envelope`; this module re-exports it as
:class:`SkillEnvelope` and provides build / parse helpers used by the CLI
and orchestrator scripts.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Union

from agentsociety2.skills.paper.models import (
    Envelope,
    EnvelopeStatus,
    Severity,
)

# Re-export under a more skill-centric name; the schema is the same.
SkillEnvelope = Envelope


def build_envelope(
    status: EnvelopeStatus,
    *,
    artifacts_read: Optional[List[str]] = None,
    artifacts_written: Optional[List[str]] = None,
    key_findings: Optional[List[str]] = None,
    blocking_reason: Optional[str] = None,
    recommended_next_step: Optional[str] = None,
    severity: Optional[Severity] = None,
) -> Envelope:
    """Construct a :class:`SkillEnvelope` with sensible list defaults."""

    return Envelope(
        status=status,
        artifacts_read=list(artifacts_read or []),
        artifacts_written=list(artifacts_written or []),
        key_findings=list(key_findings or []),
        blocking_reason=blocking_reason,
        recommended_next_step=recommended_next_step,
        severity=severity,
    )


def parse_envelope(payload: Union[str, bytes, Dict[str, Any]]) -> Envelope:
    """Parse an envelope from a JSON string, bytes, or pre-decoded dict."""

    if isinstance(payload, (bytes, bytearray)):
        payload = payload.decode("utf-8")
    if isinstance(payload, str):
        return Envelope.model_validate_json(payload)
    return Envelope.model_validate(payload)


def envelope_to_json(envelope: Envelope, *, indent: Optional[int] = None) -> str:
    """Serialize ``envelope`` to a JSON string (UTF-8 safe)."""

    return json.dumps(
        envelope.model_dump(mode="json", exclude_none=False),
        ensure_ascii=False,
        indent=indent,
    )


__all__ = [
    "SkillEnvelope",
    "Envelope",
    "EnvelopeStatus",
    "Severity",
    "build_envelope",
    "parse_envelope",
    "envelope_to_json",
]
