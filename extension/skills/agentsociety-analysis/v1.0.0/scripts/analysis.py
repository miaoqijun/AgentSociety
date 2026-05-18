#!/usr/bin/env python3
"""Core analysis CLI subcommands for context, schema, and query access."""

import argparse
import asyncio
import ast
import dataclasses
import json
import os
import re
import shutil
import sqlite3
import sys
import tempfile
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
DependencyDetector: type[Any] | None = None
LocalCodeExecutor: type[Any] | None = None
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
    global DependencyDetector
    global LocalCodeExecutor

    if ContextLoader is not None:
        return

    try:
        from agentsociety2.code_executor.dependency_detector import (
            DependencyDetector as _DependencyDetector,
        )
        from agentsociety2.code_executor.local_executor import (
            LocalCodeExecutor as _LocalCodeExecutor,
        )
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
    DependencyDetector = _DependencyDetector
    LocalCodeExecutor = _LocalCodeExecutor


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
        json.dumps(payload, default=_json_default, ensure_ascii=False, separators=(",", ":"))
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

    list_tables_parser = subparsers.add_parser("list-tables")
    list_tables_parser.add_argument("--db-path", required=True)

    data_summary_parser = subparsers.add_parser("data-summary")
    data_summary_parser.add_argument("--db-path", required=True)

    query_data_parser = subparsers.add_parser("query-data")
    query_data_parser.add_argument("--db-path", required=True)
    query_data_parser.add_argument("--sql", required=True)

    run_code_parser = subparsers.add_parser("run-code")
    run_code_parser.add_argument("--db-path")
    run_code_parser.add_argument("--code", required=True)
    run_code_parser.add_argument("--timeout", type=int, default=120)
    run_code_parser.add_argument("--extra-files")

    run_eda_parser = subparsers.add_parser("run-eda")
    run_eda_parser.add_argument("--db-path", required=True)
    run_eda_parser.add_argument("--output-dir", required=True)
    run_eda_parser.add_argument(
        "--type",
        required=True,
        choices=["ydata", "sweetviz", "missingno", "correlation", "quick-stats"],
    )
    run_eda_parser.add_argument("--tables")

    collect_assets_parser = subparsers.add_parser("collect-assets")
    collect_assets_parser.add_argument("--workspace", default=workspace_default)
    collect_assets_parser.add_argument("--hypothesis-id", required=True)
    collect_assets_parser.add_argument("--experiment-id", required=True)
    collect_assets_parser.add_argument("--output-dir", required=True)
    collect_assets_parser.add_argument("--charts-dir")
    collect_assets_parser.add_argument("--filter")

    compose_figure_parser = subparsers.add_parser("compose-figure")
    compose_figure_parser.add_argument("--spec", required=True)

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


def _read_code_payload(code_arg: str) -> tuple[str, Path]:
    if code_arg == "-":
        return sys.stdin.read(), Path.cwd()

    code_path = Path(code_arg).resolve()
    return code_path.read_text(encoding="utf-8"), code_path.parent


def _copy_into_work_dir(source: Path, destination_dir: Path, name: str | None = None) -> Path:
    target = destination_dir / (name or source.name)
    shutil.copy2(source, target)
    return target


def _collect_artifacts(
    work_dir: Path,
    output_dir: Path,
    artifact_paths: list[str],
) -> list[str]:
    allowed_suffixes = {".png", ".jpg", ".jpeg", ".svg", ".pdf", ".webp", ".csv", ".json", ".txt"}
    output_dir.mkdir(parents=True, exist_ok=True)

    collected: list[str] = []
    for artifact in artifact_paths:
        rel_path = Path(artifact)
        source_path = work_dir / rel_path
        if source_path.suffix.lower() not in allowed_suffixes or not source_path.exists():
            continue

        destination_path = output_dir / rel_path
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        if source_path.resolve() != destination_path.resolve():
            shutil.copy2(source_path, destination_path)
        collected.append(str(destination_path))

    return sorted(collected)


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


_CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")


def _contains_cjk(text: str) -> bool:
    return bool(_CJK_RE.search(text or ""))


def _extract_string_literals(node: ast.AST | None) -> list[str]:
    if node is None:
        return []
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return [node.value]
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        values: list[str] = []
        for element in node.elts:
            values.extend(_extract_string_literals(element))
        return values
    return []


def _validate_legend_language(code: str) -> None:
    """Reject plotting code that hardcodes CJK text into legend labels."""

    try:
        tree = ast.parse(code)
    except SyntaxError:
        return

    violations: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue

        func = node.func
        func_name = func.attr if isinstance(func, ast.Attribute) else (
            func.id if isinstance(func, ast.Name) else ""
        )

        for keyword in node.keywords:
            if keyword.arg not in {"label", "labels", "title"}:
                continue
            if keyword.arg == "title" and func_name != "legend":
                continue

            for literal in _extract_string_literals(keyword.value):
                if _contains_cjk(literal):
                    violations.append(
                        f"{keyword.arg}={literal!r}"
                    )

        if func_name != "legend":
            continue

        if node.args:
            for literal in _extract_string_literals(node.args[0]):
                if _contains_cjk(literal):
                    violations.append(f"legend({literal!r})")

    if violations:
        details = ", ".join(dict.fromkeys(violations))
        raise ValueError(
            "run-code requires chart legends to use English only. "
            f"Found non-English legend text in: {details}"
        )


def _attribute_path(node: ast.AST | None) -> str:
    if node is None:
        return ""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _attribute_path(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    return ""


def _collect_import_aliases(tree: ast.AST) -> tuple[set[str], set[str], set[str]]:
    matplotlib_aliases: set[str] = set()
    pyplot_aliases: set[str] = set()
    seaborn_aliases: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "matplotlib":
                    matplotlib_aliases.add(alias.asname or alias.name)
                elif alias.name == "matplotlib.pyplot":
                    pyplot_aliases.add(alias.asname or alias.name)
                elif alias.name == "seaborn":
                    seaborn_aliases.add(alias.asname or alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module == "matplotlib":
                for alias in node.names:
                    if alias.name == "pyplot":
                        pyplot_aliases.add(alias.asname or alias.name)
                    elif alias.name == "use":
                        matplotlib_aliases.add(alias.asname or alias.name)
            elif node.module == "matplotlib.pyplot":
                for alias in node.names:
                    pyplot_aliases.add(alias.asname or alias.name)
            elif node.module == "seaborn":
                for alias in node.names:
                    seaborn_aliases.add(alias.asname or alias.name)

    return matplotlib_aliases, pyplot_aliases, seaborn_aliases


def _extract_constant_strings(node: ast.AST | None) -> set[str]:
    return set(_extract_string_literals(node))


def _validate_plotting_conventions(code: str) -> None:
    """Validate core matplotlib conventions required by the analysis skill."""

    try:
        tree = ast.parse(code)
    except SyntaxError:
        return

    matplotlib_aliases, pyplot_aliases, seaborn_aliases = _collect_import_aliases(tree)
    if not (matplotlib_aliases or pyplot_aliases or seaborn_aliases):
        return

    agg_configured = False
    font_family_configured = False
    sans_serif_configured = False
    svg_fonttype_configured = False

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            path = _attribute_path(node.func)

            if path in matplotlib_aliases or path == "use":
                if node.args and "Agg" in _extract_constant_strings(node.args[0]):
                    agg_configured = True
            elif any(path == f"{alias}.use" for alias in matplotlib_aliases):
                if node.args and "Agg" in _extract_constant_strings(node.args[0]):
                    agg_configured = True
            elif any(path == f"{alias}.switch_backend" for alias in pyplot_aliases):
                if node.args and "Agg" in _extract_constant_strings(node.args[0]):
                    agg_configured = True

            rcparams_update_aliases = pyplot_aliases | matplotlib_aliases
            if any(path == f"{alias}.rcParams.update" for alias in rcparams_update_aliases):
                dict_nodes = [arg for arg in node.args if isinstance(arg, ast.Dict)]
                dict_nodes.extend(
                    keyword.value
                    for keyword in node.keywords
                    if keyword.arg is None and isinstance(keyword.value, ast.Dict)
                )
                for dict_node in dict_nodes:
                    for key_node, value_node in zip(dict_node.keys, dict_node.values):
                        key_strings = _extract_constant_strings(key_node)
                        value_strings = _extract_constant_strings(value_node)
                        if "font.family" in key_strings and "sans-serif" in value_strings:
                            font_family_configured = True
                        if "font.sans-serif" in key_strings:
                            sans_serif_configured = True
                        if "svg.fonttype" in key_strings and "none" in value_strings:
                            svg_fonttype_configured = True

        if isinstance(node, ast.Assign):
            for target in node.targets:
                if not isinstance(target, ast.Subscript):
                    continue
                target_path = _attribute_path(target.value)
                if not any(
                    target_path == f"{alias}.rcParams"
                    for alias in (pyplot_aliases | matplotlib_aliases)
                ):
                    continue
                key_strings = _extract_constant_strings(target.slice)
                value_strings = _extract_constant_strings(node.value)
                if "font.family" in key_strings and "sans-serif" in value_strings:
                    font_family_configured = True
                if "font.sans-serif" in key_strings:
                    sans_serif_configured = True
                if "svg.fonttype" in key_strings and "none" in value_strings:
                    svg_fonttype_configured = True

    missing_requirements: list[str] = []
    if not agg_configured:
        missing_requirements.append('matplotlib backend configured to "Agg"')
    if not font_family_configured:
        missing_requirements.append('`plt.rcParams["font.family"] = "sans-serif"`')
    if not sans_serif_configured:
        missing_requirements.append('a `font.sans-serif` rcParams setting')
    if not svg_fonttype_configured:
        missing_requirements.append('`svg.fonttype = "none"` for editable SVG text')

    if missing_requirements:
        raise ValueError(
            "run-code requires analysis charts to include the plotting style scaffold. "
            "Missing: " + ", ".join(missing_requirements)
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
                "width": _ensure_positive_int(box.get("width"), f"panels[{index}].box.width"),
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
    canvas_height = _ensure_positive_int(canvas_spec.get("height", 1400), "canvas.height")
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
        "layout": {"type": layout_type, **{k: v for k, v in layout.items() if k != "type"}},
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
    context = ContextLoader(workspace).load_context(args.hypothesis_id, args.experiment_id)
    db_path = (
        workspace
        / f"hypothesis_{context.hypothesis_id}"
        / f"experiment_{context.experiment_id}"
        / "run"
        / "sqlite.db"
    )
    return _ok(
        context=context,
        paths={"db_path": db_path},
    )


def _run_list_tables(args: argparse.Namespace) -> int:
    _ensure_analysis_dependencies()
    db_path = Path(args.db_path)
    schema = extract_database_schema(db_path)
    tables = [
        {"name": name, "column_count": len(columns)}
        for name, columns in sorted(schema.items())
    ]
    return _ok(tables=tables)


def _run_data_summary(args: argparse.Namespace) -> int:
    _ensure_analysis_dependencies()
    summary = DataReader(Path(args.db_path)).read_full_summary()
    return _ok(
        summary={
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
    db_path = Path(args.db_path).resolve()
    sql = _validate_read_only_sql(args.sql)
    db_uri = db_path.as_uri() + "?mode=ro"
    with sqlite3.connect(db_uri, uri=True) as conn:
        cursor = conn.execute(sql)
        columns = [column[0] for column in cursor.description or []]
        rows = [list(row) for row in cursor.fetchall()]
    return _ok(columns=columns, rows=rows, count=len(rows))


def _run_code(args: argparse.Namespace) -> int:
    _ensure_analysis_dependencies()
    code, persistent_output_dir = _read_code_payload(args.code)
    _validate_legend_language(code)
    _validate_plotting_conventions(code)
    persistent_output_dir.mkdir(parents=True, exist_ok=True)
    work_dir = Path(tempfile.mkdtemp(prefix="analysis_run_", dir=persistent_output_dir))

    try:
        if args.db_path:
            db_path = Path(args.db_path).resolve()
            _copy_into_work_dir(db_path, work_dir, name="sqlite.db")

        for extra_file in _parse_csv_list(args.extra_files) or []:
            _copy_into_work_dir(Path(extra_file).resolve(), work_dir)

        dependencies = DependencyDetector().detect(code)
        result = asyncio.run(
            LocalCodeExecutor(work_dir=work_dir).execute(
                code,
                dependencies=dependencies,
                timeout=args.timeout,
            )
        )
        artifacts = _collect_artifacts(work_dir, persistent_output_dir, result.artifacts)
        _emit(
            {
                "success": result.success,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "return_code": result.return_code,
                "artifacts": artifacts,
            }
        )
        return 0 if result.success else 1
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


def _run_eda(args: argparse.Namespace) -> int:
    _ensure_analysis_dependencies()
    db_path = Path(args.db_path)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    tables = _parse_csv_list(args.tables)
    generator = EDAGenerator()
    reader = DataReader(db_path)
    requested_tables, selected_tables, invalid_tables = generator.resolve_table_selection(
        reader,
        tables,
    )

    if requested_tables and not selected_tables:
        requested = ", ".join(requested_tables)
        return _error(f"run-eda: none of the requested tables are available: {requested}")

    if args.type == "quick-stats":
        content = generator.generate_quick_stats(db_path, tables=selected_tables)
        quick_stats_path = output_dir / "eda_quick_stats.md"
        quick_stats_path.write_text(content or "", encoding="utf-8")
        return _ok(
            type=args.type,
            files=[str(quick_stats_path)],
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
    return _ok(
        type=args.type,
        files=files,
        requested_tables=requested_tables,
        selected_tables=selected_tables,
        invalid_tables=invalid_tables,
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
            if not file_path.is_file() or file_path.suffix.lower() not in SUPPORTED_IMAGE_FORMATS:
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
        if args.command == "run-code":
            return _run_code(args)
        if args.command == "run-eda":
            return _run_eda(args)
        if args.command == "collect-assets":
            return _run_collect_assets(args)
        if args.command == "compose-figure":
            return _run_compose_figure(args)
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
