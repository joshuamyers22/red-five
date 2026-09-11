from __future__ import annotations

import csv
import io
from dataclasses import FrozenInstanceError
from pathlib import Path
from typing import cast

import pytest
from matplotlib.patches import Rectangle

from red_five import rendering
from red_five.cli import main
from red_five.contracts import ContractError
from red_five.evaluation import evaluate
from red_five.reporting import canonical, seal_report
from red_five.signal_io import json_object
from red_five.visualization import (
    ReportView,
    Table,
    load_report,
    mapping,
    number,
    sequence,
    text_cell,
)

ROOT = Path(__file__).resolve().parents[1]


def evidence(*, weights: bool = True) -> dict[str, object]:
    return evaluate(
        (ROOT / "examples/signals.csv").read_bytes(),
        (ROOT / "examples/evaluation.json").read_bytes(),
        b"plan",
        b"lock",
        code_identity={"revision": "fixture"},
        software={"runtime": "fixture"},
        weight_bytes=(ROOT / "examples/weights.csv").read_bytes() if weights else None,
    )


def view() -> ReportView:
    return ReportView(seal_report(evidence()))


def test_exact_tables_and_chart_data() -> None:
    item = view()
    assert item.table().height == 2
    assert item.table("economics")["net_return"][0] == "0.01438"
    fig = item.figure("returns")
    heights = [cast(Rectangle, patch).get_height() for patch in fig.axes[0].patches]
    assert heights == pytest.approx([0.015, 0, 0.01438, -0.000603])
    assert item.figure().axes[0].get_ylim() == (-1.05, 1.05)
    assert item.figure("coverage").axes[0].get_ylabel() == "Observations"
    frame = item.table()
    frame.replace_column(0, frame.get_column("model_id").rename("changed"))
    assert item.table().columns[0] == "model_id"


def test_notebook_html_and_safe_exports() -> None:
    report = evidence()
    groups = sequence(report["standalone"])
    mapping(groups[0])["group"] = ["<script>alert(1)</script>", "=CMD()", "001"]
    item = ReportView(seal_report(report))
    html = item.html()
    assert "<script>" not in html
    assert "&lt;script&gt;" in html and "<svg" in html
    assert "unavailable in this full-report schema" in html
    assert "=CMD()" in item.tables["signals"].csv().decode()
    table = Table(
        ("text", "number"),
        (("=CMD()", -1.25), ("\\N", None), ("'quoted", 0), ("a\tb", 1)),
    )
    rows = list(csv.reader(io.StringIO(table.csv().decode())))
    assert rows[1] == ["'=CMD()", "-1.25"]
    assert rows[2] == ["'\\N", "\\N"]
    assert rows[3][0] == "''quoted"
    assert rows[4][0] == "'a\tb"


def test_missing_metrics_and_no_weights() -> None:
    report = evidence(weights=False)
    row = mapping(sequence(report["standalone"])[0])
    row.update(
        pearson_ic=None,
        rank_ic=None,
        status="unavailable",
        reason="constant-score-or-target",
    )
    item = ReportView(seal_report(report))
    assert item.table()["pearson_ic"][0] is None
    assert "unavailable" in item.tables["signals"].html("Signals")
    assert item.table("economics").height == 0
    assert "Unavailable" in item.figure("costs").axes[0].texts[0].get_text()
    assert "unavailable" in item.figure().axes[0].texts[0].get_text()


def test_pagination_and_unknown_views() -> None:
    report = evidence()
    groups = sequence(report["standalone"])
    report["standalone"] = groups * 11
    item = ReportView(seal_report(report))
    assert len(item.figure(page=1).axes[0].get_xticks()) == 2
    for kind, page in [("wrong", 0), ("coverage", 2), ("returns", -1), ("costs", True)]:
        with pytest.raises(ContractError):
            item.figure(kind, page)
    with pytest.raises(ContractError):
        item.table("unknown")


@pytest.mark.parametrize(
    "field,value",
    [
        ("status", "accept"),
        ("mode", "unknown"),
        ("group_fields", list[str]()),
        ("standalone", [None]),
        ("standalone", [None] * 201),
    ],
)
def test_unsupported_report(field: str, value: object) -> None:
    report = evidence()
    report[field] = value
    with pytest.raises(ContractError):
        ReportView(seal_report(report))


@pytest.mark.parametrize(
    "field,value",
    [
        ("group", ["bad"]),
        ("observations", -1),
        ("pearson_ic", 2),
        ("status", "bad"),
        ("status", "unavailable"),
    ],
)
def test_bad_metric(field: str, value: object) -> None:
    report = evidence()
    mapping(sequence(report["standalone"])[0])[field] = value
    with pytest.raises(ContractError):
        ReportView(seal_report(report))


@pytest.mark.parametrize("amount", ["NaN", "1e40", "not-numeric"])
def test_bad_accounting(amount: str) -> None:
    report = evidence()
    mapping(sequence(mapping(report["economics"])["periods"])[0])["net_return"] = amount
    with pytest.raises(ContractError):
        ReportView(seal_report(report))


def test_boundary_helpers() -> None:
    for value in [None, True, "4", float("inf")]:
        with pytest.raises(ContractError):
            number(value)
    with pytest.raises(ContractError):
        number(1.5, count=True)
    with pytest.raises(ContractError):
        text_cell("x" * 1025)
    with pytest.raises(ContractError):
        sequence(None)


def test_bundle_roundtrip_idempotent_and_tamper(tmp_path: Path) -> None:
    item = view()
    output = tmp_path / "bundle"
    original = item.content
    assert item.export(output).name == "index.html"
    assert rendering.verify_bundle(output)["run_id"] == item.run_id
    assert item.export(output) == output / "index.html"
    assert item.content == original == (output / "report.json").read_bytes()
    assert (output / "correlations-01.png").read_bytes().startswith(b"\x89PNG")
    (output / "signals.csv").write_text("changed")
    with pytest.raises(ContractError, match="digest"):
        rendering.verify_bundle(output)


def test_bundle_unsafe_names_and_symlinks(tmp_path: Path) -> None:
    output = tmp_path / "bundle"
    view().export(output)
    manifest = json_object((output / "manifest.json").read_bytes())
    mapping(manifest["files"])["../outside.csv"] = "bad"
    (output / "manifest.json").write_bytes(canonical(manifest))
    with pytest.raises(ContractError, match="unsafe"):
        rendering.verify_bundle(output)
    alias = tmp_path / "alias"
    alias.symlink_to(output, target_is_directory=True)
    with pytest.raises(ContractError, match="symlink"):
        rendering.verify_bundle(alias)


def test_budget_and_publication_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    item = view()
    monkeypatch.setattr(rendering, "MAX_BUNDLE_BYTES", 1)
    with pytest.raises(ContractError, match="budget"):
        item.export(tmp_path / "oversize")
    assert not (tmp_path / "oversize").exists()
    monkeypatch.setattr(rendering, "MAX_BUNDLE_BYTES", 32 * 1024 * 1024)
    monkeypatch.setattr(rendering, "MAX_SECONDS", -1)
    with pytest.raises(ContractError, match="time"):
        item.html()
    with pytest.raises(ContractError, match="time"):
        item.export(tmp_path / "timeout")


def test_cli_and_malformed_input(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "report.json"
    path.write_bytes(seal_report(evidence()))
    output = tmp_path / "bundle"
    assert main(["render", str(path), "--output-dir", str(output)]) == 0
    assert main(["verify-bundle", str(output)]) == 0
    assert '"status": "verified"' in capsys.readouterr().out
    path.write_bytes(seal_report({"schema_version": "bad"}))
    assert main(["render", str(path), "--output-dir", str(output)]) == 2
    assert "evaluation_failed" in capsys.readouterr().err
    bad = evidence()
    mapping(bad["identity"]).pop("config")
    # Reseal identity to test a malformed but correctly hashed artifact.
    from red_five.reporting import canonical
    from red_five.signal_io import digest

    bad["run_id"] = digest(canonical(bad["identity"]))
    path.write_bytes(seal_report(bad))
    with pytest.raises(ContractError):
        load_report(path)


def test_cross_sectional_labels() -> None:
    report = evidence()
    config = mapping(mapping(report["identity"])["config"])
    config["mode"] = report["mode"] = "cross_sectional"
    report["group_fields"] = ["model_id", "decision_time"]
    for item in sequence(report["standalone"]):
        mapping(item)["group"] = ["model", "2026-01-05T14:00:00+00:00"]
    from red_five.signal_io import digest

    report["run_id"] = digest(canonical(report["identity"]))
    assert ReportView(seal_report(report)).table().columns[1] == "decision_time"


def test_view_is_immutable() -> None:
    item = view()
    with pytest.raises(FrozenInstanceError):
        item.status = "accept"  # pyright: ignore[reportAttributeAccessIssue]
    with pytest.raises(TypeError):
        cast(dict[str, Table], item.tables)["signals"] = Table((), ())


def test_mid_publish_failure_removes_only_owned_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sibling = tmp_path / "keep.txt"
    sibling.write_text("keep")

    def fail(_path: Path) -> dict[str, object]:
        raise OSError("injected verification failure")

    monkeypatch.setattr(rendering, "verify_bundle", fail)
    with pytest.raises(OSError, match="injected"):
        view().export(tmp_path / "partial")
    assert not (tmp_path / "partial").exists()
    assert sibling.read_text() == "keep"


def test_existing_output_and_unlisted_files(tmp_path: Path) -> None:
    item = view()
    output = tmp_path / "bundle"
    item.export(output)
    alias = tmp_path / "alias"
    alias.symlink_to(output, target_is_directory=True)
    with pytest.raises(ContractError, match="symlink"):
        item.export(alias)
    (output / "extra.txt").write_text("unlisted")
    with pytest.raises(ContractError, match="unlisted"):
        rendering.verify_bundle(output)


def test_svg_and_png_repeatable() -> None:
    item = view()
    for fmt in ("svg", "png"):
        assert rendering.figure_bytes(item.figure(), fmt) == rendering.figure_bytes(
            item.figure(), fmt
        )


@pytest.mark.parametrize(
    "name",
    ["signal-report.ipynb", "composition-cookbook.ipynb", "quantile-diagnostics.ipynb"],
)
def test_tracked_notebook_has_no_saved_outputs(name: str) -> None:
    notebook = json_object((ROOT / "notebooks" / name).read_bytes())
    for item in sequence(notebook["cells"]):
        cell = mapping(item)
        if cell["cell_type"] == "code":
            assert cell["execution_count"] is None
            assert cell["outputs"] == []
