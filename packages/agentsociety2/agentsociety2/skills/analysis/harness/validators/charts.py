from __future__ import annotations

import ast
from pathlib import Path

from agentsociety2.skills.analysis.harness.models import ValidationResult
from agentsociety2.skills.analysis.harness.validators._helpers import (
    CHART_NAME_RE,
    FIGURE_NAME_RE,
    blocked,
    issue,
    passed,
)


def validate_chart_script(code: str) -> ValidationResult:
    issues = []
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        return blocked(
            [
                issue(
                    "invalid_python",
                    phase="refine",
                    message=str(exc),
                    fix_hint="Fix syntax in chart script",
                )
            ]
        )

    has_agg = False
    has_svg_fonttype = False
    has_font_family = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Attribute) and func.attr == "use":
                if node.args and isinstance(node.args[0], ast.Constant):
                    if str(node.args[0].value).lower() == "agg":
                        has_agg = True
        if isinstance(node, ast.Assign):
            targets = node.targets
            if len(targets) == 1 and isinstance(targets[0], ast.Subscript):
                sub = targets[0]
                if (
                    isinstance(sub.value, ast.Attribute)
                    and sub.value.attr == "rcParams"
                ):
                    if isinstance(sub.slice, ast.Constant):
                        key = str(sub.slice.value)
                        if key == "svg.fonttype" and isinstance(
                            node.value, ast.Constant
                        ):
                            if str(node.value.value) == "none":
                                has_svg_fonttype = True
                        if key == "font.family":
                            has_font_family = True

    if not has_agg:
        issues.append(
            issue(
                "missing_agg_backend",
                phase="refine",
                message='matplotlib.use("Agg") not found',
                fix_hint='Add matplotlib.use("Agg") at top of script',
            )
        )
    if not has_svg_fonttype:
        issues.append(
            issue(
                "missing_svg_fonttype",
                phase="refine",
                message='rcParams["svg.fonttype"] = "none" not found',
                fix_hint='Set plt.rcParams["svg.fonttype"] = "none"',
            )
        )
    if not has_font_family:
        issues.append(
            issue(
                "missing_font_family",
                phase="refine",
                message="sans-serif font family not configured",
                fix_hint="Set font.family and font.sans-serif in rcParams",
            )
        )

    if issues:
        return blocked(issues)
    return passed()


def validate_chart_file(
    chart_path: Path,
    *,
    max_charts: int,
    current_count: int,
) -> ValidationResult:
    issues = []
    if not chart_path.exists():
        issues.append(
            issue(
                "chart_missing",
                phase="refine",
                message=f"Chart file not found: {chart_path}",
                fix_hint="Run run-code to generate the chart",
            )
        )
        return blocked(issues)

    name = chart_path.name
    if not (CHART_NAME_RE.match(name) or FIGURE_NAME_RE.match(name)):
        issues.append(
            issue(
                "chart_naming",
                phase="refine",
                message=f"Chart name does not match convention: {name}",
                fix_hint="Use chart_NN_slug.png or figure_NN_slug.png",
            )
        )

    if chart_path.suffix.lower() == ".png" and chart_path.stat().st_size < 100:
        issues.append(
            issue(
                "chart_empty_file",
                phase="refine",
                message=f"Chart file too small: {chart_path}",
                fix_hint="Regenerate chart; output may be blank",
            )
        )

    if max_charts > 0 and current_count >= max_charts:
        issues.append(
            issue(
                "chart_budget_exceeded",
                phase="refine",
                message=f"Chart count {current_count} >= cap {max_charts}",
                fix_hint="Remove a chart or set max_charts to 0 in state.yaml (no cap)",
            )
        )

    if issues:
        return blocked(issues)
    return passed()
