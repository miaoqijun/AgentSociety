from __future__ import annotations

import argparse
import json
from pathlib import Path

import yaml  # type: ignore[import-untyped]

from agentsociety2.skills.paper.cli import generate_paper


def test_status_parser_defaults_workspace_to_current_dir():
    parser = generate_paper.build_parser()

    args = parser.parse_args(["status"])

    assert args.workspace == "."
    assert args.func is generate_paper.cmd_status


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
    literature_dir = workspace / "papers"
    manuscript_dir.mkdir(parents=True)
    literature_dir.mkdir(parents=True)
    (manuscript_dir / "main.md").write_text(
        "Body with [FIG:F1] and [CITE:Entry302024].",
        encoding="utf-8",
    )

    meta = {
        "title": "Test Paper",
        "authors": [{"name": "Alice", "affils": [1], "corresponding": True, "email": "a@example.com"}],
        "affils": [{"id": 1, "name": "Test Lab"}],
    }
    (paper_dir / "paper_meta.yaml").write_text(
        yaml.safe_dump(meta, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    (literature_dir / "literature_index.json").write_text(
        json.dumps(
            {
                "entries": [
                    {"title": f"Entry{index} Title", "year": 2024}
                    for index in range(31)
                ]
            }
        ),
        encoding="utf-8",
    )

    compiler = generate_paper._compiler
    models = generate_paper._models
    research_pack = models.ResearchPack(
        workspace_path=str(workspace),
        literature=[
            models.ResearchPackLiterature(
                cite_key=f"Entry{index}2024",
                title=f"Entry{index} Title",
            )
            for index in range(31)
        ],
    )
    generate_paper._state.research_pack.save(workspace, research_pack)

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
