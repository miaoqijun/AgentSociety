from __future__ import annotations

import argparse
import json
from datetime import datetime
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from typing import TypedDict

import yaml  # type: ignore[import-untyped]

from agentsociety2.skills.paper.cli import generate_paper
from agentsociety2.skills.paper.paths import nature_template_dir


def _load_paper_adapter_cli_module():
    repo_root = Path(__file__).resolve().parents[3]
    module_path = (
        repo_root
        / "extension"
        / "skills"
        / "agentsociety-paper-adapter"
        / "v1.0.0"
        / "scripts"
        / "build_research_pack.py"
    )
    spec = spec_from_file_location("paper_adapter_cli_test_module", module_path)
    module = module_from_spec(spec)
    assert spec is not None
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


paper_adapter_cli = _load_paper_adapter_cli_module()


class CompileUrlCase(TypedDict):
    name: str
    data_url: str | None
    code_url: str | None


def _write_basic_meta(
    workspace: Path,
    *,
    data_url: str | None = "https://example.com/data",
    code_url: str | None = "https://example.com/code",
    corresponding: bool = False,
) -> None:
    paper_dir = workspace / "paper"
    authors: list[dict[str, object]] = [{"name": "Alice", "affils": [1]}]
    meta: dict[str, object] = {
        "title": "Test Paper",
        "authors": authors,
        "affils": [{"id": 1, "name": "Test Lab"}],
    }
    if corresponding:
        authors[0]["corresponding"] = True
        authors[0]["email"] = "a@example.com"
    if data_url is not None:
        meta["data_availability_url"] = data_url
    if code_url is not None:
        meta["code_availability_url"] = code_url
    (paper_dir / "paper_meta.yaml").write_text(
        yaml.safe_dump(meta, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )


def test_status_parser_defaults_workspace_to_current_dir():
    parser = generate_paper.build_parser()

    args = parser.parse_args(["status"])

    assert args.workspace == "."
    assert args.func is generate_paper.cmd_status


def test_paper_adapter_parser_defaults_workspace_from_env(monkeypatch, tmp_path):
    monkeypatch.setenv("AGENTSOCIETY_WORKSPACE", str(tmp_path))

    parser = paper_adapter_cli.build_parser()
    args = parser.parse_args([])

    assert Path(args.workspace) == tmp_path.resolve()


def test_nature_template_dir_uses_skill_packaged_template():
    template_dir = nature_template_dir()

    assert template_dir.name == "nature"
    assert (template_dir / "main.tex.j2").exists()
    assert "docs/superpowers" not in str(template_dir)


def test_read_manuscript_results_supports_nested_and_legacy_layouts(tmp_path: Path):
    generate_paper._ensure_paper_imports()

    manuscript_dir = tmp_path / "paper" / "artifacts" / "manuscript"
    nested_results_dir = manuscript_dir / "results"
    nested_results_dir.mkdir(parents=True)

    (nested_results_dir / "01_nested.md").write_text("nested result", encoding="utf-8")
    (manuscript_dir / "results_02_legacy.md").write_text("legacy result", encoding="utf-8")

    text = generate_paper._read_manuscript_results(tmp_path)

    assert "nested result" in text
    assert "legacy result" in text


def test_invalid_citation_keys_are_detected_against_research_pack(tmp_path: Path):
    generate_paper._ensure_paper_imports()

    models = generate_paper._models
    research_pack = models.ResearchPack(
        workspace_path=str(tmp_path),
        literature=[
            models.ResearchPackLiterature(
                cite_key="Levy2021",
                title="Example Title",
            )
        ],
    )
    generate_paper._state.research_pack.save(tmp_path, research_pack)

    invalid = generate_paper._invalid_citation_keys(
        tmp_path,
        "Valid [CITE:Levy2021], invalid [CITE:C3], mixed [CITE:Levy2021, C6].",
    )

    assert invalid == ["C3", "C6"]


def test_invalid_citation_keys_accept_reference_pool_supplemental_entries(tmp_path: Path):
    generate_paper._ensure_paper_imports()

    models = generate_paper._models
    research_pack = models.ResearchPack(
        workspace_path=str(tmp_path),
        literature=[],
        reference_pool=models.ResearchPackReferencePool(
            workspace_refs=[
                models.ResearchPackLiterature(
                    cite_key="Levy2021",
                    title="Example Title",
                )
            ],
            supplemental_refs=[
                models.ResearchPackLiterature(
                    cite_key="Smith2024",
                    title="Supplemental Entry",
                )
            ],
        ),
    )
    generate_paper._state.research_pack.save(tmp_path, research_pack)

    invalid = generate_paper._invalid_citation_keys(
        tmp_path,
        "Core [CITE:Levy2021], supplemental [CITE:Smith2024], invalid [CITE:C3].",
    )

    assert invalid == ["C3"]


def test_build_pack_preserves_incremental_supplemental_literature(tmp_path: Path, monkeypatch):
    generate_paper._ensure_paper_imports()

    (tmp_path / "paper").mkdir(parents=True)
    _write_basic_meta(tmp_path)
    state_dir = tmp_path / "paper" / "state"
    state_dir.mkdir(parents=True)

    models = generate_paper._models
    generate_paper._state.paper_state.save(
        tmp_path,
        models.PaperState(current_phase=models.PaperPhase.framing),
    )
    generate_paper._state.research_pack.save(
        tmp_path,
        models.ResearchPack(
            workspace_path=str(tmp_path),
            literature=[
                models.ResearchPackLiterature(
                    cite_key="Existing2024",
                    title="Existing Workspace Entry",
                    bibtex="@article{existing2024,\n  title = {Existing Workspace Entry}\n}",
                ),
                models.ResearchPackLiterature(
                    cite_key="Supplement2024",
                    title="Supplemental Entry",
                    bibtex="@article{supplement2024,\n  title = {Supplemental Entry}\n}",
                ),
            ],
        ),
    )

    fresh_pack = models.ResearchPack(
        workspace_path=str(tmp_path),
        literature=[
            models.ResearchPackLiterature(
                cite_key="Existing2024",
                title="Existing Workspace Entry",
                bibtex="@article{existing2024,\n  title = {Existing Workspace Entry}\n}",
            ),
            models.ResearchPackLiterature(
                cite_key="Fresh2025",
                title="Fresh Workspace Entry",
                bibtex="@article{fresh2025,\n  title = {Fresh Workspace Entry}\n}",
            ),
        ],
    )

    monkeypatch.setattr(
        generate_paper._adapter_research_pack_builder,
        "build_research_pack",
        lambda workspace, research_objective=None: fresh_pack,
    )

    rc = generate_paper.cmd_build_pack(
        argparse.Namespace(workspace=str(tmp_path), research_objective=None)
    )

    assert rc == 0
    saved_pack = generate_paper._state.research_pack.load(tmp_path)
    assert [entry.cite_key for entry in saved_pack.literature] == [
        "Existing2024",
        "Fresh2025",
        "Supplement2024",
    ]
    assert saved_pack.reference_pool is not None
    assert [entry.cite_key for entry in saved_pack.reference_pool.workspace_refs] == [
        "Existing2024",
        "Fresh2025",
    ]
    assert [entry.cite_key for entry in saved_pack.reference_pool.supplemental_refs] == [
        "Supplement2024",
    ]


def test_research_pack_literature_keeps_bibtex_alignment_after_skipping_empty_titles():
    generate_paper._ensure_paper_imports()

    builder = generate_paper._adapter_research_pack_builder

    literature = builder._literature_to_models(
        [
            {"title": "", "year": 2023},
            {"title": "Second Entry", "year": 2024},
        ]
    )

    assert len(literature) == 1
    assert literature[0].title == "Second Entry"
    assert literature[0].bibtex
    assert "Second Entry" in literature[0].bibtex


def test_open_run_generates_unique_directory_for_same_timestamp(tmp_path: Path):
    generate_paper._ensure_paper_imports()

    runs = generate_paper._state.runs

    first_ts, first_dir = runs.open_run(tmp_path, timestamp="20260507_120000")
    second_ts, second_dir = runs.open_run(tmp_path, timestamp="20260507_120000")

    assert first_ts == "20260507_120000"
    assert second_ts == "20260507_120000_01"
    assert first_dir != second_dir
    assert first_dir.exists()
    assert second_dir.exists()


def test_compile_creates_stable_output_aliases_and_persists_envelope(
    tmp_path: Path,
    monkeypatch,
):
    generate_paper._ensure_paper_imports()

    workspace = tmp_path
    paper_dir = workspace / "paper"
    manuscript_dir = paper_dir / "artifacts" / "manuscript"
    manuscript_dir.mkdir(parents=True)
    (manuscript_dir / "main.md").write_text(
        "Body with [FIG:F1] and [CITE:Entry302024].",
        encoding="utf-8",
    )
    _write_basic_meta(workspace, corresponding=True)

    compiler = generate_paper._compiler
    models = generate_paper._models
    research_pack = models.ResearchPack(
        workspace_path=str(workspace),
        literature=[
            models.ResearchPackLiterature(
                cite_key=f"Entry{index}2024",
                title=f"Entry{index} Title",
                bibtex=(
                    f"@article{{entry{index}2024,\n"
                    f"  title = {{Entry{index} Title}},\n"
                    "  year = {2024}\n}"
                ),
            )
            for index in range(31)
        ],
    )
    generate_paper._state.research_pack.save(workspace, research_pack)
    generate_paper._state.figure_argument.save(
        workspace,
        models.FigureArgumentMap(
            figures=[
                models.FigureSpec(
                    figure_id="F1",
                    title="Main effect plot",
                    question_answered="Does the treatment move the main outcome?",
                    status="rendered",
                    file_path=str(tmp_path / "f1.png"),
                    panels=["Treatment effect by condition."],
                )
            ]
        ),
    )
    (tmp_path / "f1.png").write_bytes(b"png")

    def fake_compile(compose_dir: Path, *_, **__):
        out_dir = Path(compose_dir) / "out"
        out_dir.mkdir(parents=True, exist_ok=True)
        pdf_path = out_dir / "main.pdf"
        log_path = out_dir / "main.log"
        pdf_path.write_bytes(b"%PDF-1.4\n")
        log_path.write_text("ok", encoding="utf-8")
        return models.CompileResult(
            pdf_path=str(pdf_path),
            log_path=str(log_path),
            success=True,
            errors=[],
        )

    monkeypatch.setattr(compiler, "compile", fake_compile)

    rc = generate_paper.cmd_compile(argparse.Namespace(workspace=str(workspace)))

    assert rc == 0

    runs_dir = workspace / "paper" / "runs"
    run_names = sorted(p.name for p in runs_dir.iterdir() if p.is_dir())
    assert len(run_names) == 1
    run_dir = runs_dir / run_names[0]

    assert (run_dir / "compose" / "out" / "paper.pdf").exists()
    assert (run_dir / "compose" / "out" / "paper.log").exists()
    references_bib = (run_dir / "compose" / "references.bib").read_text(encoding="utf-8")
    assert "@article{entry302024," in references_bib

    envelope_payload = json.loads((run_dir / "envelope.json").read_text(encoding="utf-8"))
    assert envelope_payload["status"] == "DONE"


def test_compile_requires_matching_research_pack_workspace(tmp_path: Path):
    generate_paper._ensure_paper_imports()

    workspace = tmp_path
    paper_dir = workspace / "paper"
    manuscript_dir = paper_dir / "artifacts" / "manuscript"
    manuscript_dir.mkdir(parents=True)
    (manuscript_dir / "main.md").write_text("Body", encoding="utf-8")
    _write_basic_meta(workspace)

    models = generate_paper._models
    generate_paper._state.research_pack.save(
        workspace,
        models.ResearchPack(
            workspace_path="/tmp/other-workspace",
            literature=[],
        ),
    )

    rc = generate_paper.cmd_compile(argparse.Namespace(workspace=str(workspace)))

    assert rc == 2


def test_compile_blocks_rendered_figures_without_file_paths(tmp_path: Path):
    generate_paper._ensure_paper_imports()

    workspace = tmp_path
    paper_dir = workspace / "paper"
    manuscript_dir = paper_dir / "artifacts" / "manuscript"
    manuscript_dir.mkdir(parents=True)
    (manuscript_dir / "main.md").write_text("Body with [FIG:F1].", encoding="utf-8")
    _write_basic_meta(workspace)

    models = generate_paper._models
    generate_paper._state.research_pack.save(
        workspace,
        models.ResearchPack(
            workspace_path=str(workspace),
            literature=[],
        ),
    )
    generate_paper._state.figure_argument.save(
        workspace,
        models.FigureArgumentMap(
            figures=[
                models.FigureSpec(
                    figure_id="F1",
                    status="rendered",
                    file_path=None,
                )
            ]
        ),
    )

    rc = generate_paper.cmd_compile(argparse.Namespace(workspace=str(workspace)))

    assert rc == 2


def test_compile_blocks_open_review_round(tmp_path: Path):
    generate_paper._ensure_paper_imports()

    workspace = tmp_path
    paper_dir = workspace / "paper"
    manuscript_dir = paper_dir / "artifacts" / "manuscript"
    manuscript_dir.mkdir(parents=True)
    (manuscript_dir / "main.md").write_text("Body", encoding="utf-8")
    _write_basic_meta(workspace)

    models = generate_paper._models
    generate_paper._state.research_pack.save(
        workspace,
        models.ResearchPack(
            workspace_path=str(workspace),
            literature=[],
        ),
    )
    generate_paper._state.reviews.save_round(
        workspace,
        models.ReviewRound(
            round_num=1,
            reviews=[
                models.Review(
                    reviewer_profile="precision-editor",
                    verdict="revise_local",
                    severity="warning",
                )
            ],
        ),
    )

    rc = generate_paper.cmd_compile(argparse.Namespace(workspace=str(workspace)))

    assert rc == 2


def test_compile_blocks_claims_without_visible_citation_anchor(tmp_path: Path):
    generate_paper._ensure_paper_imports()

    workspace = tmp_path
    paper_dir = workspace / "paper"
    manuscript_dir = paper_dir / "artifacts" / "manuscript"
    manuscript_dir.mkdir(parents=True)
    (manuscript_dir / "main.md").write_text(
        "Body without the expected supporting citation.",
        encoding="utf-8",
    )
    _write_basic_meta(workspace)

    models = generate_paper._models
    generate_paper._state.research_pack.save(
        workspace,
        models.ResearchPack(
            workspace_path=str(workspace),
            literature=[
                models.ResearchPackLiterature(
                    cite_key="Levy2021",
                    title="Example Title",
                    bibtex="@article{levy2021,\n  title = {Example Title}\n}",
                )
            ],
        ),
    )
    generate_paper._state.claim_ledger.save(
        workspace,
        models.ClaimLedger(
            claims=[
                models.Claim(
                    claim_id="C1",
                    claim_text="Supported claim",
                    evidence_support=["[CITE:Levy2021]"],
                )
            ]
        ),
    )

    rc = generate_paper.cmd_compile(argparse.Namespace(workspace=str(workspace)))

    assert rc == 2


def test_compile_blocks_claims_without_visible_figure_anchor(tmp_path: Path):
    generate_paper._ensure_paper_imports()

    workspace = tmp_path
    paper_dir = workspace / "paper"
    manuscript_dir = paper_dir / "artifacts" / "manuscript"
    manuscript_dir.mkdir(parents=True)
    (manuscript_dir / "main.md").write_text(
        "Body without the expected figure reference.",
        encoding="utf-8",
    )
    _write_basic_meta(workspace)

    models = generate_paper._models
    generate_paper._state.paper_state.save(
        workspace,
        models.PaperState(current_phase=models.PaperPhase.manuscript_build),
    )
    generate_paper._state.research_pack.save(
        workspace,
        models.ResearchPack(workspace_path=str(workspace), literature=[]),
    )
    generate_paper._state.claim_ledger.save(
        workspace,
        models.ClaimLedger(
            claims=[
                models.Claim(
                    claim_id="C1",
                    claim_text="Figure-backed claim",
                    evidence_support=["F1"],
                )
            ]
        ),
    )
    generate_paper._state.figure_argument.save(
        workspace,
        models.FigureArgumentMap(
            figures=[
                models.FigureSpec(
                    figure_id="F1",
                    title="Main effect plot",
                    question_answered="Does the treatment move the main outcome?",
                    status="rendered",
                    file_path=str(tmp_path / "f1.png"),
                    panels=["Treatment effect by condition."],
                )
            ]
        ),
    )
    (tmp_path / "f1.png").write_bytes(b"png")

    rc = generate_paper.cmd_compile(argparse.Namespace(workspace=str(workspace)))

    assert rc == 2


def test_compile_blocks_unfilled_degraded_generation_slot_markers(tmp_path: Path):
    generate_paper._ensure_paper_imports()

    workspace = tmp_path
    paper_dir = workspace / "paper"
    manuscript_dir = paper_dir / "artifacts" / "manuscript"
    manuscript_dir.mkdir(parents=True)
    (manuscript_dir / "main.md").write_text(
        "Body with unresolved slot [[METRIC_SLOT:s1]].",
        encoding="utf-8",
    )
    _write_basic_meta(workspace)

    models = generate_paper._models
    generate_paper._state.paper_state.save(
        workspace,
        models.PaperState(current_phase=models.PaperPhase.manuscript_build),
    )
    generate_paper._state.research_pack.save(
        workspace,
        models.ResearchPack(workspace_path=str(workspace), literature=[]),
    )

    rc = generate_paper.cmd_compile(argparse.Namespace(workspace=str(workspace)))

    assert rc == 2
    state = generate_paper._state.paper_state.load(workspace)
    assert state.last_blocker == "compile blocked by residual degraded-generation slot markers"
    assert len(state.round_constraints) == 1
    assert state.round_constraints[0].generation_mode == "template_slots"
    assert state.round_constraints[0].issue_type == "residual_template_slots"
    assert "METRIC_SLOT" in state.round_constraints[0].required_slot_types


def test_compile_blocks_source_platform_mismatch(tmp_path: Path):
    generate_paper._ensure_paper_imports()

    workspace = tmp_path
    paper_dir = workspace / "paper"
    manuscript_dir = paper_dir / "artifacts" / "manuscript"
    manuscript_dir.mkdir(parents=True)
    (manuscript_dir / "main.md").write_text(
        "Levy randomly assigned Twitter users to follow accounts sharing counter-attitudinal news.",
        encoding="utf-8",
    )
    _write_basic_meta(workspace)

    models = generate_paper._models
    generate_paper._state.research_pack.save(
        workspace,
        models.ResearchPack(
            workspace_path=str(workspace),
            topic=(
                "Original study design: large-scale field experiment on Facebook. "
                "Intervention: offer subscriptions to outlets."
            ),
            literature=[],
        ),
    )

    rc = generate_paper.cmd_compile(argparse.Namespace(workspace=str(workspace)))

    assert rc == 2


def test_compile_runs_from_workspace_root(tmp_path: Path, monkeypatch):
    generate_paper._ensure_paper_imports()

    workspace = tmp_path
    paper_dir = workspace / "paper"
    manuscript_dir = paper_dir / "artifacts" / "manuscript"
    nested_cwd = manuscript_dir / "results"
    nested_cwd.mkdir(parents=True)
    (manuscript_dir / "main.md").write_text("Body", encoding="utf-8")
    _write_basic_meta(workspace, corresponding=True)

    compiler = generate_paper._compiler
    models = generate_paper._models
    generate_paper._state.research_pack.save(
        workspace,
        models.ResearchPack(workspace_path=str(workspace), literature=[]),
    )

    seen_cwds: list[Path] = []

    def fake_compile(compose_dir: Path, *_, **__):
        seen_cwds.append(Path.cwd())
        out_dir = Path(compose_dir) / "out"
        out_dir.mkdir(parents=True, exist_ok=True)
        pdf_path = out_dir / "main.pdf"
        log_path = out_dir / "main.log"
        pdf_path.write_bytes(b"%PDF-1.4\n")
        log_path.write_text("ok", encoding="utf-8")
        return models.CompileResult(
            pdf_path=str(pdf_path),
            log_path=str(log_path),
            success=True,
            errors=[],
        )

    monkeypatch.setattr(compiler, "compile", fake_compile)
    monkeypatch.chdir(nested_cwd)

    rc = generate_paper.cmd_compile(argparse.Namespace(workspace=str(workspace)))

    assert rc == 0
    assert seen_cwds == [workspace]


def test_compile_requires_data_and_code_availability_urls(tmp_path: Path):
    generate_paper._ensure_paper_imports()

    models = generate_paper._models
    cases: list[CompileUrlCase] = [
        {"name": "missing-data", "data_url": None, "code_url": "https://example.com/code"},
        {"name": "missing-code", "data_url": "https://example.com/data", "code_url": None},
    ]

    for case in cases:
        workspace = tmp_path / case["name"]
        paper_dir = workspace / "paper"
        manuscript_dir = paper_dir / "artifacts" / "manuscript"
        manuscript_dir.mkdir(parents=True)
        (manuscript_dir / "main.md").write_text("Body", encoding="utf-8")
        _write_basic_meta(
            workspace,
            data_url=case["data_url"],
            code_url=case["code_url"],
        )
        generate_paper._state.research_pack.save(
            workspace,
            models.ResearchPack(workspace_path=str(workspace), literature=[]),
        )

        rc = generate_paper.cmd_compile(argparse.Namespace(workspace=str(workspace)))

        assert rc == 2


def test_compile_blocks_rendered_figures_without_title_question_or_panels(tmp_path: Path):
    generate_paper._ensure_paper_imports()

    models = generate_paper._models
    cases = [
        models.FigureSpec(
            figure_id="F1",
            title="",
            question_answered="What changes?",
            status="rendered",
            file_path=str(tmp_path / "missing-title.png"),
            panels=["Main estimate."],
        ),
        models.FigureSpec(
            figure_id="F1",
            title="Main effect plot",
            question_answered="",
            status="rendered",
            file_path=str(tmp_path / "missing-question.png"),
            panels=["Main estimate."],
        ),
        models.FigureSpec(
            figure_id="F1",
            title="Main effect plot",
            question_answered="What changes?",
            status="rendered",
            file_path=str(tmp_path / "missing-panels.png"),
            panels=[],
        ),
    ]

    for index, figure in enumerate(cases, start=1):
        workspace = tmp_path / f"figure-case-{index}"
        paper_dir = workspace / "paper"
        manuscript_dir = paper_dir / "artifacts" / "manuscript"
        manuscript_dir.mkdir(parents=True)
        (manuscript_dir / "main.md").write_text("Body with [FIG:F1].", encoding="utf-8")
        _write_basic_meta(workspace)
        Path(figure.file_path).write_bytes(b"png")
        generate_paper._state.research_pack.save(
            workspace,
            models.ResearchPack(workspace_path=str(workspace), literature=[]),
        )
        generate_paper._state.figure_argument.save(
            workspace,
            models.FigureArgumentMap(figures=[figure]),
        )

        rc = generate_paper.cmd_compile(argparse.Namespace(workspace=str(workspace)))

        assert rc == 2


def test_compile_strips_top_level_section_headings_before_tex_assembly(
    tmp_path: Path,
    monkeypatch,
):
    generate_paper._ensure_paper_imports()

    workspace = tmp_path
    paper_dir = workspace / "paper"
    manuscript_dir = paper_dir / "artifacts" / "manuscript"
    results_dir = manuscript_dir / "results"
    results_dir.mkdir(parents=True)

    (manuscript_dir / "abstract.md").write_text(
        "# Abstract\n\nAbstract body.",
        encoding="utf-8",
    )
    (manuscript_dir / "main.md").write_text(
        "# Main\n\nMain body.",
        encoding="utf-8",
    )
    (results_dir / "01_result.md").write_text(
        "# Results\n\n## Result A\n\nResult body.",
        encoding="utf-8",
    )
    (manuscript_dir / "discussion.md").write_text(
        "## Discussion\n\nDiscussion body.",
        encoding="utf-8",
    )
    _write_basic_meta(workspace, corresponding=True)

    models = generate_paper._models
    generate_paper._state.research_pack.save(
        workspace,
        models.ResearchPack(workspace_path=str(workspace), literature=[]),
    )

    captured_compose_dir: list[Path] = []

    def fake_compile(compose_dir: Path, *_, **__):
        captured_compose_dir.append(Path(compose_dir))
        out_dir = Path(compose_dir) / "out"
        out_dir.mkdir(parents=True, exist_ok=True)
        pdf_path = out_dir / "main.pdf"
        log_path = out_dir / "main.log"
        pdf_path.write_bytes(b"%PDF-1.4\n")
        log_path.write_text("ok", encoding="utf-8")
        return models.CompileResult(
            pdf_path=str(pdf_path),
            log_path=str(log_path),
            success=True,
            errors=[],
        )

    monkeypatch.setattr(generate_paper._compiler, "compile", fake_compile)

    rc = generate_paper.cmd_compile(argparse.Namespace(workspace=str(workspace)))

    assert rc == 0
    assert len(captured_compose_dir) == 1
    main_tex = (captured_compose_dir[0] / "main.tex").read_text(encoding="utf-8")
    assert "# Abstract" not in main_tex
    assert "\\# Main" not in main_tex
    assert "\\# Results" not in main_tex
    assert "\\subsection*{Discussion}" not in main_tex


def test_run_loop_rejects_unimplemented_review_rounds(tmp_path: Path):
    generate_paper._ensure_paper_imports()

    paper_dir = tmp_path / "paper"
    paper_dir.mkdir(parents=True)
    (paper_dir / "paper_meta.yaml").write_text(
        yaml.safe_dump(
            {
                "title": "Test Paper",
                "authors": [{"name": "Alice", "affils": [1]}],
                "affils": [{"id": 1, "name": "Test Lab"}],
            },
            sort_keys=False,
            allow_unicode=True,
        ),
        encoding="utf-8",
    )

    rc = generate_paper.cmd_run_loop(
        argparse.Namespace(workspace=str(tmp_path), max_rounds=1)
    )

    assert rc == 2


def test_review_round_accepts_advance_state_to_release_gate(tmp_path: Path):
    generate_paper._ensure_paper_imports()

    paper_state_path = tmp_path / "paper" / "state"
    paper_state_path.mkdir(parents=True)
    models = generate_paper._models
    state = models.PaperState(current_phase=models.PaperPhase.skeptical_review)
    generate_paper._state.paper_state.save(tmp_path, state)

    payload = {
        "round_num": 1,
        "reviews": [
            {
                "reviewer_profile": "precision-editor",
                "verdict": "accept",
                "severity": "info",
            }
        ],
        "completed_at": datetime.utcnow().isoformat(),
    }

    rc = generate_paper.cmd_review(
        argparse.Namespace(workspace=str(tmp_path), payload=json.dumps(payload), round=1)
    )

    assert rc == 0
    updated = generate_paper._state.paper_state.load(tmp_path)
    assert updated.current_phase == models.PaperPhase.release_gate
    assert updated.release_status == models.ReleaseStatus.ready
    assert updated.round == 1


def test_review_round_non_accept_advances_to_revision_router(tmp_path: Path):
    generate_paper._ensure_paper_imports()

    paper_state_path = tmp_path / "paper" / "state"
    paper_state_path.mkdir(parents=True)
    models = generate_paper._models
    state = models.PaperState(current_phase=models.PaperPhase.skeptical_review)
    generate_paper._state.paper_state.save(tmp_path, state)

    payload = {
        "round_num": 1,
        "reviews": [
            {
                "reviewer_profile": "evidence-skeptic",
                "verdict": "revise_structural",
                "severity": "warning",
            }
        ],
        "completed_at": datetime.utcnow().isoformat(),
    }

    rc = generate_paper.cmd_review(
        argparse.Namespace(workspace=str(tmp_path), payload=json.dumps(payload), round=1)
    )

    assert rc == 0
    updated = generate_paper._state.paper_state.load(tmp_path)
    assert updated.current_phase == models.PaperPhase.revision_router
    assert updated.release_status == models.ReleaseStatus.in_review


def test_run_loop_routes_framing_phase_to_storyline_requirement(tmp_path: Path):
    generate_paper._ensure_paper_imports()

    paper_dir = tmp_path / "paper"
    (paper_dir / "state").mkdir(parents=True)
    (paper_dir / "paper_meta.yaml").write_text(
        yaml.safe_dump(
            {
                "title": "Test Paper",
                "authors": [{"name": "Alice", "affils": [1]}],
                "affils": [{"id": 1, "name": "Test Lab"}],
            },
            sort_keys=False,
            allow_unicode=True,
        ),
        encoding="utf-8",
    )

    models = generate_paper._models
    generate_paper._state.paper_state.save(
        tmp_path,
        models.PaperState(current_phase=models.PaperPhase.framing),
    )
    generate_paper._state.research_pack.save(
        tmp_path,
        models.ResearchPack(workspace_path=str(tmp_path)),
    )

    rc = generate_paper.cmd_run_loop(
        argparse.Namespace(workspace=str(tmp_path), max_rounds=0)
    )

    assert rc == 2


def test_run_loop_expansion_plan_records_external_dispatches(tmp_path: Path):
    generate_paper._ensure_paper_imports()

    paper_dir = tmp_path / "paper"
    (paper_dir / "state").mkdir(parents=True)
    _write_basic_meta(tmp_path)

    models = generate_paper._models
    generate_paper._state.paper_state.save(
        tmp_path,
        models.PaperState(current_phase=models.PaperPhase.expansion_plan),
    )
    generate_paper._state.research_pack.save(
        tmp_path,
        models.ResearchPack(workspace_path=str(tmp_path)),
    )
    generate_paper._state.evidence_backlog.save(
        tmp_path,
        models.EvidenceBacklog.model_validate(
            {
                "gaps": [
                    {
                        "gap_id": "G1",
                        "claim_id": "C1",
                        "gap_type": "missing_literature",
                        "description": "Need prior work coverage.",
                        "priority": "high",
                        "auto_executable": True,
                        "tool": "agentsociety-literature-search",
                    },
                    {
                        "gap_id": "G2",
                        "claim_id": "C2",
                        "gap_type": "missing_figure",
                        "description": "Need an additional robustness plot.",
                        "priority": "high",
                        "auto_executable": True,
                        "tool": "agentsociety-analysis",
                    },
                ]
            }
        ),
    )

    rc = generate_paper.cmd_run_loop(
        argparse.Namespace(workspace=str(tmp_path), max_rounds=0)
    )

    assert rc == 0
    state = generate_paper._state.paper_state.load(tmp_path)
    assert state.current_phase == models.PaperPhase.expansion_plan
    assert state.counters.citation_augmentations == 1
    assert state.counters.figure_regenerations == 1
    latest_run = generate_paper._state.runs.latest_run(tmp_path)
    assert latest_run is not None
    dispatches = generate_paper._state.runs.list_dispatches(tmp_path, latest_run)
    assert [dispatch.target_skill for dispatch in dispatches] == [
        "agentsociety-literature-search",
        "agentsociety-analysis",
    ]


def test_run_loop_routes_manuscript_build_to_compile(tmp_path: Path, monkeypatch):
    generate_paper._ensure_paper_imports()

    paper_dir = tmp_path / "paper"
    manuscript_dir = paper_dir / "artifacts" / "manuscript"
    manuscript_dir.mkdir(parents=True)
    (paper_dir / "state").mkdir(parents=True, exist_ok=True)
    (paper_dir / "paper_meta.yaml").write_text(
        yaml.safe_dump(
            {
                "title": "Test Paper",
                "authors": [{"name": "Alice", "affils": [1]}],
                "affils": [{"id": 1, "name": "Test Lab"}],
            },
            sort_keys=False,
            allow_unicode=True,
        ),
        encoding="utf-8",
    )
    (manuscript_dir / "main.md").write_text("Body", encoding="utf-8")

    models = generate_paper._models
    generate_paper._state.paper_state.save(
        tmp_path,
        models.PaperState(current_phase=models.PaperPhase.manuscript_build),
    )
    generate_paper._state.research_pack.save(
        tmp_path,
        models.ResearchPack(workspace_path=str(tmp_path)),
    )
    generate_paper._state.claim_ledger.save(
        tmp_path,
        models.ClaimLedger(claims=[]),
    )
    generate_paper._state.figure_argument.save(
        tmp_path,
        models.FigureArgumentMap(figures=[]),
    )

    monkeypatch.setattr(generate_paper, "cmd_compile", lambda args: 0)

    rc = generate_paper.cmd_run_loop(
        argparse.Namespace(workspace=str(tmp_path), max_rounds=0)
    )

    assert rc == 0


def test_run_loop_revision_router_resets_to_manuscript_build(tmp_path: Path):
    generate_paper._ensure_paper_imports()

    paper_dir = tmp_path / "paper"
    (paper_dir / "state").mkdir(parents=True)
    (paper_dir / "paper_meta.yaml").write_text(
        yaml.safe_dump(
            {
                "title": "Test Paper",
                "authors": [{"name": "Alice", "affils": [1], "corresponding": True, "email": "a@example.com"}],
                "affils": [{"id": 1, "name": "Test Lab"}],
            },
            sort_keys=False,
            allow_unicode=True,
        ),
        encoding="utf-8",
    )

    models = generate_paper._models
    generate_paper._state.paper_state.save(
        tmp_path,
        models.PaperState(current_phase=models.PaperPhase.revision_router),
    )
    generate_paper._state.research_pack.save(
        tmp_path,
        models.ResearchPack(workspace_path=str(tmp_path)),
    )
    generate_paper._state.reviews.save_round(
        tmp_path,
        models.ReviewRound(
            round_num=1,
            completed_at=datetime.utcnow(),
            reviews=[
                models.Review(
                    reviewer_profile="precision-editor",
                    verdict="revise_structural",
                    severity="warning",
                    target_layer="section",
                    issue_type="structure",
                )
            ],
        ),
    )

    rc = generate_paper.cmd_run_loop(
        argparse.Namespace(workspace=str(tmp_path), max_rounds=0)
    )

    assert rc == 0
    state = generate_paper._state.paper_state.load(tmp_path)
    assert state.current_phase == models.PaperPhase.manuscript_build


def test_run_loop_revision_router_records_dispatch_for_manuscript_build(tmp_path: Path):
    generate_paper._ensure_paper_imports()

    paper_dir = tmp_path / "paper"
    (paper_dir / "state").mkdir(parents=True)
    (paper_dir / "paper_meta.yaml").write_text(
        yaml.safe_dump(
            {
                "title": "Test Paper",
                "authors": [{"name": "Alice", "affils": [1], "corresponding": True, "email": "a@example.com"}],
                "affils": [{"id": 1, "name": "Test Lab"}],
            },
            sort_keys=False,
            allow_unicode=True,
        ),
        encoding="utf-8",
    )

    models = generate_paper._models
    generate_paper._state.paper_state.save(
        tmp_path,
        models.PaperState(current_phase=models.PaperPhase.revision_router),
    )
    generate_paper._state.research_pack.save(
        tmp_path,
        models.ResearchPack(workspace_path=str(tmp_path)),
    )
    generate_paper._state.reviews.save_round(
        tmp_path,
        models.ReviewRound(
            round_num=1,
            completed_at=datetime.utcnow(),
            reviews=[
                models.Review(
                    reviewer_profile="precision-editor",
                    verdict="revise_structural",
                    severity="warning",
                    target_layer="section",
                    issue_type="structure",
                )
            ],
        ),
    )

    rc = generate_paper.cmd_run_loop(
        argparse.Namespace(workspace=str(tmp_path), max_rounds=0)
    )

    assert rc == 0
    latest_run = generate_paper._state.runs.latest_run(tmp_path)
    assert latest_run is not None
    dispatches = generate_paper._state.runs.list_dispatches(tmp_path, latest_run)
    assert len(dispatches) == 1
    dispatch = dispatches[0]
    assert dispatch.status == "completed"
    assert dispatch.target_skill == "agentsociety-paper-architecture"
    assert dispatch.target_subagent == "producer"
    assert dispatch.envelope is not None
    assert dispatch.envelope.status == "DONE"
    assert dispatch.notes is not None
    assert "manuscript-build" in dispatch.notes


def test_run_loop_revision_router_persists_template_slot_constraint_for_anchor_drift(tmp_path: Path):
    generate_paper._ensure_paper_imports()

    paper_dir = tmp_path / "paper"
    (paper_dir / "state").mkdir(parents=True)
    _write_basic_meta(tmp_path, corresponding=True)

    models = generate_paper._models
    generate_paper._state.paper_state.save(
        tmp_path,
        models.PaperState(current_phase=models.PaperPhase.revision_router),
    )
    generate_paper._state.research_pack.save(
        tmp_path,
        models.ResearchPack(workspace_path=str(tmp_path)),
    )
    generate_paper._state.reviews.save_round(
        tmp_path,
        models.ReviewRound(
            round_num=1,
            completed_at=datetime.utcnow(),
            reviews=[
                models.Review(
                    reviewer_profile="precision-editor",
                    verdict="revise_structural",
                    severity="warning",
                    target_layer="paragraph",
                    issue_type="missing_citation_anchor",
                    raw_text="The paragraph drifted away from the evidence anchor and needs [CITE:Levy2021].",
                )
            ],
        ),
    )

    rc = generate_paper.cmd_run_loop(
        argparse.Namespace(workspace=str(tmp_path), max_rounds=0)
    )

    assert rc == 0
    state = generate_paper._state.paper_state.load(tmp_path)
    assert state.current_phase == models.PaperPhase.manuscript_build
    assert len(state.round_constraints) == 1
    constraint = state.round_constraints[0]
    assert constraint.generation_mode == "template_slots"
    assert constraint.target_artifact == "draft_section"
    assert constraint.target_layer == "paragraph"
    assert constraint.source_reviewer == "precision-editor"
    assert constraint.required_anchors == ["[CITE:Levy2021]"]
    assert "CITE_SLOT" in constraint.required_slot_types

    latest_run = generate_paper._state.runs.latest_run(tmp_path)
    assert latest_run is not None
    dispatches = generate_paper._state.runs.list_dispatches(tmp_path, latest_run)
    assert len(dispatches) == 1
    assert dispatches[0].notes is not None
    assert "mode=template_slots" in dispatches[0].notes


def test_run_loop_revision_router_records_dispatch_for_literature_search(tmp_path: Path):
    generate_paper._ensure_paper_imports()

    paper_dir = tmp_path / "paper"
    (paper_dir / "state").mkdir(parents=True)
    _write_basic_meta(tmp_path, corresponding=True)

    models = generate_paper._models
    generate_paper._state.paper_state.save(
        tmp_path,
        models.PaperState(current_phase=models.PaperPhase.revision_router),
    )
    generate_paper._state.research_pack.save(
        tmp_path,
        models.ResearchPack(workspace_path=str(tmp_path)),
    )
    generate_paper._state.reviews.save_round(
        tmp_path,
        models.ReviewRound(
            round_num=1,
            completed_at=datetime.utcnow(),
            reviews=[
                models.Review(
                    reviewer_profile="evidence-skeptic",
                    verdict="revise_structural",
                    severity="warning",
                    target_layer="evidence",
                    issue_type="missing_literature",
                )
            ],
        ),
    )

    rc = generate_paper.cmd_run_loop(
        argparse.Namespace(workspace=str(tmp_path), max_rounds=0)
    )

    assert rc == 0
    state = generate_paper._state.paper_state.load(tmp_path)
    assert state.current_phase == models.PaperPhase.evidence_audit
    assert state.counters.citation_augmentations == 1
    latest_run = generate_paper._state.runs.latest_run(tmp_path)
    assert latest_run is not None
    dispatches = generate_paper._state.runs.list_dispatches(tmp_path, latest_run)
    assert len(dispatches) == 1
    assert dispatches[0].target_skill == "agentsociety-literature-search"
    assert dispatches[0].target_subagent is None


def test_run_loop_revision_router_records_dispatch_for_analysis(tmp_path: Path):
    generate_paper._ensure_paper_imports()

    paper_dir = tmp_path / "paper"
    (paper_dir / "state").mkdir(parents=True)
    _write_basic_meta(tmp_path, corresponding=True)

    models = generate_paper._models
    generate_paper._state.paper_state.save(
        tmp_path,
        models.PaperState(current_phase=models.PaperPhase.revision_router),
    )
    generate_paper._state.research_pack.save(
        tmp_path,
        models.ResearchPack(workspace_path=str(tmp_path)),
    )
    generate_paper._state.reviews.save_round(
        tmp_path,
        models.ReviewRound(
            round_num=1,
            completed_at=datetime.utcnow(),
            reviews=[
                models.Review(
                    reviewer_profile="figure-logic-reviewer",
                    verdict="revise_structural",
                    severity="warning",
                    target_layer="figure_plan",
                    issue_type="missing_figure",
                )
            ],
        ),
    )

    rc = generate_paper.cmd_run_loop(
        argparse.Namespace(workspace=str(tmp_path), max_rounds=0)
    )

    assert rc == 0
    state = generate_paper._state.paper_state.load(tmp_path)
    assert state.current_phase == models.PaperPhase.manuscript_build
    assert state.counters.figure_regenerations == 1
    latest_run = generate_paper._state.runs.latest_run(tmp_path)
    assert latest_run is not None
    dispatches = generate_paper._state.runs.list_dispatches(tmp_path, latest_run)
    assert len(dispatches) == 1
    assert dispatches[0].target_skill == "agentsociety-analysis"
    assert dispatches[0].target_subagent is None


def test_run_loop_revision_router_opens_human_gate_for_major_pivot(tmp_path: Path):
    generate_paper._ensure_paper_imports()

    paper_dir = tmp_path / "paper"
    (paper_dir / "state").mkdir(parents=True)
    (paper_dir / "paper_meta.yaml").write_text(
        yaml.safe_dump(
            {
                "title": "Test Paper",
                "authors": [{"name": "Alice", "affils": [1], "corresponding": True, "email": "a@example.com"}],
                "affils": [{"id": 1, "name": "Test Lab"}],
            },
            sort_keys=False,
            allow_unicode=True,
        ),
        encoding="utf-8",
    )

    models = generate_paper._models
    generate_paper._state.paper_state.save(
        tmp_path,
        models.PaperState(current_phase=models.PaperPhase.revision_router),
    )
    generate_paper._state.research_pack.save(
        tmp_path,
        models.ResearchPack(workspace_path=str(tmp_path)),
    )
    generate_paper._state.reviews.save_round(
        tmp_path,
        models.ReviewRound(
            round_num=1,
            completed_at=datetime.utcnow(),
            reviews=[
                models.Review(
                    reviewer_profile="angle-critic",
                    verdict="pivot_major",
                    severity="fatal",
                    target_layer="framing",
                    issue_type="major_pivot",
                    raw_text="needs human authorization",
                )
            ],
        ),
    )

    rc = generate_paper.cmd_run_loop(
        argparse.Namespace(workspace=str(tmp_path), max_rounds=0)
    )

    assert rc == 1
    assert generate_paper._state.human_gates.has_pending(tmp_path)
    state = generate_paper._state.paper_state.load(tmp_path)
    assert state.release_status == models.ReleaseStatus.blocked
    assert state.pending_human_gate is not None


def test_run_loop_revision_router_records_dispatch_for_human_gate(tmp_path: Path):
    generate_paper._ensure_paper_imports()

    paper_dir = tmp_path / "paper"
    (paper_dir / "state").mkdir(parents=True)
    (paper_dir / "paper_meta.yaml").write_text(
        yaml.safe_dump(
            {
                "title": "Test Paper",
                "authors": [{"name": "Alice", "affils": [1], "corresponding": True, "email": "a@example.com"}],
                "affils": [{"id": 1, "name": "Test Lab"}],
            },
            sort_keys=False,
            allow_unicode=True,
        ),
        encoding="utf-8",
    )

    models = generate_paper._models
    generate_paper._state.paper_state.save(
        tmp_path,
        models.PaperState(current_phase=models.PaperPhase.revision_router),
    )
    generate_paper._state.research_pack.save(
        tmp_path,
        models.ResearchPack(workspace_path=str(tmp_path)),
    )
    generate_paper._state.reviews.save_round(
        tmp_path,
        models.ReviewRound(
            round_num=1,
            completed_at=datetime.utcnow(),
            reviews=[
                models.Review(
                    reviewer_profile="angle-critic",
                    verdict="pivot_major",
                    severity="fatal",
                    target_layer="framing",
                    issue_type="major_pivot",
                    raw_text="needs human authorization",
                )
            ],
        ),
    )

    rc = generate_paper.cmd_run_loop(
        argparse.Namespace(workspace=str(tmp_path), max_rounds=0)
    )

    assert rc == 1
    latest_run = generate_paper._state.runs.latest_run(tmp_path)
    assert latest_run is not None
    dispatches = generate_paper._state.runs.list_dispatches(tmp_path, latest_run)
    assert len(dispatches) == 1
    dispatch = dispatches[0]
    assert dispatch.status == "completed"
    assert dispatch.target_skill == "human-gate"
    assert dispatch.target_subagent is None
    assert dispatch.envelope is not None
    assert dispatch.envelope.status == "DONE"
    assert dispatch.notes is not None
    assert "human_gate" in dispatch.notes


def test_run_loop_revision_router_opens_human_gate_when_figure_cap_exceeded(tmp_path: Path):
    generate_paper._ensure_paper_imports()

    paper_dir = tmp_path / "paper"
    (paper_dir / "state").mkdir(parents=True)
    (paper_dir / "paper_meta.yaml").write_text(
        yaml.safe_dump(
            {
                "title": "Test Paper",
                "authors": [{"name": "Alice", "affils": [1], "corresponding": True, "email": "a@example.com"}],
                "affils": [{"id": 1, "name": "Test Lab"}],
            },
            sort_keys=False,
            allow_unicode=True,
        ),
        encoding="utf-8",
    )

    models = generate_paper._models
    generate_paper._state.paper_state.save(
        tmp_path,
        models.PaperState(
            current_phase=models.PaperPhase.revision_router,
            counters=models.Counters(figure_regenerations=2, citation_augmentations=0),
        ),
    )
    generate_paper._state.research_pack.save(
        tmp_path,
        models.ResearchPack(workspace_path=str(tmp_path)),
    )
    generate_paper._state.reviews.save_round(
        tmp_path,
        models.ReviewRound(
            round_num=1,
            completed_at=datetime.utcnow(),
            reviews=[
                models.Review(
                    reviewer_profile="figure-logic-reviewer",
                    verdict="revise_structural",
                    severity="warning",
                    target_layer="figure_plan",
                    issue_type="missing_figure",
                )
            ],
        ),
    )

    rc = generate_paper.cmd_run_loop(
        argparse.Namespace(workspace=str(tmp_path), max_rounds=0)
    )

    assert rc == 1
    assert generate_paper._state.human_gates.has_pending(tmp_path)


def test_run_loop_revision_router_opens_human_gate_when_citation_cap_exceeded(tmp_path: Path):
    generate_paper._ensure_paper_imports()

    paper_dir = tmp_path / "paper"
    (paper_dir / "state").mkdir(parents=True)
    (paper_dir / "paper_meta.yaml").write_text(
        yaml.safe_dump(
            {
                "title": "Test Paper",
                "authors": [{"name": "Alice", "affils": [1], "corresponding": True, "email": "a@example.com"}],
                "affils": [{"id": 1, "name": "Test Lab"}],
            },
            sort_keys=False,
            allow_unicode=True,
        ),
        encoding="utf-8",
    )

    models = generate_paper._models
    generate_paper._state.paper_state.save(
        tmp_path,
        models.PaperState(
            current_phase=models.PaperPhase.revision_router,
            counters=models.Counters(figure_regenerations=0, citation_augmentations=2),
        ),
    )
    generate_paper._state.research_pack.save(
        tmp_path,
        models.ResearchPack(workspace_path=str(tmp_path)),
    )
    generate_paper._state.reviews.save_round(
        tmp_path,
        models.ReviewRound(
            round_num=1,
            completed_at=datetime.utcnow(),
            reviews=[
                models.Review(
                    reviewer_profile="evidence-skeptic",
                    verdict="revise_structural",
                    severity="warning",
                    target_layer="evidence",
                    issue_type="missing_literature",
                )
            ],
        ),
    )

    rc = generate_paper.cmd_run_loop(
        argparse.Namespace(workspace=str(tmp_path), max_rounds=0)
    )

    assert rc == 1
    assert generate_paper._state.human_gates.has_pending(tmp_path)


def test_run_loop_revision_router_records_dispatch_for_release_gate(tmp_path: Path):
    generate_paper._ensure_paper_imports()

    paper_dir = tmp_path / "paper"
    (paper_dir / "state").mkdir(parents=True)
    (paper_dir / "paper_meta.yaml").write_text(
        yaml.safe_dump(
            {
                "title": "Test Paper",
                "authors": [{"name": "Alice", "affils": [1], "corresponding": True, "email": "a@example.com"}],
                "affils": [{"id": 1, "name": "Test Lab"}],
            },
            sort_keys=False,
            allow_unicode=True,
        ),
        encoding="utf-8",
    )

    models = generate_paper._models
    generate_paper._state.paper_state.save(
        tmp_path,
        models.PaperState(current_phase=models.PaperPhase.revision_router),
    )
    generate_paper._state.research_pack.save(
        tmp_path,
        models.ResearchPack(workspace_path=str(tmp_path)),
    )
    generate_paper._state.reviews.save_round(
        tmp_path,
        models.ReviewRound(
            round_num=1,
            completed_at=datetime.utcnow(),
            reviews=[
                models.Review(
                    reviewer_profile="precision-editor",
                    verdict="accept",
                    severity="info",
                    resolved_state="resolved",
                )
            ],
            unresolved_fatal=[],
        ),
    )

    rc = generate_paper.cmd_run_loop(
        argparse.Namespace(workspace=str(tmp_path), max_rounds=0)
    )

    assert rc == 0
    state = generate_paper._state.paper_state.load(tmp_path)
    assert state.current_phase == models.PaperPhase.release_gate
    latest_run = generate_paper._state.runs.latest_run(tmp_path)
    assert latest_run is not None
    dispatches = generate_paper._state.runs.list_dispatches(tmp_path, latest_run)
    assert len(dispatches) == 1
    dispatch = dispatches[0]
    assert dispatch.status == "completed"
    assert dispatch.target_skill == "paper-orchestrator"
    assert dispatch.target_subagent == "release-gate-judge"
    assert dispatch.envelope is not None
    assert dispatch.envelope.status == "DONE"
    assert dispatch.notes == "all unresolved issues cleared; route to release-gate"


def test_run_loop_release_gate_marks_paper_ready(tmp_path: Path):
    generate_paper._ensure_paper_imports()

    paper_dir = tmp_path / "paper"
    manuscript_dir = paper_dir / "artifacts" / "manuscript"
    manuscript_dir.mkdir(parents=True)
    (paper_dir / "state").mkdir(parents=True, exist_ok=True)
    (paper_dir / "paper_meta.yaml").write_text(
        yaml.safe_dump(
            {
                "title": "Test Paper",
                "authors": [{"name": "Alice", "affils": [1], "corresponding": True, "email": "a@example.com"}],
                "affils": [{"id": 1, "name": "Test Lab"}],
            },
            sort_keys=False,
            allow_unicode=True,
        ),
        encoding="utf-8",
    )

    models = generate_paper._models
    generate_paper._state.paper_state.save(
        tmp_path,
        models.PaperState(current_phase=models.PaperPhase.release_gate),
    )
    generate_paper._state.research_pack.save(
        tmp_path,
        models.ResearchPack(
            workspace_path=str(tmp_path),
            analyses=[
                models.ResearchPackAnalysis(
                    analysis_id="analysis:1",
                    hypothesis_id="1",
                    summary="Supported analysis",
                )
            ],
        ),
    )
    generate_paper._state.storyline.save(
        tmp_path,
        models.StorylineMap(
            current_angle="Strong angle",
            contribution_statement="Clear contribution",
        ),
    )
    generate_paper._state.claim_ledger.save(
        tmp_path,
        models.ClaimLedger(
            claims=[
                models.Claim(
                    claim_id="C1",
                    claim_text="Supported claim",
                    evidence_support=["analysis:1"],
                )
            ]
        ),
    )
    generate_paper._state.figure_argument.save(
        tmp_path,
        models.FigureArgumentMap(
            figures=[
                models.FigureSpec(
                    figure_id="F1",
                    claim_supported=["C1"],
                    status="rendered",
                )
            ]
        ),
    )
    generate_paper._state.reviews.save_round(
        tmp_path,
        models.ReviewRound(
            round_num=1,
            completed_at=datetime.utcnow(),
            reviews=[
                models.Review(
                    reviewer_profile="precision-editor",
                    verdict="accept",
                    severity="info",
                )
            ],
            unresolved_fatal=[],
        ),
    )
    timestamp, run_dir = generate_paper._state.runs.open_run(
        tmp_path, timestamp="20260507_123000"
    )
    out_dir = run_dir / "compose" / "out"
    out_dir.mkdir(parents=True)
    (out_dir / "paper.pdf").write_bytes(b"x" * (10 * 1024 + 32))

    rc = generate_paper.cmd_run_loop(
        argparse.Namespace(workspace=str(tmp_path), max_rounds=0)
    )

    assert timestamp == "20260507_123000"
    assert rc == 0
    state = generate_paper._state.paper_state.load(tmp_path)
    assert state.release_status == models.ReleaseStatus.ready


def test_run_loop_release_gate_blocks_unknown_claim_analysis_support(tmp_path: Path):
    generate_paper._ensure_paper_imports()

    paper_dir = tmp_path / "paper"
    manuscript_dir = paper_dir / "artifacts" / "manuscript"
    manuscript_dir.mkdir(parents=True)
    (paper_dir / "state").mkdir(parents=True, exist_ok=True)
    (manuscript_dir / "main.md").write_text("Body", encoding="utf-8")
    (paper_dir / "paper_meta.yaml").write_text(
        yaml.safe_dump(
            {
                "title": "Test Paper",
                "authors": [{"name": "Alice", "affils": [1], "corresponding": True, "email": "a@example.com"}],
                "affils": [{"id": 1, "name": "Test Lab"}],
            },
            sort_keys=False,
            allow_unicode=True,
        ),
        encoding="utf-8",
    )

    models = generate_paper._models
    generate_paper._state.paper_state.save(
        tmp_path,
        models.PaperState(current_phase=models.PaperPhase.release_gate),
    )
    generate_paper._state.research_pack.save(
        tmp_path,
        models.ResearchPack(workspace_path=str(tmp_path)),
    )
    generate_paper._state.storyline.save(
        tmp_path,
        models.StorylineMap(
            current_angle="Strong angle",
            contribution_statement="Clear contribution",
        ),
    )
    generate_paper._state.claim_ledger.save(
        tmp_path,
        models.ClaimLedger(
            claims=[
                models.Claim(
                    claim_id="C1",
                    claim_text="Unsupported claim",
                    evidence_support=["analysis:missing"],
                )
            ]
        ),
    )
    generate_paper._state.figure_argument.save(
        tmp_path,
        models.FigureArgumentMap(figures=[]),
    )
    generate_paper._state.reviews.save_round(
        tmp_path,
        models.ReviewRound(
            round_num=1,
            completed_at=datetime.utcnow(),
            reviews=[
                models.Review(
                    reviewer_profile="precision-editor",
                    verdict="accept",
                    severity="info",
                )
            ],
            unresolved_fatal=[],
        ),
    )
    timestamp, run_dir = generate_paper._state.runs.open_run(
        tmp_path, timestamp="20260507_123100"
    )
    out_dir = run_dir / "compose" / "out"
    out_dir.mkdir(parents=True)
    (out_dir / "paper.pdf").write_bytes(b"x" * (10 * 1024 + 32))

    rc = generate_paper.cmd_run_loop(
        argparse.Namespace(workspace=str(tmp_path), max_rounds=0)
    )

    assert timestamp == "20260507_123100"
    assert rc == 2


def test_human_gate_decide_accept_routes_back_to_requested_phase(tmp_path: Path):
    generate_paper._ensure_paper_imports()

    models = generate_paper._models
    generate_paper._state.paper_state.save(
        tmp_path,
        models.PaperState(
            current_phase=models.PaperPhase.revision_router,
            pending_human_gate="gate-test",
            release_status=models.ReleaseStatus.blocked,
        ),
    )
    generate_paper._state.human_gates.open_gate(
        tmp_path,
        gate_id="gate-test",
        triggering_issue="major_pivot",
        proposed_pivot="framing",
        severity="major",
    )

    rc = generate_paper.cmd_human_gate_decide(
        argparse.Namespace(
            workspace=str(tmp_path),
            gate_id="gate-test",
            decision="accept",
            accepted_version="manuscript-build",
            note=None,
        )
    )

    assert rc == 0
    state = generate_paper._state.paper_state.load(tmp_path)
    assert state.current_phase == models.PaperPhase.manuscript_build
    assert state.release_status == models.ReleaseStatus.in_review
    assert state.pending_human_gate is None


def test_status_reports_round_constraint_count(tmp_path: Path, capsys):
    generate_paper._ensure_paper_imports()

    models = generate_paper._models
    generate_paper._state.paper_state.save(
        tmp_path,
        models.PaperState(
            current_phase=models.PaperPhase.manuscript_build,
            round_constraints=[
                models.RoundConstraint(
                    constraint_id="test-constraint",
                    generation_mode="template_slots",
                    issue_type="missing_anchor",
                )
            ],
        ),
    )

    rc = generate_paper.cmd_status(argparse.Namespace(workspace=str(tmp_path)))

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["success"] is True
    assert "round_constraints=1" in payload["envelope"]["key_findings"]
    assert len(payload["state"]["round_constraints"]) == 1


def test_human_gate_decide_reject_keeps_paper_blocked(tmp_path: Path):
    generate_paper._ensure_paper_imports()

    models = generate_paper._models
    generate_paper._state.paper_state.save(
        tmp_path,
        models.PaperState(
            current_phase=models.PaperPhase.revision_router,
            pending_human_gate="gate-test",
            release_status=models.ReleaseStatus.blocked,
        ),
    )
    generate_paper._state.human_gates.open_gate(
        tmp_path,
        gate_id="gate-test",
        triggering_issue="major_pivot",
        proposed_pivot="framing",
        severity="major",
    )

    rc = generate_paper.cmd_human_gate_decide(
        argparse.Namespace(
            workspace=str(tmp_path),
            gate_id="gate-test",
            decision="reject",
            accepted_version=None,
            note="rejected",
        )
    )

    assert rc == 0
    state = generate_paper._state.paper_state.load(tmp_path)
    assert state.release_status == models.ReleaseStatus.blocked
    assert state.pending_human_gate == "gate-test"


def test_release_marks_ready_paper_as_released(tmp_path: Path):
    generate_paper._ensure_paper_imports()

    models = generate_paper._models
    generate_paper._state.reviews.save_round(
        tmp_path,
        models.ReviewRound(
            round_num=1,
            completed_at=datetime.utcnow(),
            reviews=[
                models.Review(
                    reviewer_profile="precision-editor",
                    verdict="accept",
                    severity="info",
                )
            ],
        ),
    )
    generate_paper._state.paper_state.save(
        tmp_path,
        models.PaperState(
            current_phase=models.PaperPhase.release_gate,
            release_status=models.ReleaseStatus.ready,
        ),
    )

    rc = generate_paper.cmd_release(
        argparse.Namespace(workspace=str(tmp_path))
    )

    assert rc == 0
    state = generate_paper._state.paper_state.load(tmp_path)
    assert state.release_status == models.ReleaseStatus.released


def test_release_requires_completed_latest_review_round(tmp_path: Path):
    generate_paper._ensure_paper_imports()

    paper_dir = tmp_path / "paper"
    (paper_dir / "state").mkdir(parents=True, exist_ok=True)

    models = generate_paper._models
    generate_paper._state.paper_state.save(
        tmp_path,
        models.PaperState(
            current_phase=models.PaperPhase.release_gate,
            release_status=models.ReleaseStatus.ready,
        ),
    )
    generate_paper._state.reviews.save_round(
        tmp_path,
        models.ReviewRound(
            round_num=1,
            reviews=[
                models.Review(
                    reviewer_profile="precision-editor",
                    verdict="accept",
                    severity="info",
                )
            ],
        ),
    )

    rc = generate_paper.cmd_release(argparse.Namespace(workspace=str(tmp_path)))

    assert rc == 2
