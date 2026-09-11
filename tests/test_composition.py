from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import cast

import matplotlib as mpl
import pytest
from matplotlib.figure import Figure
from matplotlib.patches import Rectangle

from red_five import component_export, sections, standalone
from red_five.cli import main
from red_five.component_export import (
    Component,
    export_components,
    options_from_dict,
    selection_from_dict,
    verify_components,
)
from red_five.composition import PlotOptions, Selection
from red_five.contracts import ContractError
from red_five.evaluation import evaluate
from red_five.rendering import verify_bundle
from red_five.reporting import (
    canonical,
    seal_report,
    software_versions,
    source_identity,
)
from red_five.sections import SectionName, SectionResult, evaluate_section
from red_five.signal_io import digest, json_object
from red_five.visualization import ReportView, mapping, sequence

ROOT = Path(__file__).resolve().parents[1]
SIGNALS = (ROOT / "examples/signals.csv").read_bytes()
CONFIG = (ROOT / "examples/evaluation.json").read_bytes()
WEIGHTS = (ROOT / "examples/weights.csv").read_bytes()


def section(name: SectionName = "standalone") -> SectionResult:
    return evaluate_section(
        name,
        SIGNALS,
        CONFIG,
        b"plan",
        b"lock",
        weight_bytes=WEIGHTS if name == "economics" else None,
    )


@pytest.mark.parametrize("name", ["standalone", "coverage", "economics"])
def test_independent_sections_match_full_report(name: SectionName) -> None:
    report = evaluate(
        SIGNALS,
        CONFIG,
        b"plan",
        b"lock",
        code_identity=source_identity(),
        software=software_versions(),
        weight_bytes=WEIGHTS,
    )
    extracted = ReportView(seal_report(report)).section(name)
    independent = section(name)
    assert extracted.data == independent.data
    assert extracted.status == independent.status
    assert (
        extracted.section_id != independent.section_id
    )  # Different lineage, same values.


def test_dependency_isolation(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("unrelated computation invoked")

    monkeypatch.setattr(sections, "account_weights", fail)
    monkeypatch.setattr(sections, "parse_weights", fail)
    assert section().status == "computed"
    monkeypatch.setattr(standalone, "correlations", fail)
    assert section("coverage").data.columns[-1] == "missing_mature_labels"


def test_economics_never_computes_correlations(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("unrelated diagnostics invoked")

    monkeypatch.setattr(sections, "evaluate_groups", fail)
    assert section("economics").data.rows[0][-2] == "0.01438"


def test_missing_and_unrelated_weights_rejected() -> None:
    with pytest.raises(ContractError, match="requires supplied"):
        evaluate_section("economics", SIGNALS, CONFIG, b"p", b"l")
    with pytest.raises(ContractError, match="not an input"):
        evaluate_section("standalone", SIGNALS, CONFIG, b"p", b"l", weight_bytes=b"bad")
    with pytest.raises(ContractError, match="not represented"):
        evaluate_section(
            "economics",
            SIGNALS,
            CONFIG,
            b"p",
            b"l",
            weight_bytes=WEIGHTS.replace(b",ES,", b",OTHER,"),
        )


def test_selection_exact_values_and_no_recalculation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result = section()
    original = result.content

    def fail(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("rendering recalculated results")

    monkeypatch.setattr(sections, "evaluate_groups", fail)
    panel = result.select(
        Selection(model_ids=("ES-model",), columns=("model_id", "rank_ic"), precision=2)
    )
    assert panel.table().shape == (1, 2)
    assert panel.table()["rank_ic"][0] == 1
    assert "displaying 1/2" in panel.html() and "1 omitted" in panel.html()
    assert "1.00" in panel.html()
    panel.figure(
        options=PlotOptions(colors=("#123456",), metrics=("rank_ic",), ylim=(-0.5, 0.5))
    )
    assert result.content == original
    empty = result.select(Selection(model_ids=("missing",)))
    assert empty.table().height == 0 and "displaying 0/2" in empty.html()
    assert "Unavailable" in empty.figure().axes[0].texts[0].get_text()


def test_caller_axes_and_global_style_preserved() -> None:
    fig = Figure(figsize=(10, 8))
    left = fig.add_subplot(211)
    right = fig.add_subplot(212)
    right.title.set_text("untouched")
    before = dict(mpl.rcParams)
    panel = section().select()
    assert (
        panel.plot(ax=left, options=PlotOptions(title="My signal", font_size=12))
        is left
    )
    assert len(fig.axes) == 2 and right.get_title() == "untouched"
    assert dict(mpl.rcParams) == before
    assert left.get_title() == "My signal"
    with pytest.raises(ContractError, match="occupied"):
        panel.plot(ax=left)
    panel.plot(ax=left, options=PlotOptions(overlay=True, label_prefix="repeat "))
    with pytest.raises(ContractError, match="occupied"):
        section("economics").select().plot(ax=left, options=PlotOptions(overlay=True))


def test_plot_styles_and_table_sorting() -> None:
    panel = section("economics").select(
        Selection(sort_by="net_return", descending=False)
    )
    assert panel.table()["net_return"].to_list() == ["-0.000603", "0.01438"]
    fig = panel.figure(
        options=PlotOptions(
            figsize=(6, 4),
            dpi=80,
            legend=False,
            metrics=("net_return",),
            title="Custom",
            yscale="symlog",
        )
    )
    assert fig.dpi == 80
    assert fig.axes[0].get_yscale() == "symlog"
    assert [
        cast(Rectangle, p).get_height() for p in fig.axes[0].patches
    ] == pytest.approx([-0.000603, 0.01438])
    assert any("clipped" in t.get_text() for t in fig.axes[0].texts)


@pytest.mark.parametrize(
    "options",
    [
        {"dpi": 1000},
        {"colors": ("red",)},
        {"markers": ("bad",)},
        {"yscale": "log"},
        {"ylim": (1, -1)},
        {"figsize": (0, 2)},
        {"font_size": 40},
        {"metrics": ("rank_ic", "rank_ic")},
    ],
)
def test_invalid_plot_options(options: dict[str, object]) -> None:
    spec = asdict(PlotOptions())
    spec.update(options)
    # Round-trip through JSON to exercise the external display-specification boundary.
    with pytest.raises(ContractError):
        options_from_dict(json_object(canonical(spec)))


def test_selection_and_kind_errors() -> None:
    for selection in (
        Selection(portfolio_ids=("unknown",)),
        Selection(columns=("bad",)),
        Selection(sort_by="bad"),
        Selection(decision_times=("2026-01-01",)),
    ):
        with pytest.raises(ContractError):
            section().select(selection)
    with pytest.raises(ContractError):
        Selection(precision=20)
    with pytest.raises(ContractError):
        Selection(columns=("model_id", "model_id"))
    with pytest.raises(ContractError):
        section("coverage").select().figure("correlations")
    with pytest.raises(ContractError):
        section().select().figure(options=PlotOptions(metrics=("net_return",)))


def test_single_table_export_skips_all_plotting(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("table-only export attempted a figure")

    monkeypatch.setattr(component_export, "figure_bytes", fail)
    output = tmp_path / "table-only"
    export_components(
        [Component(section().select(Selection(model_ids=("ES-model",))))], output
    )
    assert verify_bundle(output)["scope"] == "partial"
    assert not list(output.glob("*.svg"))
    assert not (output / "report.json").exists()


def test_custom_collection_reproducible_and_tamper(tmp_path: Path) -> None:
    selection = Selection(model_ids=("ES-model",), precision=3)
    options = PlotOptions(
        colors=("#123456",), metrics=("rank_ic",), title="Chosen signal"
    )
    components = [
        Component(section().select(selection), "correlations", options),
        Component(section("economics").select()),
    ]
    output = tmp_path / "custom"
    assert export_components(components, output) == output / "index.html"
    assert export_components(components, output) == output / "index.html"
    manifest = verify_components(output)
    record = mapping(sequence(manifest["components"])[0])
    assert selection_from_dict(mapping(record["selection"])) == selection
    assert options_from_dict(mapping(record["options"])) == options
    assert "Chosen signal" in (output / "component-01.svg").read_text()
    (output / "component-01.csv").write_text("tampered")
    with pytest.raises(ContractError, match="digest"):
        verify_components(output)


def test_partial_manifest_and_section_attacks(tmp_path: Path) -> None:
    output = tmp_path / "parts"
    export_components([Component(section().select())], output)
    manifest = json_object((output / "manifest.json").read_bytes())
    mapping(sequence(manifest["components"])[0])["source"] = "../outside.json"
    (output / "manifest.json").write_bytes(canonical(manifest))
    with pytest.raises(ContractError, match="source filename"):
        verify_components(output)
    with pytest.raises(ContractError):
        SectionResult(section().content.replace(b"ES-model", b"XX-model"))
    payload = json_object(section().content)
    payload.pop("section_id")
    payload["scope"] = "complete"
    with pytest.raises(ContractError):
        SectionResult(canonical({**payload, "section_id": digest(canonical(payload))}))


def test_new_sample_changes_identity_and_maturity() -> None:
    config = json_object(CONFIG)
    config["as_of"] = "2026-01-09T16:00:00Z"
    altered = evaluate_section(
        "standalone", SIGNALS, canonical(config), b"plan", b"lock"
    )
    assert altered.section_id != section().section_id
    assert altered.data.rows[0][altered.data.columns.index("immature_labels")] == 1


def test_partial_failure_is_clean(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail(_path: Path) -> dict[str, object]:
        raise OSError("injected partial publication failure")

    monkeypatch.setattr(component_export, "verify_components", fail)
    with pytest.raises(OSError, match="injected"):
        export_components([Component(section().select())], tmp_path / "partial")
    assert not (tmp_path / "partial").exists()


def test_partial_cli_and_companion_table(tmp_path: Path) -> None:
    panel = section().select()
    output = tmp_path / "one"
    panel.export(output)
    assert main(["verify-bundle", str(output)]) == 0
    narrow = section().select(Selection(columns=("model_id",)))
    with pytest.raises(ContractError, match="plotted metrics"):
        narrow.export(tmp_path / "bad", kind="correlations")
    assert not (tmp_path / "bad").exists()
