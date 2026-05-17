"""Tests for the extension analysis CLI helpers."""

from importlib.util import module_from_spec, spec_from_file_location
import json
from pathlib import Path

import pytest


def _load_analysis_cli_module():
    repo_root = Path(__file__).resolve().parents[3]
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
