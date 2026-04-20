#!/usr/bin/env python3
"""Core analysis CLI subcommands for context, schema, and query access."""

import argparse
import asyncio
import ast
import dataclasses
import json
import re
import shutil
import sqlite3
import sys
import tempfile
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from pydantic import BaseModel


# Load environment variables from workspace .env file
workspace_root = Path(__file__).resolve().parents[4]
env_file = workspace_root / ".env"
if env_file.exists():
    load_dotenv(env_file)

ContextLoader: type[Any] | None = None
DataReader: type[Any] | None = None
extract_database_schema: Any = None
EDAGenerator: type[Any] | None = None
AssetManager: type[Any] | None = None
ReportAsset: type[Any] | None = None
SUPPORTED_IMAGE_FORMATS: set[str] | None = None
DependencyDetector: type[Any] | None = None
LocalCodeExecutor: type[Any] | None = None


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

    load_context_parser = subparsers.add_parser("load-context")
    load_context_parser.add_argument("--workspace", required=True)
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
    collect_assets_parser.add_argument("--workspace", required=True)
    collect_assets_parser.add_argument("--hypothesis-id", required=True)
    collect_assets_parser.add_argument("--experiment-id", required=True)
    collect_assets_parser.add_argument("--output-dir", required=True)
    collect_assets_parser.add_argument("--charts-dir")
    collect_assets_parser.add_argument("--filter")

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
        assets = [asset for asset in assets if Path(asset.file_path).name in selected_names]

    processed = asset_manager.process_assets(assets, output_dir)
    return _ok(assets=processed)



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
