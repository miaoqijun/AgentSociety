"""Output helpers for the analysis tool layer."""

from __future__ import annotations

import base64
import mimetypes
import shutil
from dataclasses import dataclass
from hashlib import sha1
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    import pandas as pd
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    pd = None

from agentsociety2.logger import get_logger

from .models import (
    DIR_ARTIFACTS,
    DIR_EXPERIMENT_PREFIX,
    DIR_HYPOTHESIS_PREFIX,
    DIR_REPORT_ASSETS,
    DIR_RUN,
    SUPPORTED_IMAGE_FORMATS,
    ReportAsset,
)
from .utils import _sanitize_id

logger = get_logger()


@dataclass
class ReportPaths:
    """Report file paths."""

    markdown: Path
    html: Path
    markdown_zh: Optional[Path] = None
    html_zh: Optional[Path] = None
    markdown_en: Optional[Path] = None
    html_en: Optional[Path] = None
    assets_dir: Optional[Path] = None


class AssetManager:
    """Discover and normalize analysis assets."""

    def __init__(self, workspace_path: Path):
        self.workspace_path = Path(workspace_path)
        self.logger = logger

    def discover_assets(
        self,
        experiment_id: str,
        hypothesis_id: str,
    ) -> List[ReportAsset]:
        """Discover image assets under `run/artifacts`."""

        hid = _sanitize_id(hypothesis_id)
        eid = _sanitize_id(experiment_id)
        asset_path = (
            self.workspace_path
            / f"{DIR_HYPOTHESIS_PREFIX}{hid}"
            / f"{DIR_EXPERIMENT_PREFIX}{eid}"
            / DIR_RUN
            / DIR_ARTIFACTS
        )

        assets: List[ReportAsset] = []
        if not asset_path.exists():
            return assets

        for file_path in asset_path.rglob("*"):
            if file_path.suffix.lower() not in SUPPORTED_IMAGE_FORMATS:
                continue
            relative_path = file_path.relative_to(asset_path)
            assets.append(
                ReportAsset(
                    asset_id=self._build_asset_id("viz", relative_path),
                    asset_type="visualization",
                    title=self._format_title(file_path.stem),
                    file_path=str(file_path),
                    description=f"Generated visualization: {relative_path.as_posix()}",
                    file_size=file_path.stat().st_size,
                )
            )

        return assets

    def process_assets(
        self,
        assets: List[ReportAsset],
        output_dir: Path,
    ) -> Dict[str, Any]:
        """Copy assets into `assets/` and generate optional base64 payloads."""

        assets_dir = output_dir / DIR_REPORT_ASSETS
        assets_dir.mkdir(exist_ok=True)
        processed: Dict[str, Any] = {}
        used_names: set[str] = set()

        for asset in assets:
            source_path = Path(asset.file_path)
            if not source_path.exists():
                continue

            dest_name = self._build_unique_dest_name(source_path, asset.asset_id, used_names)
            dest_path = assets_dir / dest_name
            if source_path.resolve() != dest_path.resolve():
                shutil.copy2(source_path, dest_path)

            embedded = None
            if source_path.suffix.lower() in SUPPORTED_IMAGE_FORMATS:
                with open(source_path, "rb") as file_handle:
                    encoded = base64.b64encode(file_handle.read()).decode("utf-8")
                    mime = (mimetypes.guess_type(source_path.name) or ("image/png", None))[0]
                    embedded = f"data:{mime};base64,{encoded}"

            processed[asset.asset_id] = {
                "title": asset.title,
                "local_path": str(dest_path),
                "relative_path": f"{DIR_REPORT_ASSETS}/{dest_name}",
                "embedded_data": embedded,
                "description": asset.description,
            }

        return processed

    def _build_asset_id(self, prefix: str, relative_path: Path) -> str:
        normalized = relative_path.as_posix()
        digest = sha1(normalized.encode("utf-8")).hexdigest()[:10]
        return f"{prefix}_{relative_path.stem}_{digest}"

    def _build_unique_dest_name(
        self,
        source_path: Path,
        asset_id: str,
        used_names: set[str],
    ) -> str:
        candidate = source_path.name
        if candidate not in used_names:
            used_names.add(candidate)
            return candidate

        suffix = source_path.suffix
        stem = source_path.stem
        unique_name = f"{stem}_{asset_id[-10:]}{suffix}"
        counter = 1
        while unique_name in used_names:
            unique_name = f"{stem}_{asset_id[-10:]}_{counter}{suffix}"
            counter += 1
        used_names.add(unique_name)
        return unique_name

    def _format_title(self, filename: str) -> str:
        title = filename.replace("_", " ").replace("-", " ")
        return " ".join(word.capitalize() for word in title.split())


AssetProcessor = AssetManager


class EDAGenerator:
    """Generate exploratory data analysis artifacts."""

    def __init__(self):
        self.logger = logger

    def resolve_table_selection(
        self,
        reader,
        tables: Optional[List[str]],
    ) -> Tuple[List[str], List[str], List[str]]:
        """Return requested, selected, and invalid table names."""

        available_tables = reader.read_schema().tables
        if tables is None:
            return available_tables, available_tables, []

        requested_tables: List[str] = []
        seen = set()
        for table in tables:
            name = (table or "").strip()
            if not name or name in seen:
                continue
            seen.add(name)
            requested_tables.append(name)

        available_set = set(available_tables)
        selected_tables = [table for table in requested_tables if table in available_set]
        invalid_tables = [table for table in requested_tables if table not in available_set]
        return requested_tables, selected_tables, invalid_tables

    def _resolve_tables(self, reader, tables: Optional[List[str]]) -> List[str]:
        _, selected_tables, _ = self.resolve_table_selection(reader, tables)
        return selected_tables

    def generate_quick_stats(
        self,
        db_path: Path,
        max_rows: int = 5000,
        tables: Optional[List[str]] = None,
    ) -> Optional[str]:
        if not db_path.exists():
            return None

        from .data import DataReader, DatabaseSchema

        reader = DataReader(db_path)
        schema = reader.read_schema()
        selected_tables = self._resolve_tables(reader, tables)
        filtered_schema = DatabaseSchema(
            tables=selected_tables,
            columns={table: schema.columns.get(table, []) for table in selected_tables},
            row_counts={table: schema.row_counts.get(table, 0) for table in selected_tables},
            markdown=schema.markdown,
        )
        stats = reader.compute_stats(filtered_schema)

        return stats.quick_stats_md

    def generate_missingno_report(
        self,
        db_path: Path,
        output_dir: Path,
        max_rows: int = 50000,
        tables: Optional[List[str]] = None,
    ) -> Optional[Path]:
        """Generate a missing-value report with missingno."""

        if not db_path.exists():
            return None

        from .data import DataReader

        reader = DataReader(db_path)
        selected_tables = self._resolve_tables(reader, tables)
        sample = reader.read_sample_data(tables=selected_tables, limit=max_rows)

        if not sample:
            return None
        if pd is None:
            self.logger.warning("pandas 未安装，跳过 missingno 报告生成")
            return None

        all_dfs = []
        for table_name, data in sample.items():
            if data and len(data) > 0:
                df = pd.DataFrame(data)
                df.columns = [f"{table_name}.{col}" for col in df.columns]
                all_dfs.append(df)

        if not all_dfs:
            return None

        combined_df = pd.concat(all_dfs, axis=1)
        if len(combined_df.columns) > 50:
            missing_counts = combined_df.isnull().sum()
            top_missing = missing_counts.nlargest(50).index.tolist()
            combined_df = combined_df[top_missing]

        output_dir.mkdir(parents=True, exist_ok=True)

        try:
            import matplotlib.pyplot as plt
            import missingno as msno

            out_file = output_dir / "eda_missingno.html"

            fig, axes = plt.subplots(2, 2, figsize=(16, 12))

            try:
                msno.matrix(combined_df, ax=axes[0, 0], fontsize=8)
                axes[0, 0].set_title("Missing Value Matrix", fontsize=12)
            except Exception:
                axes[0, 0].text(0.5, 0.5, "Matrix plot failed", ha="center", va="center")
                axes[0, 0].set_title("Missing Value Matrix (Error)")

            try:
                msno.bar(combined_df, ax=axes[0, 1], fontsize=8)
                axes[0, 1].set_title("Missing Value Bar Chart", fontsize=12)
            except Exception:
                axes[0, 1].text(0.5, 0.5, "Bar plot failed", ha="center", va="center")
                axes[0, 1].set_title("Missing Value Bar (Error)")

            try:
                if len(combined_df.columns) > 1:
                    msno.heatmap(combined_df, ax=axes[1, 0], fontsize=8)
                    axes[1, 0].set_title("Missing Value Correlation Heatmap", fontsize=12)
                else:
                    axes[1, 0].text(0.5, 0.5, "Need >1 columns", ha="center", va="center")
                    axes[1, 0].set_title("Correlation Heatmap (Skipped)")
            except Exception:
                axes[1, 0].text(0.5, 0.5, "Heatmap failed", ha="center", va="center")
                axes[1, 0].set_title("Correlation Heatmap (Error)")

            try:
                if len(combined_df.columns) > 1:
                    msno.dendrogram(combined_df, ax=axes[1, 1], fontsize=8)
                    axes[1, 1].set_title("Missing Value Dendrogram", fontsize=12)
                else:
                    axes[1, 1].text(0.5, 0.5, "Need >1 columns", ha="center", va="center")
                    axes[1, 1].set_title("Dendrogram (Skipped)")
            except Exception:
                axes[1, 1].text(0.5, 0.5, "Dendrogram failed", ha="center", va="center")
                axes[1, 1].set_title("Dendrogram (Error)")

            plt.tight_layout()
            plt.savefig(str(out_file).replace(".html", ".png"), dpi=150, bbox_inches="tight")
            plt.close()

            html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Missing Value Analysis (missingno)</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 40px; }}
        h1 {{ color: #333; }}
        .summary {{ background: #f5f5f5; padding: 15px; border-radius: 5px; margin: 20px 0; }}
        .stats {{ margin-top: 10px; }}
        img {{ max-width: 100%; height: auto; margin: 20px 0; border: 1px solid #ddd; }}
    </style>
</head>
<body>
    <h1>Missing Value Analysis</h1>
    <div class="summary">
        <p><strong>Tool</strong>: missingno - Missing data visualization</p>
        <p><strong>Total Columns Analyzed</strong>: {len(combined_df.columns)}</p>
        <p><strong>Total Rows</strong>: {len(combined_df)}</p>
        <div class="stats">
            <p><strong>Total Missing Values</strong>: {combined_df.isnull().sum().sum()}</p>
            <p><strong>Columns with Missing</strong>: {(combined_df.isnull().sum() > 0).sum()}</p>
        </div>
    </div>
    <img src="eda_missingno.png" alt="Missing Value Visualization">
</body>
</html>"""
            out_file.write_text(html_content, encoding="utf-8")

            self.logger.info("生成 missingno 缺失值报告: %s", out_file)
            return out_file

        except ImportError:
            self.logger.warning("missingno 未安装，跳过缺失值可视化")
            return None
        except Exception as exc:
            self.logger.warning("missingno 生成失败: %s", exc)
            return None

    def generate_correlation_report(
        self,
        db_path: Path,
        output_dir: Path,
        max_rows: int = 50000,
        tables: Optional[List[str]] = None,
    ) -> Optional[Path]:
        """Generate a correlation report."""

        if not db_path.exists():
            return None

        from .data import DataReader

        reader = DataReader(db_path)
        selected_tables = self._resolve_tables(reader, tables)
        sample = reader.read_sample_data(tables=selected_tables, limit=max_rows)

        if not sample:
            return None
        if pd is None:
            self.logger.warning("pandas 未安装，跳过相关性报告生成")
            return None

        output_dir.mkdir(parents=True, exist_ok=True)

        generated_files = []
        for table_name, data in sample.items():
            if not data or len(data) < 2:
                continue

            df = pd.DataFrame(data)
            numeric_df = df.select_dtypes(include=["number"])

            if len(numeric_df.columns) < 2:
                continue

            try:
                import matplotlib.pyplot as plt
                import seaborn as sns

                corr_matrix = numeric_df.corr()

                fig, ax = plt.subplots(figsize=(12, 10))
                sns.heatmap(
                    corr_matrix,
                    annot=True,
                    fmt=".2f",
                    cmap="coolwarm",
                    center=0,
                    square=True,
                    linewidths=0.5,
                    ax=ax,
                )
                ax.set_title(f"Correlation Matrix: {table_name}", fontsize=14)

                safe_name = "".join(c if c.isalnum() or c in "_-" else "_" for c in table_name)
                out_file = output_dir / f"correlation_{safe_name}.png"
                plt.tight_layout()
                plt.savefig(str(out_file), dpi=150, bbox_inches="tight")
                plt.close()

                generated_files.append((table_name, str(out_file)))
                self.logger.info(
                    "生成相关性矩阵: %s (表: %s, %d 列)",
                    out_file,
                    table_name,
                    len(numeric_df.columns),
                )

            except Exception as exc:
                self.logger.warning("生成表 %s 的相关性矩阵失败: %s", table_name, exc)

        if not generated_files:
            return None

        index_file = output_dir / "correlation_index.html"
        rows = "\n".join(
            f'<tr><td>{name}</td><td><img src="{Path(path).name}" style="max-width:800px"></td></tr>'
            for name, path in generated_files
        )
        html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Correlation Analysis</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 40px; }}
        h1 {{ color: #333; }}
        table {{ border-collapse: collapse; width: 100%; }}
        td {{ padding: 20px; border-bottom: 1px solid #ddd; }}
        img {{ max-width: 100%; }}
    </style>
</head>
<body>
    <h1>Correlation Analysis Report</h1>
    <table>
        <tr><th>Table</th><th>Correlation Matrix</th></tr>
        {rows}
    </table>
</body>
</html>"""
        index_file.write_text(html_content, encoding="utf-8")

        return index_file

    def generate_ydata_profile(
        self,
        db_path: Path,
        output_dir: Path,
        max_rows: int = 10000,
        tables: Optional[List[str]] = None,
    ) -> Optional[Path]:
        """Generate a ydata-profiling report."""

        if not db_path.exists():
            return None

        from .data import DataReader

        reader = DataReader(db_path)
        selected_tables = self._resolve_tables(reader, tables)
        sample = reader.read_sample_data(tables=selected_tables, limit=max_rows)

        if not sample:
            return None
        if pd is None:
            self.logger.warning("pandas 未安装，跳过 ydata-profiling 报告生成")
            return None

        non_empty_tables = {
            table_name: data
            for table_name, data in sample.items()
            if data and len(data) > 0
        }

        if not non_empty_tables:
            return None

        output_dir.mkdir(parents=True, exist_ok=True)

        try:
            from ydata_profiling import ProfileReport

            if len(non_empty_tables) == 1:
                table_name = next(iter(non_empty_tables.keys()))
                df = pd.DataFrame(non_empty_tables[table_name])
                out_file = output_dir / "eda_profile.html"
                profile = ProfileReport(df, title=f"EDA: {table_name}", minimal=True)
                profile.to_file(str(out_file))
                self.logger.info(
                    "生成 ydata-profiling 报告: %s (表: %s, %d 行)",
                    out_file,
                    table_name,
                    len(df),
                )
                return out_file

            generated_files = []
            for table_name, data in non_empty_tables.items():
                df = pd.DataFrame(data)
                if df.empty:
                    continue
                safe_name = "".join(c if c.isalnum() or c in "_-" else "_" for c in table_name)
                table_file = output_dir / f"eda_profile_{safe_name}.html"
                try:
                    profile = ProfileReport(df, title=f"EDA: {table_name}", minimal=True)
                    profile.to_file(str(table_file))
                    generated_files.append((table_name, table_file.name, len(df)))
                    self.logger.info(
                        "生成 ydata-profiling 表报告: %s (表: %s, %d 行)",
                        table_file,
                        table_name,
                        len(df),
                    )
                except Exception as exc:
                    self.logger.warning("生成表 %s 的 EDA 报告失败: %s", table_name, exc)

            if not generated_files:
                return None

            index_file = output_dir / "eda_profile.html"
            index_content = self._build_eda_index_html(generated_files, "ydata-profiling")
            index_file.write_text(index_content, encoding="utf-8")
            self.logger.info("生成 EDA 索引页: %s (%d 张表)", index_file, len(generated_files))
            return index_file

        except Exception as exc:
            self.logger.debug("ydata-profiling 生成失败: %s", exc)
            return None

    def _build_eda_index_html(
        self,
        table_files: List[Tuple[str, str, int]],
        tool_name: str,
    ) -> str:
        rows = "\n".join(
            f'<tr><td><a href="{filename}">{name}</a></td><td>{row_count}</td></tr>'
            for name, filename, row_count in table_files
        )
        return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>EDA Reports Index</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 40px; }}
        h1 {{ color: #333; }}
        table {{ border-collapse: collapse; width: 100%; max-width: 600px; margin-top: 20px; }}
        th, td {{ border: 1px solid #ddd; padding: 12px; text-align: left; }}
        th {{ background-color: #f5f5f5; }}
        tr:hover {{ background-color: #f9f9f9; }}
        a {{ color: #1890ff; text-decoration: none; }}
        a:hover {{ text-decoration: underline; }}
        .info {{ color: #666; margin-top: 10px; }}
    </style>
</head>
<body>
    <h1>EDA Reports Index ({tool_name})</h1>
    <p class="info">Click on a table name to view its EDA report.</p>
    <table>
        <tr><th>Table</th><th>Rows</th></tr>
{rows}
    </table>
</body>
</html>"""

    def generate_sweetviz_profile(
        self,
        db_path: Path,
        output_dir: Path,
        max_rows: int = 10000,
        tables: Optional[List[str]] = None,
    ) -> Optional[Path]:
        """Generate a Sweetviz report."""

        if not db_path.exists():
            return None

        from .data import DataReader

        reader = DataReader(db_path)
        selected_tables = self._resolve_tables(reader, tables)
        sample = reader.read_sample_data(tables=selected_tables, limit=max_rows)

        if not sample:
            return None
        if pd is None:
            self.logger.warning("pandas 未安装，跳过 Sweetviz 报告生成")
            return None

        non_empty_tables = {
            table_name: data
            for table_name, data in sample.items()
            if data and len(data) > 0
        }

        if not non_empty_tables:
            return None

        output_dir.mkdir(parents=True, exist_ok=True)

        try:
            import sweetviz as sv

            if len(non_empty_tables) == 1:
                table_name = next(iter(non_empty_tables.keys()))
                df = pd.DataFrame(non_empty_tables[table_name])
                out_file = output_dir / "eda_sweetviz.html"
                report = sv.analyze(df)
                report.show_html(str(out_file), open_browser=False)
                if out_file.exists():
                    self.logger.info(
                        "生成 Sweetviz 报告: %s (表: %s, %d 行)",
                        out_file,
                        table_name,
                        len(df),
                    )
                    return out_file
                return None

            generated_files = []
            for table_name, data in non_empty_tables.items():
                df = pd.DataFrame(data)
                if df.empty:
                    continue
                safe_name = "".join(c if c.isalnum() or c in "_-" else "_" for c in table_name)
                table_file = output_dir / f"eda_sweetviz_{safe_name}.html"
                try:
                    report = sv.analyze(df)
                    report.show_html(str(table_file), open_browser=False)
                    if table_file.exists():
                        generated_files.append((table_name, table_file.name, len(df)))
                        self.logger.info(
                            "生成 Sweetviz 表报告: %s (表: %s, %d 行)",
                            table_file,
                            table_name,
                            len(df),
                        )
                except Exception as exc:
                    self.logger.warning("生成表 %s 的 Sweetviz 报告失败: %s", table_name, exc)

            if not generated_files:
                return None

            index_file = output_dir / "eda_sweetviz.html"
            index_content = self._build_eda_index_html(generated_files, "Sweetviz")
            index_file.write_text(index_content, encoding="utf-8")
            self.logger.info(
                "生成 Sweetviz EDA 索引页: %s (%d 张表)",
                index_file,
                len(generated_files),
            )
            return index_file

        except Exception as exc:
            self.logger.debug("Sweetviz 生成失败: %s", exc)
            return None
