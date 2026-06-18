"""Tests for the analysis harness validators and state."""

import json
import sqlite3
from pathlib import Path

import pytest

from agentsociety2.skills.analysis.harness import state as harness_state
from agentsociety2.skills.analysis.harness.models import (
    AnalysisPlan,
    Claim,
    ClaimsDocument,
    ClaimMode,
    FigureContract,
    HypothesisAnalysisState,
    ReflectionReport,
)
from agentsociety2.skills.analysis.harness.review import (
    REPORT_DIMENSION_KEYS,
    report_content_fingerprint,
    save_report_review,
)
from agentsociety2.skills.analysis.harness.schemas import (
    ReportQualityReview,
    ReviewVerdict,
)
from agentsociety2.skills.analysis.harness.report_assets import (
    sync_report_assets_from_reports,
)
from agentsociety2.skills.analysis.harness.validators import (
    validate_chart_script,
    validate_claims,
    validate_explore,
    validate_plan,
    validate_refine,
    validate_release,
    validate_report_quality,
    validate_synthesis,
)
from agentsociety2.skills.analysis.harness import cli as harness_cli
from agentsociety2.skills.analysis.harness.json_io import load_model_from_text
from agentsociety2.skills.analysis.harness.schemas import ReportOutline


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "workspace"
    ws.mkdir()
    db_path = ws / "hypothesis_1" / "experiment_1" / "run" / "sqlite.db"
    db_path.parent.mkdir(parents=True)
    conn = sqlite3.connect(str(db_path))
    conn.execute("CREATE TABLE metrics (step INTEGER, value REAL)")
    conn.executemany("INSERT INTO metrics VALUES (?, ?)", [(1, 1.0), (2, 2.0)])
    conn.commit()
    conn.close()

    data_dir = ws / "presentation" / "hypothesis_1" / "data"
    data_dir.mkdir(parents=True)
    (data_dir / "eda_quick_stats.md").write_text("# quick stats\n", encoding="utf-8")
    return ws


def test_validate_plan_blocks_empty(workspace: Path) -> None:
    result = validate_plan(AnalysisPlan())
    assert result.status == "BLOCKED"
    assert any(i.code == "missing_research_question" for i in result.issues)


def _minimal_report_html(lang: str = "zh") -> str:
    title = "Overview" if lang == "en" else "概述"
    return (
        f'<!DOCTYPE html><html lang="{lang}"><head><meta charset="utf-8"/></head>'
        f"<body><h1>{title}</h1><h2>Data</h2><h2>Findings</h2>"
        f'<img src="assets/chart_01_test.png" alt="c"/>'
        f"<h2>Conclusion</h2></body></html>"
    )


def test_validate_plan_passes_minimal(workspace: Path) -> None:
    plan = AnalysisPlan(
        research_question="Does treatment increase metric?",
        primary_metrics=["value"],
        target_tables=["metrics"],
        confirmatory_claims=["Treatment raises mean value"],
    )
    result = validate_plan(plan)
    assert result.status == "PASS"


def test_validate_explore_requires_eda_artifact(workspace: Path) -> None:
    plan = AnalysisPlan(
        research_question="q",
        primary_metrics=["value"],
        target_tables=["metrics"],
        confirmatory_claims=["c"],
        eda_profile="quick-stats",
    )
    db = workspace / "hypothesis_1" / "experiment_1" / "run" / "sqlite.db"
    result = validate_explore(workspace, "1", db_path=db, plan=plan)
    assert result.status == "PASS"


def test_validate_explore_missing_eda(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    db_path = ws / "hypothesis_1" / "experiment_1" / "run" / "sqlite.db"
    db_path.parent.mkdir(parents=True)
    conn = sqlite3.connect(str(db_path))
    conn.execute("CREATE TABLE metrics (value REAL)")
    conn.execute("INSERT INTO metrics VALUES (1.0)")
    conn.commit()
    conn.close()
    data_dir = ws / "presentation" / "hypothesis_1" / "data"
    data_dir.mkdir(parents=True)
    plan = AnalysisPlan(
        research_question="q",
        primary_metrics=["value"],
        target_tables=["metrics"],
        confirmatory_claims=["c"],
        eda_profile="ydata",
    )
    result = validate_explore(
        ws, "1", db_path=db_path, plan=plan, data_dir=data_dir, recorded_artifacts=[]
    )
    assert result.status == "BLOCKED"
    assert any(i.code == "explore_output_empty" for i in result.issues)


def test_validate_explore_missing_output_dir_blocks(workspace: Path) -> None:
    plan = AnalysisPlan(
        research_question="q",
        primary_metrics=["value"],
        target_tables=["metrics"],
        confirmatory_claims=["c"],
    )
    db = workspace / "hypothesis_1" / "experiment_1" / "run" / "sqlite.db"
    result = validate_explore(
        workspace,
        "1",
        db_path=db,
        plan=plan,
        data_dir=workspace / "presentation" / "hypothesis_1" / "missing_data",
    )
    assert result.status == "BLOCKED"
    assert any(i.code == "explore_output_dir_missing" for i in result.issues)


def test_validate_claims_requires_approved_confirmatory() -> None:
    doc = ClaimsDocument(
        hypothesis_id="1",
        claims=[
            Claim(
                claim_id="c1",
                statement="Treatment increases value",
                mode=ClaimMode.confirmatory,
                evidence="metrics table mean comparison",
                approved=False,
            )
        ],
    )
    result = validate_claims(doc)
    assert result.status == "BLOCKED"
    assert any(i.code == "no_approved_confirmatory_claim" for i in result.issues)


def test_validate_refine_requires_contracts_and_validated_charts(
    workspace: Path,
) -> None:
    st = HypothesisAnalysisState(hypothesis_id="1", chart_count=1)
    result = validate_refine(st, workspace, "1")
    assert result.status == "BLOCKED"
    assert any(i.code == "refine_no_contracts" for i in result.issues)

    st = HypothesisAnalysisState(
        hypothesis_id="1",
        figure_contracts=[
            FigureContract(
                contract_id="f1",
                claim_id="c1",
                core_finding="Treatment increases value",
                output_files=["chart_01_value.png"],
            )
        ],
        chart_count=0,
    )
    result = validate_refine(st, workspace, "1")
    assert result.status == "BLOCKED"
    assert any(i.code == "refine_no_validated_charts" for i in result.issues)


def test_validate_chart_deduplicates_chart_count(workspace: Path) -> None:
    harness_cli.cmd_intake(workspace, "1", "1")
    chart = (
        workspace / "presentation" / "hypothesis_1" / "charts" / "chart_01_value.png"
    )
    chart.parent.mkdir(parents=True, exist_ok=True)
    chart.write_bytes(b"\x89PNG\r\n\x1a\n" + b"x" * 200)

    first = harness_cli.cmd_validate_chart(workspace, "1", chart_path=str(chart))
    second = harness_cli.cmd_validate_chart(workspace, "1", chart_path=str(chart))

    assert first["chart_count"] == 1
    assert second["chart_count"] == 1
    st = harness_state.load_hypothesis_state(workspace, "1")
    assert st.phase_artifacts["refine_validated_charts"] == [str(chart.resolve())]


def test_intake_and_write_plan(workspace: Path) -> None:
    out = harness_cli.cmd_intake(workspace, "1", "1")
    assert out["db_ready"] is True
    harness_cli.cmd_write_plan(
        workspace,
        "1",
        {
            "research_question": "Test question",
            "primary_metrics": ["value"],
            "target_tables": ["metrics"],
            "confirmatory_claims": ["Hypothesis holds"],
            "eda_profile": "quick-stats",
        },
    )
    from agentsociety2.skills.analysis.harness.models import (
        AttestationStatus,
    )

    harness_cli.cmd_record_attestation(
        workspace,
        "1",
        {
            "phase": "frame",
            "status": AttestationStatus.DONE.value,
            "key_findings": ["Plan locked"],
            "rubric": {
                "research_question_confirmed": True,
                "success_criteria": "Compare mean value across steps",
            },
        },
    )
    result = harness_cli.cmd_validate_plan(workspace, "1")
    assert result["status"] == "PASS"
    assert result["attestation_pass"] is True


def test_gate_status_only_shows_next_phase_after_current_gate_pass(
    workspace: Path,
) -> None:
    from agentsociety2.skills.analysis.harness.models import AttestationStatus

    harness_cli.cmd_intake(workspace, "1", "1")
    status = harness_cli.cmd_gate_status(workspace, "1")["hypothesis"]
    assert status["current_phase"] == "frame"
    assert status["next_phase"] is None
    assert "structural" in status["blocked_by"]

    harness_cli.cmd_write_plan(
        workspace,
        "1",
        {
            "research_question": "Does treatment increase value?",
            "primary_metrics": ["value"],
            "target_tables": ["metrics"],
            "confirmatory_claims": ["Treatment increases value"],
        },
    )
    harness_cli.cmd_record_attestation(
        workspace,
        "1",
        {
            "phase": "frame",
            "status": AttestationStatus.DONE.value,
            "key_findings": ["Plan approved"],
            "rubric": {
                "research_question_confirmed": True,
                "success_criteria": "Compare value",
            },
        },
    )
    harness_cli.cmd_validate_plan(workspace, "1")

    status = harness_cli.cmd_gate_status(workspace, "1")["hypothesis"]
    assert status["current_gate_pass"] is True
    assert status["blocked_by"] == []
    assert status["next_phase"] == "explore"


def test_phase_attestation_becomes_stale_after_artifact_change(workspace: Path) -> None:
    from agentsociety2.skills.analysis.harness.models import AttestationStatus

    harness_cli.cmd_intake(workspace, "1", "1")
    harness_cli.cmd_write_plan(
        workspace,
        "1",
        {
            "research_question": "Test question",
            "primary_metrics": ["value"],
            "target_tables": ["metrics"],
            "confirmatory_claims": ["Hypothesis holds"],
        },
    )
    harness_cli.cmd_record_attestation(
        workspace,
        "1",
        {
            "phase": "frame",
            "status": AttestationStatus.DONE.value,
            "key_findings": ["Plan approved"],
            "rubric": {
                "research_question_confirmed": True,
                "success_criteria": "Compare metrics",
            },
        },
    )
    assert harness_cli.cmd_validate_plan(workspace, "1")["status"] == "PASS"

    harness_cli.cmd_write_plan(
        workspace,
        "1",
        {"research_question": "Changed question after attestation"},
    )
    result = harness_cli.cmd_validate_plan(workspace, "1")
    assert result["status"] == "BLOCKED"
    assert any(i.get("code") == "attestation_stale" for i in result["issues"])


def test_draft_reflection_creates_reviewable_learning_report(
    workspace: Path,
) -> None:
    harness_cli.cmd_intake(workspace, "1", "1")
    harness_cli.cmd_write_plan(
        workspace,
        "1",
        {
            "research_question": "Does treatment increase value?",
            "primary_metrics": ["value"],
            "target_tables": ["metrics"],
            "confirmatory_claims": ["Treatment increases value"],
        },
    )
    harness_cli.cmd_record_claim(
        workspace,
        "1",
        {
            "claim_id": "c1",
            "statement": "Treatment increases value",
            "mode": "confirmatory",
            "approved": True,
        },
    )

    result = harness_cli.cmd_draft_reflection(workspace, "1", "1")

    assert Path(result["reflection_path"]).exists()
    reflection = ReflectionReport.model_validate(result["reflection"])
    assert reflection.hypothesis_id == "1"
    assert reflection.reusable_methods
    assert any(item.item_id == "approved_claims" for item in reflection.what_worked)


def test_promote_reflection_writes_lessons_recipes_and_confirmed_preferences(
    workspace: Path,
) -> None:
    harness_cli.cmd_record_reflection(
        workspace,
        "1",
        {
            "hypothesis_id": "1",
            "experiment_id": "1",
            "what_worked": [
                {
                    "title": "Conservative claims worked",
                    "content": "User preferred cautious confirmatory claims.",
                    "evidence": ["claims.json"],
                    "confidence": "high",
                }
            ],
            "reusable_methods": [
                {
                    "recipe_id": "cautious_claims",
                    "title": "Cautious claim protocol",
                    "content": "Keep claim strength aligned with evidence.",
                    "recommended_steps": ["Ask for user alignment", "Approve claims"],
                    "pitfalls": ["Do not overclaim"],
                    "confidence": "high",
                }
            ],
            "user_preferences_observed": [
                {
                    "item_id": "claim_style",
                    "title": "Claim style",
                    "content": "Use conservative wording.",
                    "category": "writing",
                    "value": "conservative claims",
                    "evidence": ["user-confirmed"],
                    "confidence": "high",
                }
            ],
        },
    )

    promoted = harness_cli.cmd_promote_reflection(workspace, "1")
    assert promoted["status"] == "PROMOTED"
    assert promoted["preference_keys"] == []

    skipped = harness_cli.cmd_promote_reflection(workspace, "1")
    assert skipped["status"] == "SKIPPED"
    assert skipped["reason"] == "reflection_already_promoted"

    harness_cli.cmd_record_feedback(
        workspace,
        "1",
        {
            "hypothesis_id": "1",
            "experiment_id": "1",
            "rating": 5,
            "satisfied": True,
            "comments": "请长期保持保守表述。",
            "preference_candidates": [
                {
                    "item_id": "claim_style",
                    "title": "Claim style",
                    "category": "writing",
                    "value": "conservative claims",
                    "content": "User confirmed conservative claim wording.",
                    "evidence": ["feedback:user-confirmed"],
                    "confidence": "high",
                }
            ],
        },
    )

    promoted_prefs = harness_cli.cmd_promote_reflection(
        workspace, "1", include_preferences=True
    )
    assert promoted_prefs["status"] == "PROMOTED"
    assert promoted_prefs["already_promoted"] is True

    memory_dir = Path(promoted_prefs["memory_dir"])
    assert (memory_dir / "project_lessons.jsonl").exists()
    assert (memory_dir / "method_recipes" / "cautious_claims.md").exists()
    assert promoted_prefs["preference_keys"] == ["claim_style"]
    index = harness_state.load_memory_index(workspace)
    assert index.preferences["claim_style"].value == "conservative claims"


def test_validate_release_pass(workspace: Path) -> None:
    pres = workspace / "presentation" / "hypothesis_1"
    pres.mkdir(parents=True, exist_ok=True)
    assets = pres / "assets"
    assets.mkdir()
    (assets / "chart_01_test.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"x" * 200)
    (pres / "report_zh.md").write_text(
        "## 概述\n\n## 数据\n\n## 发现\n\n![c](assets/chart_01_test.png)\none line\n\n## 结论\n",
        encoding="utf-8",
    )
    (pres / "report_en.md").write_text(
        "## Overview\n\n## Data\n\n## Findings\n\n![c](assets/chart_01_test.png)\ncaption\n\n## Conclusion\n",
        encoding="utf-8",
    )
    (pres / "report_zh.html").write_text(_minimal_report_html("zh"), encoding="utf-8")
    (pres / "report_en.html").write_text(_minimal_report_html("en"), encoding="utf-8")
    (pres / "artifact_manifest.json").write_text(
        json.dumps(
            {
                "hypothesis_id": "1",
                "artifacts": [
                    {
                        "filename": "chart_01_test.png",
                        "type": "chart",
                        "description": "test",
                        "finding_number": 1,
                        "included_in_report": True,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (pres / "data").mkdir(exist_ok=True)
    (pres / "data" / "analysis_summary.json").write_text(
        json.dumps(
            {
                "summary": "Treatment raises mean metric across steps in simulation.",
                "key_findings": [
                    "Step-wise mean value increases under treatment condition"
                ],
                "limitations": "Single seed ABM; not external validity",
            }
        ),
        encoding="utf-8",
    )
    (pres / "report_outline.json").write_text(
        json.dumps(
            {
                "hypothesis_id": "1",
                "sections": [
                    {"id": "overview"},
                    {"id": "data"},
                    {"id": "findings"},
                    {"id": "conclusions"},
                ],
                "figures": [
                    {
                        "asset": "chart_01_test.png",
                        "caption": "Test chart caption",
                        "finding_number": 1,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    from agentsociety2.skills.analysis.harness.report_bundle import write_report_bundle

    write_report_bundle(workspace, "1")
    save_report_review(
        workspace,
        "1",
        ReportQualityReview(
            hypothesis_id="1",
            verdict=ReviewVerdict.PASS,
            overall_score=5,
            dimensions={k: 5 for k in REPORT_DIMENSION_KEYS},
            report_fingerprint=report_content_fingerprint(pres),
        ),
    )
    result = validate_release(pres)
    assert result.status == "PASS"


def test_validate_release_blocks_missing_html(workspace: Path) -> None:
    pres = workspace / "presentation" / "hypothesis_1"
    pres.mkdir(parents=True, exist_ok=True)
    (pres / "report_zh.md").write_text(
        "## 概述\n\n## 数据\n\n## 发现\n\n## 结论\n", encoding="utf-8"
    )
    (pres / "report_en.md").write_text(
        "## Overview\n\n## Data\n\n## Findings\n\n## Conclusion\n",
        encoding="utf-8",
    )
    result = validate_release(pres)
    assert result.status == "BLOCKED"
    assert any(i.code == "report_missing" for i in result.issues)


def test_validate_report_quality_blocks_fluff(tmp_path: Path) -> None:
    pres = tmp_path / "presentation" / "hypothesis_1"
    pres.mkdir(parents=True)
    (pres / "report_zh.md").write_text(
        "## 概述\n\n结果显示出有趣的模式。\n\n## 数据\n\n## 发现\n\n## 结论\n",
        encoding="utf-8",
    )
    (pres / "report_en.md").write_text(
        "## Overview\n\nFurther research is needed.\n\n## Data\n\n## Findings\n\n## Conclusion\n",
        encoding="utf-8",
    )
    (pres / "report_zh.html").write_text(_minimal_report_html("zh"), encoding="utf-8")
    (pres / "report_en.html").write_text(_minimal_report_html("en"), encoding="utf-8")
    (pres / "data").mkdir()
    (pres / "data" / "analysis_summary.json").write_text(
        json.dumps(
            {"summary": "x", "key_findings": ["ok finding here"], "limitations": "sim"}
        ),
        encoding="utf-8",
    )
    result = validate_report_quality(pres)
    assert result.status == "BLOCKED"
    assert any(i.code == "report_fluff_phrase" for i in result.issues)


def test_validate_release_requires_fresh_review(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    pres = ws / "presentation" / "hypothesis_1"
    pres.mkdir(parents=True)
    (pres / "data").mkdir()
    (pres / "data" / "evidence_index.json").write_text(
        '{"sources":[]}', encoding="utf-8"
    )
    (pres / "report_zh.md").write_text("## 概述\n\n" + "word " * 40, encoding="utf-8")
    (pres / "report_en.md").write_text(
        "## Overview\n\n" + "word " * 40, encoding="utf-8"
    )
    (pres / "data" / "analysis_summary.json").write_text(
        json.dumps(
            {
                "summary": "ok summary here",
                "key_findings": ["finding with enough length"],
                "limitations": "simulation only",
            }
        ),
        encoding="utf-8",
    )
    (pres / "artifact_manifest.json").write_text(
        json.dumps({"hypothesis_id": "1", "artifacts": []}),
        encoding="utf-8",
    )
    (pres / "report_outline.json").write_text(
        json.dumps(
            {
                "hypothesis_id": "1",
                "sections": [{"id": "overview"}, {"id": "data"}, {"id": "findings"}],
                "figures": [],
            }
        ),
        encoding="utf-8",
    )
    harness_cli.cmd_intake(ws, "1", "1")
    _mark_prior_phases_gate_pass(ws, "1", "refine")
    result = harness_cli.cmd_validate_release(ws, "1", "1")
    assert result["status"] == "BLOCKED"
    assert any(
        i.get("code") == "report_review_missing" for i in result.get("issues", [])
    )


def test_build_report_context_collects_eda(workspace: Path) -> None:
    from agentsociety2.skills.analysis.harness.report_bundle import write_report_bundle

    harness_cli.cmd_intake(workspace, "1", "1")
    harness_cli.cmd_record_phase_artifacts(
        workspace,
        "1",
        "explore",
        ["presentation/hypothesis_1/data/eda_quick_stats.md"],
    )
    out = write_report_bundle(workspace, "1")
    assert out["source_count"] >= 1
    index_path = (
        workspace / "presentation" / "hypothesis_1" / "data" / "evidence_index.json"
    )
    assert index_path.exists()
    ctx_path = (
        workspace / "presentation" / "hypothesis_1" / "data" / "report_context.md"
    )
    assert "eda_quick_stats" in ctx_path.read_text(encoding="utf-8")


def test_validate_chart_script_requires_agg() -> None:
    bad = "import matplotlib.pyplot as plt\nplt.plot([1,2,3])\n"
    result = validate_chart_script(bad)
    assert result.status == "BLOCKED"


def test_validate_synthesis_missing_reports(workspace: Path) -> None:
    syn_dir = workspace / "synthesis"
    syn_dir.mkdir()
    result = validate_synthesis(
        workspace, synthesis_dir=syn_dir, scope_hypothesis_ids=["1"]
    )
    assert result.status == "BLOCKED"


def test_validate_synthesis_requires_scoped_source_artifacts(workspace: Path) -> None:
    syn_dir = workspace / "synthesis"
    syn_dir.mkdir()
    for name in (
        "synthesis_report_zh.md",
        "synthesis_report_en.md",
        "synthesis_report_zh.html",
        "synthesis_report_en.html",
    ):
        content = "<html>ok</html>" if name.endswith(".html") else "ok"
        (syn_dir / name).write_text(content, encoding="utf-8")
    (syn_dir / "synthesis_brief.json").write_text(
        json.dumps(
            {
                "synthesis_question": "What holds across hypotheses?",
                "scope_hypothesis_ids": ["1"],
                "source_artifacts": ["presentation/hypothesis_1/report_zh.md"],
            }
        ),
        encoding="utf-8",
    )
    pres = workspace / "presentation" / "hypothesis_1"
    pres.mkdir(parents=True, exist_ok=True)
    (pres / "report_zh.md").write_text("ok", encoding="utf-8")
    (pres / "report_zh.html").write_text("<html>ok</html>", encoding="utf-8")

    result = validate_synthesis(
        workspace, synthesis_dir=syn_dir, scope_hypothesis_ids=["1"]
    )

    assert result.status == "BLOCKED"
    assert any(i.code == "scope_hypothesis_source_missing" for i in result.issues)


def test_json_repair_loads_trailing_comma_outline() -> None:
    raw = """{
        "hypothesis_id": "1",
        "sections": [{"id": "overview"},],
        "figures": [],
    }"""
    outline = load_model_from_text(raw, ReportOutline)
    assert outline.hypothesis_id == "1"
    assert len(outline.sections) == 1


def test_validate_release_blocks_forbidden_presentation_dirs(tmp_path: Path) -> None:
    pres = tmp_path / "presentation" / "hypothesis_1"
    (pres / "analysis").mkdir(parents=True)
    (pres / "figures").mkdir()
    (pres / "report_zh.md").write_text(
        "## 概述\n\n## 数据\n\n## 发现\n\n## 结论\n", encoding="utf-8"
    )
    (pres / "report_en.md").write_text(
        "## Overview\n\n## Data\n\n## Findings\n\n## Conclusion\n",
        encoding="utf-8",
    )
    result = validate_release(pres)
    assert result.status == "BLOCKED"
    assert any(i.code == "presentation_layout_invalid" for i in result.issues)


def test_hypothesis_harness_dir_under_dot_agentsociety(workspace: Path) -> None:
    from agentsociety2.skills.analysis.harness.paths import hypothesis_harness_dir

    harness_cli.cmd_intake(workspace, "1", "1")
    harness_dir = hypothesis_harness_dir(workspace, "1")
    assert ".agentsociety" in str(harness_dir)
    assert harness_dir.name == "hypothesis_1"
    assert (harness_dir / "state.yaml").exists()


def test_validate_release_repairs_loose_json(tmp_path: Path) -> None:
    pres = tmp_path / "presentation" / "hypothesis_1"
    pres.mkdir(parents=True)
    assets = pres / "assets"
    assets.mkdir()
    (assets / "chart_01_test.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"x" * 200)
    (pres / "report_zh.md").write_text(
        "## 概述\n\n## 数据\n\n## 发现\n\n![c](assets/chart_01_test.png)\ncap\n\n## 结论\n",
        encoding="utf-8",
    )
    (pres / "report_en.md").write_text(
        "## Overview\n\n## Data\n\n## Findings\n\n![c](assets/chart_01_test.png)\ncap\n\n## Conclusion\n",
        encoding="utf-8",
    )
    (pres / "report_zh.html").write_text(_minimal_report_html("zh"), encoding="utf-8")
    (pres / "report_en.html").write_text(_minimal_report_html("en"), encoding="utf-8")
    (pres / "artifact_manifest.json").write_text(
        '{"hypothesis_id": "1", "artifacts": [{"filename": "chart_01_test.png", "type": "chart", "description": "t", "finding_number": 1, "included_in_report": true}],}',
        encoding="utf-8",
    )
    (pres / "data").mkdir(exist_ok=True)
    (pres / "data" / "analysis_summary.json").write_text(
        '{"summary": "ok", "key_findings": ["f1"], "limitations": "sim",}',
        encoding="utf-8",
    )
    (pres / "report_outline.json").write_text(
        '{"hypothesis_id": "1", "sections": [{"id": "overview"}, {"id": "data"}, {"id": "findings"}, {"id": "conclusions"}], "figures": [{"asset": "chart_01_test.png", "caption": "cap", "finding_number": 1}],}',
        encoding="utf-8",
    )
    from agentsociety2.skills.analysis.harness.report_bundle import write_report_bundle

    write_report_bundle(tmp_path, "1")
    result = validate_release(pres)
    assert result.status == "PASS"


def _mark_prior_phases_gate_pass(
    workspace: Path, hypothesis_id: str, through: str
) -> None:
    from agentsociety2.skills.analysis.harness.models import (
        AnalysisPhase,
        PhaseCheckpoint,
    )

    order = [p.value for p in AnalysisPhase]
    st = harness_state.load_hypothesis_state(workspace, hypothesis_id)
    for ph in order[: order.index(through) + 1]:
        cp = PhaseCheckpoint(
            phase=ph,
            structural_pass=True,
            attestation_pass=True,
            gate_pass=True,
        )
        st.phase_checkpoints[ph] = cp
    harness_state.save_hypothesis_state(workspace, hypothesis_id, st)


def test_record_attestation_produce_blocked_without_refine_gate(
    workspace: Path,
) -> None:
    from agentsociety2.skills.analysis.harness.models import AttestationStatus

    harness_cli.cmd_intake(workspace, "1", "1")
    _mark_prior_phases_gate_pass(workspace, "1", "claims")

    out = harness_cli.cmd_record_attestation(
        workspace,
        "1",
        {
            "phase": "produce",
            "status": AttestationStatus.DONE.value,
            "key_findings": ["Reports done"],
            "rubric": {
                "bilingual_reports_reviewed": True,
                "limitations_stated": "sim only",
                "independent_review_pass": True,
            },
        },
    )
    assert out.get("error") == "prior_phase_gate_blocked"
    assert any(
        i.get("code") == "prior_phase_gate_blocked" for i in out.get("issues", [])
    )


def test_sync_report_assets_copies_from_charts(tmp_path: Path) -> None:
    pres = tmp_path / "presentation" / "hypothesis_1"
    charts = pres / "charts"
    charts.mkdir(parents=True)
    (charts / "fig_a.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"x" * 80)
    (pres / "report_zh.md").write_text(
        "## 发现\n\n![a](assets/fig_a.png)\ncaption\n",
        encoding="utf-8",
    )
    result = sync_report_assets_from_reports(pres)
    assert result["copied"] == ["fig_a.png"]
    assert (pres / "assets" / "fig_a.png").is_file()


def test_validate_release_blocks_charts_dir_refs(tmp_path: Path) -> None:
    pres = tmp_path / "presentation" / "hypothesis_1"
    pres.mkdir(parents=True)
    (pres / "report_zh.md").write_text(
        "## 发现\n\n![a](charts/fig_a.png)\n",
        encoding="utf-8",
    )
    (pres / "report_en.md").write_text(
        "## Findings\n\n## Conclusion\n",
        encoding="utf-8",
    )
    result = validate_release(pres)
    assert result.status == "BLOCKED"
    assert any(i.code == "report_embeds_charts_dir" for i in result.issues)


def test_validate_release_blocked_when_refine_gate_not_pass(workspace: Path) -> None:
    harness_cli.cmd_intake(workspace, "1", "1")
    pres = workspace / "presentation" / "hypothesis_1"
    pres.mkdir(parents=True, exist_ok=True)
    (pres / "report_zh.md").write_text(
        "## 概述\n\n## 数据\n\n## 发现\n\n## 结论\n",
        encoding="utf-8",
    )
    (pres / "report_en.md").write_text(
        "## Overview\n\n## Data\n\n## Findings\n\n## Conclusion\n",
        encoding="utf-8",
    )
    result = harness_cli.cmd_validate_release(workspace, "1", "1")
    assert result["status"] == "BLOCKED"
    assert any(
        i.get("code") == "prior_phase_gate_blocked" for i in result.get("issues", [])
    )
