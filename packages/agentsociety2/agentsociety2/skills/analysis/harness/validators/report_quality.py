from __future__ import annotations

import re
from pathlib import Path
from typing import List, Optional

from agentsociety2.skills.analysis.harness.json_io import load_model_from_file
from agentsociety2.skills.analysis.harness.models import ClaimMode, ValidationResult
from agentsociety2.skills.analysis.harness.schemas import AnalysisSummary
from agentsociety2.skills.analysis.harness.state import load_claims
from agentsociety2.skills.analysis.harness.validators._helpers import (
    blocked,
    issue,
    passed,
)

MIN_REPORT_WORDS = 25
MIN_LIMITATIONS_CHARS = 8
MIN_SECTION_HEADERS = 3
MIN_KEY_FINDING_CHARS = 12

FLUFF_PATTERNS = (
    re.compile(r"有趣的模式|interesting patterns?", re.I),
    re.compile(r"结果(表明|显示).{0,12}(显著|明显)(?!.*\d)", re.I),
    re.compile(r"further research is needed", re.I),
    re.compile(r"呈现出(一定|较为)?(的)?(多样|复杂|丰富)", re.I),
)

FIGURE_LINE_RE = re.compile(r"!\[[^\]]*\]\(assets/([^)]+)\)")
SECTION_RE = re.compile(r"^##\s+.+", re.M)


def _word_count(text: str) -> int:
    tokens = re.findall(r"[\w\u4e00-\u9fff]+", text)
    return len(tokens)


def _figure_refs(text: str) -> List[str]:
    return FIGURE_LINE_RE.findall(text)


def _caption_lines_after_figures(text: str) -> List[bool]:
    lines = text.splitlines()
    ok: List[bool] = []
    for i, line in enumerate(lines):
        if FIGURE_LINE_RE.search(line):
            next_line = lines[i + 1].strip() if i + 1 < len(lines) else ""
            ok.append(len(next_line) >= 4 and not FIGURE_LINE_RE.search(next_line))
    return ok


def validate_report_quality(
    presentation_dir: Path,
    *,
    workspace: Optional[Path] = None,
    hypothesis_id: Optional[str] = None,
) -> ValidationResult:
    issues: List = []
    report_zh = presentation_dir / "report_zh.md"
    report_en = presentation_dir / "report_en.md"
    html_zh = presentation_dir / "report_zh.html"
    html_en = presentation_dir / "report_en.html"
    summary_path = presentation_dir / "data" / "analysis_summary.json"

    missing = [
        label
        for path, label in (
            (report_zh, "report_zh.md"),
            (report_en, "report_en.md"),
            (html_zh, "report_zh.html"),
            (html_en, "report_en.html"),
        )
        if not path.exists() or not path.read_text(encoding="utf-8").strip()
    ]
    if missing:
        issues.append(
            issue(
                "report_quality_missing_files",
                phase="produce",
                message=f"Bilingual MD + HTML required before quality check: {', '.join(missing)}",
                fix_hint="Write all four report files (see references/html-export.md)",
            )
        )
        return blocked(issues)

    zh_text = report_zh.read_text(encoding="utf-8")
    en_text = report_en.read_text(encoding="utf-8")

    for path, text, label in (
        (report_zh, zh_text, "report_zh.md"),
        (report_en, en_text, "report_en.md"),
    ):
        wc = _word_count(text)
        if wc < MIN_REPORT_WORDS:
            issues.append(
                issue(
                    "report_too_short",
                    phase="produce",
                    message=f"{label} has only ~{wc} words (minimum {MIN_REPORT_WORDS})",
                    fix_hint="Expand narrative sections; see references/analysis-quality.md",
                )
            )
        if len(SECTION_RE.findall(text)) < MIN_SECTION_HEADERS:
            issues.append(
                issue(
                    "report_sections_sparse",
                    phase="produce",
                    message=f"{label} needs at least {MIN_SECTION_HEADERS} `##` sections",
                    fix_hint="Use overview, data, findings, conclusions structure",
                )
            )
        for pat in FLUFF_PATTERNS:
            if pat.search(text):
                issues.append(
                    issue(
                        "report_fluff_phrase",
                        phase="produce",
                        message=f"{label} contains generic filler matching {pat.pattern!r}",
                        fix_hint="Replace with specific metrics, tables, or claim-backed statements",
                    )
                )
        captions = _caption_lines_after_figures(text)
        if captions and not all(captions):
            issues.append(
                issue(
                    "figure_caption_missing",
                    phase="produce",
                    message=f"{label}: every `![](assets/...)` needs a one-line caption below",
                    fix_hint="See checklists/quality.md",
                )
            )

    zh_figs = set(_figure_refs(zh_text))
    en_figs = set(_figure_refs(en_text))
    if zh_figs != en_figs:
        issues.append(
            issue(
                "bilingual_figure_mismatch",
                phase="produce",
                message="Chinese and English reports reference different asset sets",
                fix_hint="Mirror figure embeds across report_zh.md and report_en.md",
            )
        )

    if summary_path.exists():
        try:
            summary = load_model_from_file(summary_path, AnalysisSummary)
            if len((summary.limitations or "").strip()) < MIN_LIMITATIONS_CHARS:
                issues.append(
                    issue(
                        "limitations_too_short",
                        phase="produce",
                        message="analysis_summary.json limitations field is empty or trivial",
                        fix_hint="State simulation external-validity caveats explicitly",
                    )
                )
            weak = [
                f
                for f in summary.key_findings
                if len(str(f).strip()) < MIN_KEY_FINDING_CHARS
            ]
            if not summary.key_findings or weak:
                issues.append(
                    issue(
                        "key_findings_weak",
                        phase="produce",
                        message="analysis_summary.json key_findings must be substantive bullets",
                        fix_hint="Each finding should be a testable sentence with evidence",
                    )
                )
        except ValueError as exc:
            issues.append(
                issue(
                    "analysis_summary_invalid",
                    phase="produce",
                    message=str(exc),
                )
            )

    if workspace and hypothesis_id:
        claims_doc = load_claims(workspace, hypothesis_id)
        confirmatory = [
            c for c in claims_doc.claims if c.mode == ClaimMode.confirmatory
        ]
        for claim in confirmatory[:8]:
            needle = (claim.statement or claim.claim_id or "").strip()
            if needle and needle[:12] not in zh_text and claim.claim_id not in zh_text:
                issues.append(
                    issue(
                        "confirmatory_claim_not_in_report",
                        phase="produce",
                        message=f"Confirmatory claim not reflected in report_zh.md: {claim.claim_id or needle[:40]}",
                        fix_hint="Add a findings subsection per claim; see claims.json",
                    )
                )

    if issues:
        return blocked(
            issues,
            recommended_next_step="Revise reports with report-producer, then re-run validate-report-quality",
        )
    return passed()
