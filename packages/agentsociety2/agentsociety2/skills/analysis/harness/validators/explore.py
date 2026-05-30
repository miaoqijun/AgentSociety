from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import List, Optional

from agentsociety2.skills.analysis.harness.models import AnalysisPlan, ValidationResult
from agentsociety2.skills.analysis.harness.validators._helpers import (
    blocked,
    issue,
    passed,
)


def _run_table_checks(db_path: Path, plan: AnalysisPlan) -> List:
    issues = []
    if not plan.table_checks:
        return issues
    try:
        import pandas as pd
    except ModuleNotFoundError:
        return issues

    conn = sqlite3.connect(str(db_path))
    try:
        for check in plan.table_checks:
            table = check.table.strip()
            if not table:
                continue
            quoted = '"' + table.replace('"', '""') + '"'
            try:
                df = pd.read_sql_query(f"SELECT * FROM {quoted} LIMIT 5000", conn)
            except sqlite3.Error as exc:
                issues.append(
                    issue(
                        "table_read_failed",
                        phase="explore",
                        message=f"Cannot read table {table}: {exc}",
                    )
                )
                continue
            if len(df) < check.min_rows:
                issues.append(
                    issue(
                        "min_rows_failed",
                        phase="explore",
                        message=f"Table {table} has {len(df)} rows, need >= {check.min_rows}",
                    )
                )
            for col in check.columns:
                if col not in df.columns:
                    issues.append(
                        issue(
                            "column_missing",
                            phase="explore",
                            message=f"Table {table} missing column {col}",
                        )
                    )
    finally:
        conn.close()
    return issues


def validate_explore(
    workspace: Path,
    hypothesis_id: str,
    *,
    db_path: Path,
    plan: AnalysisPlan,
    data_dir: Optional[Path] = None,
    recorded_artifacts: Optional[List[str]] = None,
) -> ValidationResult:
    issues: List = []
    if not db_path.exists():
        issues.append(
            issue(
                "db_missing",
                phase="explore",
                message=f"sqlite.db not found: {db_path}",
            )
        )
        return blocked(issues)

    conn = sqlite3.connect(str(db_path))
    try:
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
        available = {row[0] for row in cursor.fetchall()}
    finally:
        conn.close()

    for table in plan.target_tables:
        quoted = '"' + table.replace('"', '""') + '"'
        if table not in available:
            issues.append(
                issue(
                    "target_table_missing",
                    phase="explore",
                    message=f"Target table not in database: {table}",
                )
            )
        else:
            conn = sqlite3.connect(str(db_path))
            try:
                count = conn.execute(f"SELECT COUNT(*) FROM {quoted}").fetchone()[0]
            finally:
                conn.close()
            if count < 1:
                issues.append(
                    issue(
                        "target_table_empty",
                        phase="explore",
                        message=f"Target table {table} has no rows",
                    )
                )

    if recorded_artifacts:
        missing = [p for p in recorded_artifacts if not Path(p).exists()]
        for path in missing:
            issues.append(
                issue(
                    "phase_artifact_missing",
                    phase="explore",
                    message=f"Recorded explore artifact missing: {path}",
                    fix_hint="Re-run run-explore-eda and record-phase-artifacts",
                )
            )
    elif data_dir is not None:
        if not data_dir.exists():
            issues.append(
                issue(
                    "explore_output_dir_missing",
                    phase="explore",
                    message=f"Explore output directory not found: {data_dir}",
                    fix_hint="Run intake and run-explore-eda before validate-explore",
                )
            )
        elif not any(data_dir.iterdir()):
            issues.append(
                issue(
                    "explore_output_empty",
                    phase="explore",
                    message=f"No files under {data_dir}",
                    fix_hint="Run run-explore-eda and record-phase-artifacts with output paths",
                )
            )

    issues.extend(_run_table_checks(db_path, plan))

    if issues:
        return blocked(
            issues, recommended_next_step="Fix data/EDA artifacts then validate-explore"
        )
    return passed()
