#!/usr/bin/env python3
"""Core analysis CLI subcommands for context, schema, and query access."""

import argparse
import dataclasses
import json
import os
import re
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from pydantic import BaseModel


def _default_workspace() -> Path:
    raw_workspace = os.environ.get("AGENTSOCIETY_WORKSPACE")
    if raw_workspace:
        return Path(raw_workspace).expanduser().resolve()
    return Path.cwd().resolve()


def _load_workspace_env() -> None:
    env_file = _default_workspace() / ".env"
    if env_file.exists():
        load_dotenv(env_file)


_load_workspace_env()

ContextLoader: type[Any] | None = None
DataReader: type[Any] | None = None
extract_database_schema: Any = None
EDAGenerator: type[Any] | None = None
AssetManager: type[Any] | None = None
ReportAsset: type[Any] | None = None
SUPPORTED_IMAGE_FORMATS: set[str] | None = None
_DEFAULT_IMAGE_FORMATS = {".png", ".jpg", ".jpeg", ".svg", ".pdf", ".webp"}


def _ensure_analysis_dependencies() -> None:
    """Load analysis dependencies from the active Python interpreter."""

    global ContextLoader
    global DataReader
    global extract_database_schema
    global EDAGenerator
    global AssetManager
    global ReportAsset
    global SUPPORTED_IMAGE_FORMATS
    if ContextLoader is not None:
        return

    try:
        from agentsociety2.skills.analysis import (
            AssetManager as _AssetManager,
            ContextLoader as _ContextLoader,
            DataReader as _DataReader,
            EDAGenerator as _EDAGenerator,
            extract_database_schema as _extract_database_schema,
        )
        from agentsociety2.skills.analysis.models import (
            ReportAsset as _ReportAsset,
            SUPPORTED_IMAGE_FORMATS as _SUPPORTED_IMAGE_FORMATS,
        )
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "agentsociety2 is not available in the current Python interpreter. "
            "Run this script with the workspace PYTHON_PATH from .env "
            "(for example: `$PYTHON_PATH .agentsociety/bin/ags.py analysis ...`)."
        ) from exc

    ContextLoader = _ContextLoader
    DataReader = _DataReader
    extract_database_schema = _extract_database_schema
    EDAGenerator = _EDAGenerator
    AssetManager = _AssetManager
    ReportAsset = _ReportAsset
    SUPPORTED_IMAGE_FORMATS = _SUPPORTED_IMAGE_FORMATS


class _ArgumentParseError(Exception):
    pass


class _JsonArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise _ArgumentParseError(message)

    def exit(self, status: int = 0, message: str | None = None) -> None:
        if message:
            raise _ArgumentParseError(message.strip())
        raise _ArgumentParseError(f"argument parsing exited with status {status}")


def _json_default(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return dataclasses.asdict(value)
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def _emit(payload: dict[str, Any]) -> None:
    sys.stdout.write(
        json.dumps(
            payload, default=_json_default, ensure_ascii=False, separators=(",", ":")
        )
    )
    sys.stdout.write("\n")


def _ok(**payload: Any) -> int:
    _emit({"success": True, **payload})
    return 0


def _error(message: str) -> int:
    _emit({"success": False, "error": message})
    return 1


def _build_parser() -> argparse.ArgumentParser:
    parser = _JsonArgumentParser(description="Analysis CLI tool layer")
    subparsers = parser.add_subparsers(dest="command", required=True)
    workspace_default = str(_default_workspace())

    load_context_parser = subparsers.add_parser("load-context")
    load_context_parser.add_argument("--workspace", default=workspace_default)
    load_context_parser.add_argument("--hypothesis-id", required=True)
    load_context_parser.add_argument("--experiment-id", required=True)

    def _add_data_path_argument(parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "--data-path",
            "--db-path",
            dest="data_path",
            required=True,
            help="Replay directory path; --db-path is accepted for legacy sqlite.db workflows",
        )

    list_tables_parser = subparsers.add_parser("list-tables")
    _add_data_path_argument(list_tables_parser)

    data_summary_parser = subparsers.add_parser("data-summary")
    _add_data_path_argument(data_summary_parser)

    query_data_parser = subparsers.add_parser("query-data")
    _add_data_path_argument(query_data_parser)
    query_data_parser.add_argument("--sql", required=True)

    run_eda_parser = subparsers.add_parser("run-eda")
    _add_data_path_argument(run_eda_parser)
    run_eda_parser.add_argument("--output-dir", required=True)
    run_eda_parser.add_argument(
        "--type",
        required=True,
        choices=["ydata", "sweetviz", "missingno", "correlation", "quick-stats"],
    )
    run_eda_parser.add_argument("--tables")
    run_eda_parser.add_argument("--workspace", default=workspace_default)
    run_eda_parser.add_argument("--hypothesis-id")

    collect_assets_parser = subparsers.add_parser("collect-assets")
    collect_assets_parser.add_argument("--workspace", default=workspace_default)
    collect_assets_parser.add_argument("--hypothesis-id", required=True)
    collect_assets_parser.add_argument("--experiment-id", required=True)
    collect_assets_parser.add_argument("--output-dir", required=True)
    collect_assets_parser.add_argument("--charts-dir")
    collect_assets_parser.add_argument("--filter")

    compose_figure_parser = subparsers.add_parser("compose-figure")
    compose_figure_parser.add_argument("--spec", required=True)

    def _add_harness_workspace(parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--workspace", default=workspace_default)

    intake_parser = subparsers.add_parser("intake")
    _add_harness_workspace(intake_parser)
    intake_parser.add_argument("--hypothesis-id", required=True)
    intake_parser.add_argument("--experiment-id", required=True)

    write_plan_parser = subparsers.add_parser("write-plan")
    _add_harness_workspace(write_plan_parser)
    write_plan_parser.add_argument("--hypothesis-id", required=True)
    write_plan_parser.add_argument(
        "--payload", required=True, help="JSON object or path to JSON file"
    )

    validate_plan_parser = subparsers.add_parser("validate-plan")
    _add_harness_workspace(validate_plan_parser)
    validate_plan_parser.add_argument("--hypothesis-id", required=True)

    validate_explore_parser = subparsers.add_parser("validate-explore")
    _add_harness_workspace(validate_explore_parser)
    validate_explore_parser.add_argument("--hypothesis-id", required=True)
    validate_explore_parser.add_argument("--experiment-id", required=True)

    record_claim_parser = subparsers.add_parser("record-claim")
    _add_harness_workspace(record_claim_parser)
    record_claim_parser.add_argument("--hypothesis-id", required=True)
    record_claim_parser.add_argument("--payload", required=True)

    validate_claims_parser = subparsers.add_parser("validate-claims")
    _add_harness_workspace(validate_claims_parser)
    validate_claims_parser.add_argument("--hypothesis-id", required=True)

    record_contract_parser = subparsers.add_parser("record-contract")
    _add_harness_workspace(record_contract_parser)
    record_contract_parser.add_argument("--hypothesis-id", required=True)
    record_contract_parser.add_argument("--payload", required=True)

    validate_chart_parser = subparsers.add_parser("validate-chart")
    _add_harness_workspace(validate_chart_parser)
    validate_chart_parser.add_argument("--hypothesis-id", required=True)
    validate_chart_parser.add_argument("--chart-path")
    validate_chart_parser.add_argument("--code")

    validate_refine_parser = subparsers.add_parser(
        "validate-refine",
        help="Holistic refine gate (contracts + chart files on disk)",
    )
    _add_harness_workspace(validate_refine_parser)
    validate_refine_parser.add_argument("--hypothesis-id", required=True)

    sync_assets_parser = subparsers.add_parser(
        "sync-report-assets",
        help="Copy report-referenced images from charts/ into assets/",
    )
    _add_harness_workspace(sync_assets_parser)
    sync_assets_parser.add_argument("--hypothesis-id", required=True)
    sync_assets_parser.add_argument("--experiment-id", required=True)

    validate_release_parser = subparsers.add_parser("validate-release")
    _add_harness_workspace(validate_release_parser)
    validate_release_parser.add_argument("--hypothesis-id", required=True)
    validate_release_parser.add_argument("--experiment-id", required=True)

    validate_rq_parser = subparsers.add_parser(
        "validate-report-quality",
        help="Mechanical narrative quality checks (no independent review file)",
    )
    _add_harness_workspace(validate_rq_parser)
    validate_rq_parser.add_argument("--hypothesis-id", required=True)
    validate_rq_parser.add_argument("--experiment-id", required=True)

    record_rr_parser = subparsers.add_parser(
        "record-report-review",
        help="Store independent LLM review (report_review.json)",
    )
    _add_harness_workspace(record_rr_parser)
    record_rr_parser.add_argument("--hypothesis-id", required=True)
    record_rr_parser.add_argument("--experiment-id", required=True)
    record_rr_parser.add_argument("--payload", required=True)

    record_sr_parser = subparsers.add_parser(
        "record-synthesis-review",
        help="Store independent synthesis review (synthesis_review.json)",
    )
    _add_harness_workspace(record_sr_parser)
    record_sr_parser.add_argument("--payload", required=True)

    validate_synthesis_parser = subparsers.add_parser("validate-synthesis")
    _add_harness_workspace(validate_synthesis_parser)

    validate_parser = subparsers.add_parser("validate")
    _add_harness_workspace(validate_parser)
    validate_parser.add_argument("--hypothesis-id", required=True)
    validate_parser.add_argument("--experiment-id", required=True)

    advance_parser = subparsers.add_parser("advance")
    _add_harness_workspace(advance_parser)
    advance_parser.add_argument("--hypothesis-id", required=True)
    advance_parser.add_argument("--experiment-id", required=True)
    advance_parser.add_argument("--phase", required=True)

    status_parser = subparsers.add_parser("status")
    _add_harness_workspace(status_parser)
    status_parser.add_argument("--hypothesis-id")

    run_loop_parser = subparsers.add_parser("run-loop")
    _add_harness_workspace(run_loop_parser)
    run_loop_parser.add_argument("--hypothesis-id", required=True)
    run_loop_parser.add_argument("--experiment-id", required=True)

    record_att_parser = subparsers.add_parser("record-attestation")
    _add_harness_workspace(record_att_parser)
    record_att_parser.add_argument("--hypothesis-id")
    record_att_parser.add_argument("--payload", required=True)

    build_ctx_parser = subparsers.add_parser(
        "build-report-context",
        help="Aggregate EDA/charts/claims into data/evidence_index.json and report_context.md",
    )
    _add_harness_workspace(build_ctx_parser)
    build_ctx_parser.add_argument("--hypothesis-id", required=True)

    record_art_parser = subparsers.add_parser("record-phase-artifacts")
    _add_harness_workspace(record_art_parser)
    record_art_parser.add_argument("--hypothesis-id", required=True)
    record_art_parser.add_argument("--phase", required=True)
    record_art_parser.add_argument(
        "--artifacts", required=True, help="JSON array of file paths"
    )

    gate_status_parser = subparsers.add_parser("gate-status")
    _add_harness_workspace(gate_status_parser)
    gate_status_parser.add_argument("--hypothesis-id")

    draft_reflection_parser = subparsers.add_parser(
        "draft-reflection",
        help="Create a reviewable post-run learning draft from harness state",
    )
    _add_harness_workspace(draft_reflection_parser)
    draft_reflection_parser.add_argument("--hypothesis-id", required=True)
    draft_reflection_parser.add_argument("--experiment-id", required=True)

    record_reflection_parser = subparsers.add_parser(
        "record-reflection",
        help="Store a reviewed reflection report before promotion",
    )
    _add_harness_workspace(record_reflection_parser)
    record_reflection_parser.add_argument("--hypothesis-id")
    record_reflection_parser.add_argument("--payload", required=True)

    record_feedback_parser = subparsers.add_parser(
        "record-feedback",
        help="Store user post-analysis feedback for reflection and memory promotion",
    )
    _add_harness_workspace(record_feedback_parser)
    record_feedback_parser.add_argument("--hypothesis-id")
    record_feedback_parser.add_argument("--payload", required=True)

    review_reflection_parser = subparsers.add_parser(
        "review-reflection",
        help="Run pre-promotion review over reflection and feedback records",
    )
    _add_harness_workspace(review_reflection_parser)
    review_reflection_parser.add_argument("--hypothesis-id")
    review_reflection_parser.add_argument(
        "--include-preferences",
        action="store_true",
        help="Check whether preference promotion has explicit feedback evidence",
    )

    promote_reflection_parser = subparsers.add_parser(
        "promote-reflection",
        help="Promote reviewed lessons/recipes/preferences into workspace memory",
    )
    _add_harness_workspace(promote_reflection_parser)
    promote_reflection_parser.add_argument("--hypothesis-id")
    promote_reflection_parser.add_argument(
        "--include-preferences",
        action="store_true",
        help="Promote preference candidates only after explicit user confirmation",
    )
    promote_reflection_parser.add_argument(
        "--skip-recipes",
        action="store_true",
        help="Do not write method recipe markdown files",
    )
    promote_reflection_parser.add_argument(
        "--skip-lessons",
        action="store_true",
        help="Do not append project lessons JSONL records",
    )

    memory_context_parser = subparsers.add_parser(
        "memory-context",
        help="Show active experience memory injected into analysis orchestration",
    )
    _add_harness_workspace(memory_context_parser)
    memory_context_parser.add_argument("--hypothesis-id")

    return parser


def _parse_csv_list(raw_value: str | None) -> list[str] | None:
    if raw_value is None:
        return None
    items = []
    seen = set()
    for item in raw_value.split(","):
        normalized = item.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        items.append(normalized)
    return items or None


def _get_supported_image_formats() -> set[str]:
    return SUPPORTED_IMAGE_FORMATS or _DEFAULT_IMAGE_FORMATS


def _validate_read_only_sql(sql: str) -> str:
    normalized_sql = (sql or "").strip()
    if not normalized_sql:
        raise ValueError("query-data only supports read-only SQL queries")
    if ";" in normalized_sql.rstrip(";"):
        raise ValueError("query-data only supports a single read-only SQL statement")

    compact_sql = re.sub(r"\s+", " ", normalized_sql).strip().lower()
    if not (compact_sql.startswith("select ") or compact_sql.startswith("with ")):
        raise ValueError("query-data only supports read-only SELECT or WITH queries")

    blocked_tokens = (
        " insert ",
        " update ",
        " delete ",
        " drop ",
        " alter ",
        " attach ",
        " detach ",
        " create ",
        " replace ",
        " pragma ",
        " reindex ",
        " vacuum ",
    )
    scan_sql = f" {compact_sql} "
    if any(token in scan_sql for token in blocked_tokens):
        raise ValueError("query-data only supports read-only SQL queries")
    return normalized_sql


def _validate_plotting_conventions(code: str) -> None:
    """Require the publication plotting scaffold used by generated chart scripts."""

    text = code or ""
    compact = re.sub(r"\s+", "", text)
    missing: list[str] = []

    if not re.search(r"(?:matplotlib|mpl)\.use\(\s*['\"]Agg['\"]\s*\)", text):
        missing.append('matplotlib backend configured to "Agg"')

    has_font_family = (
        'rcParams["font.family"]' in text
        or "rcParams['font.family']" in text
        or '"font.family":' in text
        or "'font.family':" in text
    )
    if not has_font_family:
        missing.append('`font.family = "sans-serif"`')

    has_sans_serif = (
        'rcParams["font.sans-serif"]' in text
        or "rcParams['font.sans-serif']" in text
        or '"font.sans-serif":' in text
        or "'font.sans-serif':" in text
    )
    if not has_sans_serif:
        missing.append("`font.sans-serif` configured with readable fallbacks")

    has_svg_fonttype_none = (
        'rcParams["svg.fonttype"]="none"' in compact
        or "rcParams['svg.fonttype']='none'" in compact
        or '"svg.fonttype":"none"' in compact
        or "'svg.fonttype':'none'" in compact
    )
    if not has_svg_fonttype_none:
        missing.append('`svg.fonttype = "none"`')

    if missing:
        raise ValueError(
            "Plotting script must include: " + "; ".join(missing)
        )


def _filter_assets_with_companions(
    assets: list[Any],
    selected_names: set[str],
) -> list[Any]:
    if not selected_names:
        return assets

    selected_stems = {
        Path(name).stem
        for name in selected_names
        if Path(name).suffix.lower() in _get_supported_image_formats()
    }

    filtered_assets = []
    for asset in assets:
        asset_name = Path(asset.file_path).name
        asset_stem = Path(asset_name).stem
        if asset_name in selected_names or asset_stem in selected_stems:
            filtered_assets.append(asset)
    return filtered_assets


def _require_pillow() -> tuple[Any, Any, Any]:
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "compose-figure requires Pillow. Install it in the active Python "
            "environment, then rerun the command."
        ) from exc
    return Image, ImageDraw, ImageFont


def _ensure_positive_int(value: Any, field_name: str) -> int:
    if not isinstance(value, int) or value <= 0:
        raise ValueError(f"{field_name} must be a positive integer")
    return value


def _ensure_non_negative_int(value: Any, field_name: str) -> int:
    if not isinstance(value, int) or value < 0:
        raise ValueError(f"{field_name} must be a non-negative integer")
    return value


def _resolve_compose_path(raw_path: str, base_dir: Path) -> Path:
    path = Path(raw_path)
    if not path.is_absolute():
        path = base_dir / path
    return path.resolve()


def _load_compose_font(image_font: Any, size: int) -> Any:
    candidates = (
        "DejaVuSans-Bold.ttf",
        "Arial Bold.ttf",
        "Arial.ttf",
    )
    for candidate in candidates:
        try:
            return image_font.truetype(candidate, size=size)
        except OSError:
            continue
    return image_font.load_default()


def _fit_image_to_box(
    image: Any,
    box_width: int,
    box_height: int,
    preserve_aspect: bool = True,
) -> tuple[Any, tuple[int, int]]:
    if preserve_aspect:
        resized = image.copy()
        resized.thumbnail((box_width, box_height))
        offset_x = (box_width - resized.width) // 2
        offset_y = (box_height - resized.height) // 2
        return resized, (offset_x, offset_y)

    return image.resize((box_width, box_height)), (0, 0)


def _grid_boxes(
    canvas_width: int,
    canvas_height: int,
    layout: dict[str, Any],
    panel_count: int,
) -> list[dict[str, int]]:
    rows = _ensure_positive_int(layout.get("rows"), "layout.rows")
    cols = _ensure_positive_int(layout.get("cols"), "layout.cols")
    capacity = rows * cols
    if panel_count > capacity:
        raise ValueError(
            f"layout grid capacity is {capacity}, but spec declares {panel_count} panels"
        )

    gap = _ensure_non_negative_int(layout.get("gap", 32), "layout.gap")
    padding = _ensure_non_negative_int(layout.get("padding", 72), "layout.padding")
    inner_width = canvas_width - padding * 2 - gap * (cols - 1)
    inner_height = canvas_height - padding * 2 - gap * (rows - 1)
    if inner_width <= 0 or inner_height <= 0:
        raise ValueError("layout padding and gap leave no drawable area on the canvas")

    cell_width = inner_width // cols
    cell_height = inner_height // rows
    boxes: list[dict[str, int]] = []
    for index in range(panel_count):
        row = index // cols
        col = index % cols
        x = padding + col * (cell_width + gap)
        y = padding + row * (cell_height + gap)
        boxes.append(
            {
                "x": x,
                "y": y,
                "width": cell_width,
                "height": cell_height,
            }
        )
    return boxes


def _manual_boxes(panels: list[dict[str, Any]]) -> list[dict[str, int]]:
    boxes: list[dict[str, int]] = []
    for index, panel in enumerate(panels):
        box = panel.get("box")
        if not isinstance(box, dict):
            raise ValueError(
                f'panel {index} requires a "box" object when layout.type is "manual"'
            )
        boxes.append(
            {
                "x": _ensure_non_negative_int(box.get("x"), f"panels[{index}].box.x"),
                "y": _ensure_non_negative_int(box.get("y"), f"panels[{index}].box.y"),
                "width": _ensure_positive_int(
                    box.get("width"), f"panels[{index}].box.width"
                ),
                "height": _ensure_positive_int(
                    box.get("height"), f"panels[{index}].box.height"
                ),
            }
        )
    return boxes


def _draw_panel_label(
    canvas: Any,
    image_draw: Any,
    image_font: Any,
    label: str,
    box: dict[str, int],
) -> None:
    font = _load_compose_font(image_font, size=42)
    draw = image_draw.Draw(canvas)
    text = label.strip()
    if not text:
        return

    left = box["x"] + 18
    top = box["y"] + 12
    draw.text((left, top), text, fill="#111111", font=font)


def _compose_figure(spec_path: Path) -> dict[str, Any]:
    Image, ImageDraw, ImageFont = _require_pillow()

    raw_spec = json.loads(spec_path.read_text(encoding="utf-8"))
    if not isinstance(raw_spec, dict):
        raise ValueError("compose-figure spec must be a JSON object")

    panels = raw_spec.get("panels")
    if not isinstance(panels, list) or not panels:
        raise ValueError("compose-figure spec must include a non-empty panels array")

    output_value = raw_spec.get("output")
    if not isinstance(output_value, str) or not output_value.strip():
        raise ValueError('compose-figure spec must include a non-empty "output" path')

    canvas_spec = raw_spec.get("canvas") or {}
    if not isinstance(canvas_spec, dict):
        raise ValueError('"canvas" must be an object when provided')
    canvas_width = _ensure_positive_int(canvas_spec.get("width", 2400), "canvas.width")
    canvas_height = _ensure_positive_int(
        canvas_spec.get("height", 1400), "canvas.height"
    )
    background = canvas_spec.get("background", "#FFFFFF")
    if not isinstance(background, str) or not background.strip():
        raise ValueError("canvas.background must be a non-empty color string")

    layout = raw_spec.get("layout") or {"type": "grid", "rows": 1, "cols": len(panels)}
    if not isinstance(layout, dict):
        raise ValueError('"layout" must be an object when provided')
    layout_type = str(layout.get("type", "grid")).strip().lower()
    if layout_type not in {"grid", "manual"}:
        raise ValueError('layout.type must be either "grid" or "manual"')

    boxes = (
        _grid_boxes(canvas_width, canvas_height, layout, len(panels))
        if layout_type == "grid"
        else _manual_boxes(panels)
    )

    base_dir = spec_path.parent
    output_path = _resolve_compose_path(output_value, base_dir)
    if output_path.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"}:
        output_path = output_path.with_suffix(".png")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    canvas = Image.new("RGBA", (canvas_width, canvas_height), background)
    panel_summaries: list[dict[str, Any]] = []
    supported_suffixes = {".png", ".jpg", ".jpeg", ".webp"}

    for index, (panel, box) in enumerate(zip(panels, boxes)):
        if not isinstance(panel, dict):
            raise ValueError(f"panels[{index}] must be an object")

        source_value = panel.get("source")
        if not isinstance(source_value, str) or not source_value.strip():
            raise ValueError(f'panels[{index}] must include a non-empty "source" path')

        source_path = _resolve_compose_path(source_value, base_dir)
        if source_path.suffix.lower() not in supported_suffixes:
            raise ValueError(
                "compose-figure currently supports raster inputs only: "
                ".png, .jpg, .jpeg, .webp. Export a PNG companion first for "
                f"{source_path.name}."
            )
        if not source_path.exists():
            raise FileNotFoundError(str(source_path))

        preserve_aspect = bool(panel.get("preserve_aspect", True))
        with Image.open(source_path) as opened_image:
            fitted_image, offset = _fit_image_to_box(
                opened_image.convert("RGBA"),
                box["width"],
                box["height"],
                preserve_aspect=preserve_aspect,
            )

        paste_x = box["x"] + offset[0]
        paste_y = box["y"] + offset[1]
        canvas.alpha_composite(fitted_image, (paste_x, paste_y))

        label = str(panel.get("label", "")).strip()
        if label:
            _draw_panel_label(
                canvas,
                ImageDraw,
                ImageFont,
                label,
                box,
            )

        panel_summaries.append(
            {
                "label": label or None,
                "source": str(source_path),
                "box": box,
                "rendered_size": {
                    "width": fitted_image.width,
                    "height": fitted_image.height,
                },
            }
        )

    if output_path.suffix.lower() in {".jpg", ".jpeg"}:
        canvas.convert("RGB").save(output_path, quality=95)
    else:
        canvas.save(output_path)

    metadata_path = output_path.with_suffix(".json")
    metadata = {
        "output": str(output_path),
        "canvas": {
            "width": canvas_width,
            "height": canvas_height,
            "background": background,
        },
        "layout": {
            "type": layout_type,
            **{k: v for k, v in layout.items() if k != "type"},
        },
        "panels": panel_summaries,
    }
    metadata_path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return {
        "output": str(output_path),
        "metadata": str(metadata_path),
        "panels": panel_summaries,
    }


def _run_load_context(args: argparse.Namespace) -> int:
    _ensure_analysis_dependencies()
    workspace = Path(args.workspace)
    context = ContextLoader(workspace).load_context(
        args.hypothesis_id, args.experiment_id
    )
    data_path = (
        workspace
        / f"hypothesis_{context.hypothesis_id}"
        / f"experiment_{context.experiment_id}"
        / "run"
        / "replay"
    )
    return _ok(
        context=context,
        paths={"data_path": data_path, "db_path": data_path},
    )


def _run_list_tables(args: argparse.Namespace) -> int:
    _ensure_analysis_dependencies()
    data_path = Path(args.data_path)
    schema = extract_database_schema(data_path)
    tables = [
        {"name": name, "column_count": len(columns)}
        for name, columns in sorted(schema.items())
    ]
    return _ok(tables=tables)


def _run_data_summary(args: argparse.Namespace) -> int:
    _ensure_analysis_dependencies()
    summary = DataReader(Path(args.data_path)).read_full_summary()
    return _ok(
        summary={
            "data_path": summary.db_path,
            "db_path": summary.db_path,
            "tables": summary.tables,
            "row_counts": summary.row_counts,
            "schema_markdown": summary.schema_markdown,
            "numeric_stats": summary.numeric_stats,
            "categorical_stats": summary.categorical_stats,
            "sample_data": summary.sample_data,
        }
    )


def _run_query_data(args: argparse.Namespace) -> int:
    db_path = Path(args.data_path).resolve()
    sql = _validate_read_only_sql(args.sql)
    replay_schema = db_path / "_schema.json" if db_path.is_dir() else None
    if replay_schema is not None and replay_schema.exists():
        from agentsociety2.storage import ReplayReader

        reader = ReplayReader(db_path)
        try:
            for dataset in reader.load_dataset_catalog():
                reader._ensure_view(dataset)
            cursor = reader._connection().execute(sql)
            columns = [column[0] for column in cursor.description or []]
            rows = [list(row) for row in cursor.fetchall()]
            return _ok(columns=columns, rows=rows, count=len(rows))
        finally:
            reader.close()
    db_uri = db_path.as_uri() + "?mode=ro"
    with sqlite3.connect(db_uri, uri=True) as conn:
        cursor = conn.execute(sql)
        columns = [column[0] for column in cursor.description or []]
        rows = [list(row) for row in cursor.fetchall()]
    return _ok(columns=columns, rows=rows, count=len(rows))


def _run_eda(args: argparse.Namespace) -> int:
    _ensure_analysis_dependencies()
    db_path = Path(args.data_path)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    tables = _parse_csv_list(args.tables)
    generator = EDAGenerator()
    reader = DataReader(db_path)
    requested_tables, selected_tables, invalid_tables = (
        generator.resolve_table_selection(
            reader,
            tables,
        )
    )

    if requested_tables and not selected_tables:
        requested = ", ".join(requested_tables)
        return _error(
            f"run-eda: none of the requested tables are available: {requested}"
        )

    if args.type == "quick-stats":
        content = generator.generate_quick_stats(db_path, tables=selected_tables)
        quick_stats_path = output_dir / "eda_quick_stats.md"
        quick_stats_path.write_text(content or "", encoding="utf-8")
        files = [str(quick_stats_path)]
        _maybe_record_eda_artifacts(args, files)
        return _ok(
            type=args.type,
            files=files,
            content=content or "",
            requested_tables=requested_tables,
            selected_tables=selected_tables,
            invalid_tables=invalid_tables,
        )

    method_map = {
        "ydata": generator.generate_ydata_profile,
        "sweetviz": generator.generate_sweetviz_profile,
        "missingno": generator.generate_missingno_report,
        "correlation": generator.generate_correlation_report,
    }
    output_path = method_map[args.type](db_path, output_dir, tables=selected_tables)
    files = [str(output_path)] if output_path else []
    _maybe_record_eda_artifacts(args, files)
    return _ok(
        type=args.type,
        files=files,
        requested_tables=requested_tables,
        selected_tables=selected_tables,
        invalid_tables=invalid_tables,
    )


def _maybe_record_eda_artifacts(args: argparse.Namespace, files: list[str]) -> None:
    if not files or not getattr(args, "hypothesis_id", None):
        return
    workspace = Path(args.workspace).resolve()
    from agentsociety2.skills.analysis.harness import cli as harness_cli

    harness_cli.cmd_record_phase_artifacts(
        workspace,
        args.hypothesis_id,
        "explore",
        files,
    )


def _run_collect_assets(args: argparse.Namespace) -> int:
    _ensure_analysis_dependencies()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    asset_manager = AssetManager(Path(args.workspace))
    assets = asset_manager.discover_assets(args.experiment_id, args.hypothesis_id)

    if args.charts_dir:
        charts_dir = Path(args.charts_dir)
        for file_path in sorted(charts_dir.rglob("*")):
            if (
                not file_path.is_file()
                or file_path.suffix.lower() not in SUPPORTED_IMAGE_FORMATS
            ):
                continue
            relative_path = file_path.relative_to(charts_dir)
            assets.append(
                ReportAsset(
                    asset_id=asset_manager._build_asset_id("chart", relative_path),
                    asset_type="chart",
                    title=file_path.stem,
                    file_path=str(file_path),
                    description=f"Collected chart: {relative_path.as_posix()}",
                    file_size=file_path.stat().st_size,
                )
            )

    selected_names = set(_parse_csv_list(args.filter) or [])
    if selected_names:
        assets = _filter_assets_with_companions(assets, selected_names)

    processed = asset_manager.process_assets(assets, output_dir)
    return _ok(assets=processed)


def _run_compose_figure(args: argparse.Namespace) -> int:
    spec_path = Path(args.spec).resolve()
    result = _compose_figure(spec_path)
    return _ok(**result)


def _load_json_payload(raw: str) -> dict[str, Any]:
    from agentsociety2.skills.analysis.harness.json_io import load_dict_payload

    return load_dict_payload(raw)


def _dispatch_harness(args: argparse.Namespace) -> int:
    from agentsociety2.skills.analysis.harness import cli as harness_cli

    workspace = Path(args.workspace)
    cmd = args.command
    if cmd == "intake":
        return _ok(
            **harness_cli.cmd_intake(workspace, args.hypothesis_id, args.experiment_id)
        )
    if cmd == "write-plan":
        return _ok(
            **harness_cli.cmd_write_plan(
                workspace, args.hypothesis_id, _load_json_payload(args.payload)
            )
        )
    if cmd == "validate-plan":
        return _ok(**harness_cli.cmd_validate_plan(workspace, args.hypothesis_id))
    if cmd == "validate-explore":
        return _ok(
            **harness_cli.cmd_validate_explore(
                workspace, args.hypothesis_id, args.experiment_id
            )
        )
    if cmd == "record-claim":
        return _ok(
            **harness_cli.cmd_record_claim(
                workspace, args.hypothesis_id, _load_json_payload(args.payload)
            )
        )
    if cmd == "validate-claims":
        return _ok(**harness_cli.cmd_validate_claims(workspace, args.hypothesis_id))
    if cmd == "record-contract":
        return _ok(
            **harness_cli.cmd_record_contract(
                workspace, args.hypothesis_id, _load_json_payload(args.payload)
            )
        )
    if cmd == "validate-chart":
        return _ok(
            **harness_cli.cmd_validate_chart(
                workspace,
                args.hypothesis_id,
                chart_path=args.chart_path,
                code=(
                    Path(args.code).read_text(encoding="utf-8")
                    if args.code and Path(args.code).exists()
                    else args.code
                ),
            )
        )
    if cmd == "validate-refine":
        return _ok(**harness_cli.cmd_validate_refine(workspace, args.hypothesis_id))
    if cmd == "build-report-context":
        return _ok(
            **harness_cli.cmd_build_report_context(workspace, args.hypothesis_id)
        )
    if cmd == "validate-report-quality":
        return _ok(
            **harness_cli.cmd_validate_report_quality(
                workspace, args.hypothesis_id, args.experiment_id
            )
        )
    if cmd == "record-report-review":
        return _ok(
            **harness_cli.cmd_record_report_review(
                workspace,
                args.hypothesis_id,
                args.experiment_id,
                _load_json_payload(args.payload),
            )
        )
    if cmd == "record-synthesis-review":
        return _ok(
            **harness_cli.cmd_record_synthesis_review(
                workspace,
                _load_json_payload(args.payload),
            )
        )
    if cmd == "sync-report-assets":
        return _ok(
            **harness_cli.cmd_sync_report_assets(
                workspace, args.hypothesis_id, args.experiment_id
            )
        )
    if cmd == "validate-release":
        return _ok(
            **harness_cli.cmd_validate_release(
                workspace, args.hypothesis_id, args.experiment_id
            )
        )
    if cmd == "validate-synthesis":
        return _ok(**harness_cli.cmd_validate_synthesis(workspace))
    if cmd == "validate":
        return _ok(
            **harness_cli.cmd_validate(
                workspace, args.hypothesis_id, args.experiment_id
            )
        )
    if cmd == "advance":
        result = harness_cli.cmd_advance(
            workspace, args.hypothesis_id, args.experiment_id, args.phase
        )
        if result.get("error"):
            return _error(result["error"])
        return _ok(**result)
    if cmd == "status":
        return _ok(
            **harness_cli.cmd_status(workspace, getattr(args, "hypothesis_id", None))
        )
    if cmd == "run-loop":
        return _ok(
            **harness_cli.cmd_run_loop(
                workspace, args.hypothesis_id, args.experiment_id
            )
        )
    if cmd == "record-attestation":
        return _ok(
            **harness_cli.cmd_record_attestation(
                workspace,
                getattr(args, "hypothesis_id", None),
                _load_json_payload(args.payload),
            )
        )
    if cmd == "record-phase-artifacts":
        artifacts = _load_json_payload(args.artifacts)
        if not isinstance(artifacts, list):
            return _error("artifacts must be a JSON array of paths")
        return _ok(
            **harness_cli.cmd_record_phase_artifacts(
                workspace, args.hypothesis_id, args.phase, artifacts
            )
        )
    if cmd == "gate-status":
        return _ok(
            **harness_cli.cmd_gate_status(
                workspace, getattr(args, "hypothesis_id", None)
            )
        )
    if cmd == "draft-reflection":
        return _ok(
            **harness_cli.cmd_draft_reflection(
                workspace, args.hypothesis_id, args.experiment_id
            )
        )
    if cmd == "record-reflection":
        return _ok(
            **harness_cli.cmd_record_reflection(
                workspace,
                getattr(args, "hypothesis_id", None),
                _load_json_payload(args.payload),
            )
        )
    if cmd == "record-feedback":
        return _ok(
            **harness_cli.cmd_record_feedback(
                workspace,
                getattr(args, "hypothesis_id", None),
                _load_json_payload(args.payload),
            )
        )
    if cmd == "review-reflection":
        return _ok(
            **harness_cli.cmd_review_reflection(
                workspace,
                getattr(args, "hypothesis_id", None),
                include_preferences=args.include_preferences,
            )
        )
    if cmd == "promote-reflection":
        return _ok(
            **harness_cli.cmd_promote_reflection(
                workspace,
                getattr(args, "hypothesis_id", None),
                include_preferences=args.include_preferences,
                include_recipes=not args.skip_recipes,
                include_lessons=not args.skip_lessons,
            )
        )
    if cmd == "memory-context":
        return _ok(
            **harness_cli.cmd_memory_context(
                workspace, getattr(args, "hypothesis_id", None)
            )
        )
    return _error(f"unknown harness command: {cmd}")


def main() -> int:
    try:
        parser = _build_parser()
        args = parser.parse_args()

        if args.command == "load-context":
            return _run_load_context(args)
        if args.command == "list-tables":
            return _run_list_tables(args)
        if args.command == "data-summary":
            return _run_data_summary(args)
        if args.command == "query-data":
            return _run_query_data(args)
        if args.command == "run-eda":
            return _run_eda(args)
        if args.command == "collect-assets":
            return _run_collect_assets(args)
        if args.command == "compose-figure":
            return _run_compose_figure(args)
        harness_commands = {
            "intake",
            "write-plan",
            "validate-plan",
            "validate-explore",
            "record-claim",
            "validate-claims",
            "record-contract",
            "validate-chart",
            "validate-refine",
            "sync-report-assets",
            "validate-release",
            "validate-report-quality",
            "record-report-review",
            "record-synthesis-review",
            "validate-synthesis",
            "validate",
            "advance",
            "status",
            "run-loop",
            "record-attestation",
            "record-phase-artifacts",
            "build-report-context",
            "gate-status",
            "draft-reflection",
            "record-reflection",
            "promote-reflection",
            "memory-context",
            "record-feedback",
            "review-reflection",
        }
        if args.command in harness_commands:
            return _dispatch_harness(args)
        return _error(f"unknown command: {args.command}")
    except _ArgumentParseError as exc:
        return _error(str(exc))
    except FileNotFoundError as exc:
        return _error(str(exc))
    except sqlite3.Error as exc:
        return _error(f"sqlite error: {exc}")
    except Exception as exc:
        return _error(str(exc))


if __name__ == "__main__":
    sys.exit(main())
