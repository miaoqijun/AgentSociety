from __future__ import annotations

from pathlib import Path
from typing import List

from agentsociety2.skills.analysis.harness.json_io import load_model_from_file
from agentsociety2.skills.analysis.harness.schemas import SynthesisBrief
from agentsociety2.skills.analysis.harness.validators._helpers import (
    blocked,
    issue,
    passed,
)


def _load_brief(path: Path) -> tuple[SynthesisBrief | None, List]:
    if not path.exists():
        return None, [
            issue(
                "synthesis_brief_missing",
                phase="synthesis",
                message="synthesis/synthesis_brief.json not found",
                fix_hint="See references/json-payloads.md for synthesis_brief template",
            )
        ]
    try:
        return load_model_from_file(path, SynthesisBrief), []
    except ValueError as exc:
        return None, [
            issue(
                "synthesis_brief_invalid",
                phase="synthesis",
                message=str(exc),
            )
        ]


def validate_synthesis(
    workspace: Path,
    *,
    synthesis_dir: Path,
    scope_hypothesis_ids: List[str],
    max_synthesis_charts: int = 0,
) -> "ValidationResult":
    issues: List = []
    report_zh = synthesis_dir / "synthesis_report_zh.md"
    report_en = synthesis_dir / "synthesis_report_en.md"
    brief_path = synthesis_dir / "synthesis_brief.json"

    for path, label in (
        (report_zh, "synthesis_report_zh.md"),
        (report_en, "synthesis_report_en.md"),
        (synthesis_dir / "synthesis_report_zh.html", "synthesis_report_zh.html"),
        (synthesis_dir / "synthesis_report_en.html", "synthesis_report_en.html"),
    ):
        if not path.exists() or not path.read_text(encoding="utf-8").strip():
            issues.append(
                issue(
                    "synthesis_report_missing",
                    phase="synthesis",
                    message=f"{label} missing or empty",
                    fix_hint="LLM writes bilingual synthesis MD + HTML (see html-export.md)",
                )
            )
        elif path.suffix.lower() == ".html":
            lower = path.read_text(encoding="utf-8").lower()
            if "<html" not in lower and "<!doctype" not in lower:
                issues.append(
                    issue(
                        "synthesis_report_html_invalid",
                        phase="synthesis",
                        message=f"{label} is not a complete HTML document",
                        fix_hint="Author synthesis HTML mirroring MD structure",
                    )
                )

    brief, brief_issues = _load_brief(brief_path)
    issues.extend(brief_issues)

    presentation_root = workspace / "presentation"
    if brief is not None:
        for rel in brief.source_artifacts:
            path = workspace / rel if not Path(rel).is_absolute() else Path(rel)
            if not path.exists():
                issues.append(
                    issue(
                        "source_artifact_missing",
                        phase="synthesis",
                        message=f"source_artifacts path not found: {rel}",
                        fix_hint="List real paths to presentation reports or analysis_summary.json",
                    )
                )
        for hid in brief.scope_hypothesis_ids:
            pres = presentation_root / f"hypothesis_{hid}"
            if (
                not (pres / "report_zh.md").exists()
                or not (pres / "report_zh.html").exists()
            ):
                issues.append(
                    issue(
                        "scope_hypothesis_no_report",
                        phase="synthesis",
                        message=f"No presentation outputs for hypothesis {hid}",
                        fix_hint="Complete validate-release for each scoped hypothesis first",
                    )
                )

    charts_dir = synthesis_dir / "charts"
    if charts_dir.exists():
        chart_count = len(list(charts_dir.glob("chart_*.png"))) + len(
            list(charts_dir.glob("figure_*.png"))
        )
        if max_synthesis_charts > 0 and chart_count > max_synthesis_charts:
            issues.append(
                issue(
                    "synthesis_chart_cap",
                    phase="synthesis",
                    message=f"Synthesis charts {chart_count} > cap {max_synthesis_charts}",
                )
            )

    if scope_hypothesis_ids and brief is None:
        for hid in scope_hypothesis_ids:
            pres = presentation_root / f"hypothesis_{hid}"
            if not (pres / "report_zh.md").exists():
                issues.append(
                    issue(
                        "scope_hypothesis_no_report",
                        phase="synthesis",
                        message=f"hypothesis {hid} missing report_zh.md",
                    )
                )

    if issues:
        return blocked(
            issues, recommended_next_step="Fix synthesis_brief.json and reports"
        )
    return passed()
