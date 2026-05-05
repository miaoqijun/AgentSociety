"""CRUD for ``artifacts/claim_ledger.{md,json}``."""

from __future__ import annotations

import json
from typing import List, Optional

from agentsociety2.skills.paper.models import Claim, ClaimLedger
from agentsociety2.skills.paper.paths import (
    PathLike,
    artifacts_dir,
    claim_ledger_json_path,
    claim_ledger_md_path,
)


def load(workspace_path: PathLike) -> Optional[ClaimLedger]:
    """Return None if the ledger has not been written yet."""

    path = claim_ledger_json_path(workspace_path)
    if not path.exists():
        return None
    raw = json.loads(path.read_text(encoding="utf-8"))
    return ClaimLedger.model_validate(raw)


def save(workspace_path: PathLike, ledger: ClaimLedger) -> None:
    artifacts_dir(workspace_path).mkdir(parents=True, exist_ok=True)
    claim_ledger_json_path(workspace_path).write_text(
        json.dumps(ledger.model_dump(mode="json"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    claim_ledger_md_path(workspace_path).write_text(
        render_markdown(ledger),
        encoding="utf-8",
    )


def render_markdown(ledger: ClaimLedger) -> str:
    lines: list[str] = ["# Claim Ledger", ""]
    if not ledger.claims:
        lines.append("_No claims recorded yet._")
        return "\n".join(lines) + "\n"
    for claim in ledger.claims:
        lines.append(f"## {claim.claim_id}: {claim.claim_text}")
        lines.append(
            f"- **type**: {claim.claim_type} | **wording strength**: {claim.allowed_wording_strength}"
        )
        if claim.evidence_support:
            lines.append("- **evidence**: " + ", ".join(claim.evidence_support))
        if claim.linked_figures:
            lines.append("- **linked figures**: " + ", ".join(claim.linked_figures))
        if claim.unsupported_gaps:
            lines.append("- **unsupported gaps**:")
            for gap in claim.unsupported_gaps:
                lines.append(f"  - {gap}")
        if claim.reviewer_objections:
            lines.append("- **reviewer objections**:")
            for note in claim.reviewer_objections:
                lines.append(f"  - {note}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def unsupported_claims(ledger: ClaimLedger) -> List[Claim]:
    """Return claims whose evidence support is empty or that have explicit gaps."""

    return [
        claim
        for claim in ledger.claims
        if not claim.evidence_support or claim.unsupported_gaps
    ]


def exists(workspace_path: PathLike) -> bool:
    return claim_ledger_json_path(workspace_path).exists()


__all__ = [
    "load",
    "save",
    "render_markdown",
    "unsupported_claims",
    "exists",
]
