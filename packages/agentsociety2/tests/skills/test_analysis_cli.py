"""Tests for the extension analysis CLI helpers."""

from importlib.util import module_from_spec, spec_from_file_location
import json
from pathlib import Path
import sqlite3

import pytest


def _load_analysis_cli_module():
    repo_root = Path(__file__).resolve().parents[4]
    module_path = (
        repo_root
        / "extension"
        / "skills"
        / "agentsociety-analysis"
        / "v1.0.0"
        / "scripts"
        / "analysis.py"
    )
    spec = spec_from_file_location("analysis_cli_test_module", module_path)
    module = module_from_spec(spec)
    assert spec is not None
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


analysis_cli = _load_analysis_cli_module()


def test_validate_plotting_conventions_accepts_publication_scaffold():
    code = """
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

plt.rcParams["font.family"] = "sans-serif"
plt.rcParams["font.sans-serif"] = ["Arial", "DejaVu Sans"]
plt.rcParams["svg.fonttype"] = "none"
"""
    analysis_cli._validate_plotting_conventions(code)


def test_validate_plotting_conventions_accepts_rcparams_update():
    code = """
import matplotlib as mpl
mpl.use("Agg")
import matplotlib.pyplot as plt

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Arial", "DejaVu Sans"],
    "svg.fonttype": "none",
})
"""
    analysis_cli._validate_plotting_conventions(code)


def test_validate_plotting_conventions_requires_scaffold():
    code = """
import matplotlib.pyplot as plt

fig, ax = plt.subplots()
"""
    with pytest.raises(ValueError) as exc_info:
        analysis_cli._validate_plotting_conventions(code)

    assert 'matplotlib backend configured to "Agg"' in str(exc_info.value)
    assert '`svg.fonttype = "none"`' in str(exc_info.value)


def test_filter_assets_with_companions_keeps_same_stem_vector_exports():
    class Asset:
        def __init__(self, file_path: str):
            self.file_path = file_path

    assets = [
        Asset("/tmp/chart_01_growth.png"),
        Asset("/tmp/chart_01_growth.svg"),
        Asset("/tmp/chart_02_other.png"),
    ]

    filtered = analysis_cli._filter_assets_with_companions(
        assets,
        {"chart_01_growth.png"},
    )

    assert [Path(asset.file_path).name for asset in filtered] == [
        "chart_01_growth.png",
        "chart_01_growth.svg",
    ]


def test_load_context_parser_defaults_workspace_from_env(monkeypatch, tmp_path):
    monkeypatch.setenv("AGENTSOCIETY_WORKSPACE", str(tmp_path))

    parser = analysis_cli._build_parser()
    args = parser.parse_args(
        ["load-context", "--hypothesis-id", "1", "--experiment-id", "2"]
    )

    assert Path(args.workspace) == tmp_path.resolve()


def test_experience_memory_commands_parse(tmp_path):
    parser = analysis_cli._build_parser()

    draft = parser.parse_args(
        [
            "draft-reflection",
            "--workspace",
            str(tmp_path),
            "--hypothesis-id",
            "1",
            "--experiment-id",
            "2",
        ]
    )
    assert draft.command == "draft-reflection"

    record = parser.parse_args(
        [
            "record-reflection",
            "--workspace",
            str(tmp_path),
            "--hypothesis-id",
            "1",
            "--payload",
            "{}",
        ]
    )
    assert record.command == "record-reflection"

    promote = parser.parse_args(
        [
            "promote-reflection",
            "--workspace",
            str(tmp_path),
            "--hypothesis-id",
            "1",
            "--include-preferences",
        ]
    )
    assert promote.command == "promote-reflection"
    assert promote.include_preferences is True

    context = parser.parse_args(
        [
            "memory-context",
            "--workspace",
            str(tmp_path),
            "--hypothesis-id",
            "1",
        ]
    )
    assert context.command == "memory-context"

    feedback = parser.parse_args(
        [
            "record-feedback",
            "--workspace",
            str(tmp_path),
            "--hypothesis-id",
            "1",
            "--payload",
            "{}",
        ]
    )
    assert feedback.command == "record-feedback"

    review = parser.parse_args(
        [
            "review-reflection",
            "--workspace",
            str(tmp_path),
            "--hypothesis-id",
            "1",
            "--include-preferences",
        ]
    )
    assert review.command == "review-reflection"
    assert review.include_preferences is True


def _run_harness_cli(capsys, *args):
    parser = analysis_cli._build_parser()
    namespace = parser.parse_args(list(args))
    rc = analysis_cli._dispatch_harness(namespace)
    output = capsys.readouterr().out.strip()
    assert rc == 0
    payload = json.loads(output)
    assert payload["success"] is True
    return payload


def _run_analysis_cli(capsys, *args):
    parser = analysis_cli._build_parser()
    namespace = parser.parse_args(list(args))
    if namespace.command == "run-eda":
        rc = analysis_cli._run_eda(namespace)
    else:
        rc = analysis_cli._dispatch_harness(namespace)
    output = capsys.readouterr().out.strip()
    assert rc == 0
    payload = json.loads(output)
    assert payload["success"] is True
    return payload


def test_analysis_experience_memory_cli_smoke(tmp_path, capsys):
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    _run_harness_cli(
        capsys,
        "intake",
        "--workspace",
        str(workspace),
        "--hypothesis-id",
        "1",
        "--experiment-id",
        "1",
    )
    _run_harness_cli(
        capsys,
        "write-plan",
        "--workspace",
        str(workspace),
        "--hypothesis-id",
        "1",
        "--payload",
        json.dumps(
            {
                "research_question": "Does treatment increase value?",
                "primary_metrics": ["value"],
                "target_tables": ["metrics"],
                "confirmatory_claims": ["Treatment increases value"],
            }
        ),
    )
    _run_harness_cli(
        capsys,
        "record-claim",
        "--workspace",
        str(workspace),
        "--hypothesis-id",
        "1",
        "--payload",
        json.dumps(
            {
                "claim_id": "c1",
                "statement": "Treatment increases value",
                "mode": "confirmatory",
                "approved": True,
            }
        ),
    )

    draft = _run_harness_cli(
        capsys,
        "draft-reflection",
        "--workspace",
        str(workspace),
        "--hypothesis-id",
        "1",
        "--experiment-id",
        "1",
    )
    assert Path(draft["reflection_path"]).exists()

    promoted = _run_harness_cli(
        capsys,
        "promote-reflection",
        "--workspace",
        str(workspace),
        "--hypothesis-id",
        "1",
    )

    memory_dir = Path(promoted["memory_dir"])
    assert (memory_dir / "project_lessons.jsonl").exists()
    assert any((memory_dir / "method_recipes").glob("*.md"))
    assert promoted["preference_keys"] == []

    context = _run_harness_cli(
        capsys,
        "memory-context",
        "--workspace",
        str(workspace),
        "--hypothesis-id",
        "1",
    )["memory_context"]
    assert context["active"] is True
    assert context["method_recipes"]

    loop = _run_harness_cli(
        capsys,
        "run-loop",
        "--workspace",
        str(workspace),
        "--hypothesis-id",
        "1",
        "--experiment-id",
        "1",
    )
    assert loop["memory_context"]["active"] is True
    assert loop["recommended_next_step"].startswith("0. Memory:")


def test_feedback_and_review_guard_preference_promotion(tmp_path, capsys):
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    _run_harness_cli(
        capsys,
        "record-reflection",
        "--workspace",
        str(workspace),
        "--hypothesis-id",
        "1",
        "--payload",
        json.dumps(
            {
                "hypothesis_id": "1",
                "experiment_id": "1",
                "what_worked": [
                    {
                        "title": "Concise reports worked",
                        "content": "Short summaries were easier to review.",
                        "evidence": ["report_zh.md"],
                    }
                ],
                "user_preferences_observed": [
                    {
                        "item_id": "report_style",
                        "title": "Report style",
                        "category": "writing",
                        "value": "concise",
                        "content": "Prefer concise reports.",
                        "evidence": [],
                    }
                ],
            }
        ),
    )

    blocked = _run_harness_cli(
        capsys,
        "promote-reflection",
        "--workspace",
        str(workspace),
        "--hypothesis-id",
        "1",
        "--include-preferences",
    )
    assert blocked["status"] == "BLOCKED"
    assert blocked["error"] == "reflection_review_blocked"

    _run_harness_cli(
        capsys,
        "record-feedback",
        "--workspace",
        str(workspace),
        "--hypothesis-id",
        "1",
        "--payload",
        json.dumps(
            {
                "hypothesis_id": "1",
                "experiment_id": "1",
                "rating": 5,
                "satisfied": True,
                "comments": "请长期保持简洁报告风格。",
                "preference_candidates": [
                    {
                        "item_id": "report_style",
                        "title": "Report style",
                        "category": "writing",
                        "value": "concise",
                        "content": "User explicitly asked for concise reports.",
                        "evidence": ["feedback:user-confirmed"],
                        "confidence": "high",
                    }
                ],
            }
        ),
    )

    review = _run_harness_cli(
        capsys,
        "review-reflection",
        "--workspace",
        str(workspace),
        "--hypothesis-id",
        "1",
        "--include-preferences",
    )
    assert review["review"]["verdict"] == "PASS"

    promoted = _run_harness_cli(
        capsys,
        "promote-reflection",
        "--workspace",
        str(workspace),
        "--hypothesis-id",
        "1",
        "--include-preferences",
    )
    assert promoted["preference_keys"] == ["report_style"]


def test_synthetic_analysis_workflow_evolves_memory(tmp_path, capsys):
    workspace = tmp_path / "workspace"
    db_path = workspace / "hypothesis_1" / "experiment_1" / "run" / "sqlite.db"
    db_path.parent.mkdir(parents=True)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE metrics (
                agent_id INTEGER,
                step INTEGER,
                treatment INTEGER,
                value REAL
            )
            """
        )
        rows = []
        for agent_id in range(1, 13):
            treatment = 1 if agent_id > 6 else 0
            for step in range(1, 5):
                baseline = 10 + step
                lift = 4.5 if treatment else 0.0
                rows.append((agent_id, step, treatment, baseline + lift + agent_id / 20))
        conn.executemany("INSERT INTO metrics VALUES (?, ?, ?, ?)", rows)

    _run_analysis_cli(
        capsys,
        "intake",
        "--workspace",
        str(workspace),
        "--hypothesis-id",
        "1",
        "--experiment-id",
        "1",
    )
    _run_analysis_cli(
        capsys,
        "write-plan",
        "--workspace",
        str(workspace),
        "--hypothesis-id",
        "1",
        "--payload",
        json.dumps(
            {
                "research_question": "Does treatment increase simulated value?",
                "primary_metrics": ["value", "treatment"],
                "target_tables": ["metrics"],
                "confirmatory_claims": [
                    "Treatment agents have higher mean value than controls"
                ],
                "eda_profile": "quick-stats",
                "table_checks": [
                    {"table": "metrics", "min_rows": 24, "columns": ["value"]}
                ],
            }
        ),
    )
    _run_analysis_cli(
        capsys,
        "record-attestation",
        "--workspace",
        str(workspace),
        "--hypothesis-id",
        "1",
        "--payload",
        json.dumps(
            {
                "phase": "frame",
                "status": "DONE",
                "key_findings": ["Synthetic AB test plan is ready"],
                "rubric": {
                    "research_question_confirmed": True,
                    "success_criteria": "Compare treatment vs control mean value",
                },
            }
        ),
    )
    assert (
        _run_analysis_cli(
            capsys,
            "validate-plan",
            "--workspace",
            str(workspace),
            "--hypothesis-id",
            "1",
        )["status"]
        == "PASS"
    )

    data_dir = workspace / "presentation" / "hypothesis_1" / "data"
    eda = _run_analysis_cli(
        capsys,
        "run-eda",
        "--workspace",
        str(workspace),
        "--hypothesis-id",
        "1",
        "--db-path",
        str(db_path),
        "--output-dir",
        str(data_dir),
        "--type",
        "quick-stats",
        "--tables",
        "metrics",
    )
    assert Path(eda["files"][0]).name == "eda_quick_stats.md"

    _run_analysis_cli(
        capsys,
        "record-attestation",
        "--workspace",
        str(workspace),
        "--hypothesis-id",
        "1",
        "--payload",
        json.dumps(
            {
                "phase": "explore",
                "status": "DONE",
                "key_findings": ["metrics table has synthetic treatment contrast"],
                "artifacts_written": ["presentation/hypothesis_1/data/eda_quick_stats.md"],
                "rubric": {
                    "tables_inspected": ["metrics"],
                    "data_limitations": "Synthetic fixture; not external evidence",
                    "eda_takeaway": "Treatment rows have visibly higher values",
                },
            }
        ),
    )
    assert (
        _run_analysis_cli(
            capsys,
            "validate-explore",
            "--workspace",
            str(workspace),
            "--hypothesis-id",
            "1",
            "--experiment-id",
            "1",
        )["status"]
        == "PASS"
    )

    _run_analysis_cli(
        capsys,
        "record-claim",
        "--workspace",
        str(workspace),
        "--hypothesis-id",
        "1",
        "--payload",
        json.dumps(
            {
                "claim_id": "c1",
                "statement": "Treatment agents have higher mean value",
                "mode": "confirmatory",
                "evidence": "metrics grouped by treatment",
                "needs_chart": True,
                "approved": True,
            }
        ),
    )
    _run_analysis_cli(
        capsys,
        "record-attestation",
        "--workspace",
        str(workspace),
        "--hypothesis-id",
        "1",
        "--payload",
        json.dumps(
            {
                "phase": "claims",
                "status": "DONE",
                "key_findings": ["Confirmatory claim approved for fixture"],
                "rubric": {
                    "claims_user_approved": True,
                    "confirmatory_vs_exploratory_clear": True,
                },
            }
        ),
    )
    assert (
        _run_analysis_cli(
            capsys,
            "validate-claims",
            "--workspace",
            str(workspace),
            "--hypothesis-id",
            "1",
        )["status"]
        == "PASS"
    )

    chart_path = (
        workspace
        / "presentation"
        / "hypothesis_1"
        / "charts"
        / "chart_01_treatment_value.png"
    )
    chart_path.parent.mkdir(parents=True, exist_ok=True)
    chart_path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"synthetic-chart" * 20)
    _run_analysis_cli(
        capsys,
        "record-contract",
        "--workspace",
        str(workspace),
        "--hypothesis-id",
        "1",
        "--payload",
        json.dumps(
            {
                "contract_id": "f1",
                "claim_id": "c1",
                "core_finding": "Treatment raises simulated value",
                "output_files": [str(chart_path)],
            }
        ),
    )
    _run_analysis_cli(
        capsys,
        "validate-chart",
        "--workspace",
        str(workspace),
        "--hypothesis-id",
        "1",
        "--chart-path",
        str(chart_path),
    )
    _run_analysis_cli(
        capsys,
        "record-attestation",
        "--workspace",
        str(workspace),
        "--hypothesis-id",
        "1",
        "--payload",
        json.dumps(
            {
                "phase": "refine",
                "status": "DONE",
                "key_findings": ["Chart maps directly to approved claim"],
                "rubric": {
                    "charts_map_to_claims": True,
                    "visual_message_clear": True,
                },
            }
        ),
    )
    assert (
        _run_analysis_cli(
            capsys,
            "validate-refine",
            "--workspace",
            str(workspace),
            "--hypothesis-id",
            "1",
        )["status"]
        == "PASS"
    )

    reflection = _run_analysis_cli(
        capsys,
        "draft-reflection",
        "--workspace",
        str(workspace),
        "--hypothesis-id",
        "1",
        "--experiment-id",
        "1",
    )["reflection"]
    assert "frame" in reflection["what_worked"][0]["content"]
    assert reflection["reusable_methods"][0]["recommended_steps"]

    promoted = _run_analysis_cli(
        capsys,
        "promote-reflection",
        "--workspace",
        str(workspace),
        "--hypothesis-id",
        "1",
    )
    lessons = (
        workspace / ".agentsociety" / "memory" / "project_lessons.jsonl"
    ).read_text(encoding="utf-8")
    recipe = next((workspace / ".agentsociety" / "memory" / "method_recipes").glob("*.md"))
    assert "Phase gates passed" in lessons
    assert "Does treatment increase simulated value" in recipe.read_text(
        encoding="utf-8"
    )
    assert promoted["preference_keys"] == []

    loop = _run_analysis_cli(
        capsys,
        "run-loop",
        "--workspace",
        str(workspace),
        "--hypothesis-id",
        "1",
        "--experiment-id",
        "1",
    )
    assert loop["memory_context"]["active"] is True
    assert loop["memory_context"]["recent_lessons"]
    assert loop["memory_context"]["method_recipes"]
    assert loop["recommended_next_step"].startswith("0. Memory:")


def test_compose_figure_grid_layout(tmp_path):
    image_module = pytest.importorskip("PIL.Image")

    chart_a = tmp_path / "chart_01_a.png"
    chart_b = tmp_path / "chart_02_b.png"
    image_module.new("RGB", (320, 200), "#ccddee").save(chart_a)
    image_module.new("RGB", (180, 260), "#f4c095").save(chart_b)

    spec_path = tmp_path / "figure_01_summary.json"
    spec_path.write_text(
        json.dumps(
            {
                "output": "figure_01_summary.png",
                "canvas": {"width": 1000, "height": 700, "background": "#FFFFFF"},
                "layout": {"type": "grid", "rows": 1, "cols": 2, "padding": 40, "gap": 20},
                "panels": [
                    {"source": chart_a.name, "label": "a"},
                    {"source": chart_b.name, "label": "b"},
                ],
            }
        ),
        encoding="utf-8",
    )

    result = analysis_cli._compose_figure(spec_path)

    output_path = Path(result["output"])
    metadata_path = Path(result["metadata"])
    assert output_path.exists()
    assert metadata_path.exists()

    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert metadata["layout"]["type"] == "grid"
    assert [panel["label"] for panel in metadata["panels"]] == ["a", "b"]


def test_compose_figure_manual_layout_writes_output(tmp_path):
    image_module = pytest.importorskip("PIL.Image")

    chart_path = tmp_path / "chart_01_main.png"
    image_module.new("RGB", (400, 240), "#9ec5ab").save(chart_path)

    spec_path = tmp_path / "figure_02_manual.json"
    spec_path.write_text(
        json.dumps(
            {
                "output": "figure_02_manual.png",
                "layout": {"type": "manual"},
                "panels": [
                    {
                        "source": chart_path.name,
                        "label": "a",
                        "box": {"x": 60, "y": 60, "width": 500, "height": 300},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    result = analysis_cli._compose_figure(spec_path)
    assert Path(result["output"]).exists()
