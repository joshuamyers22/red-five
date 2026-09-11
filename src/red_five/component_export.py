"""Partial component bundles with exact source sections and display specifications."""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from html import escape
from importlib.metadata import version
from pathlib import Path
from time import monotonic

from .composition import Panel, PlotOptions, Selection
from .contracts import ContractError
from .rendering import (
    MAX_BUNDLE_BYTES,
    MAX_SECONDS,
    PLOT_FIELDS,
    figure_bytes,
    publish_bundle,
)
from .reporting import canonical, source_identity
from .sections import SectionResult
from .signal_io import MAX_BYTES, digest, json_object, read_bytes
from .visualization import mapping, sequence, text_cell

SCHEMA = "red-five-components/v1"


@dataclass(frozen=True)
class Component:
    """A table-only component, or one configured chart page plus its exact table."""

    panel: Panel
    kind: str | None = None
    options: PlotOptions = PlotOptions()
    page: int = 0


def export_components(components: Sequence[Component], output_dir: str | Path) -> Path:
    if not 1 <= len(components) <= 20:
        raise ContractError("a partial bundle requires 1–20 components")
    start = monotonic()
    files: dict[str, bytes] = {}
    records: list[dict[str, object]] = []
    html = [
        "<!doctype html><html lang='en'><meta charset='utf-8'>",
        "<meta name='viewport' content='width=device-width'>"
        "<title>Red Five partial report</title>",
        "<body><h1>Red Five — partial report</h1>"
        "<p>No full-report verdict. Only listed components were requested.</p>",
    ]
    for i, component in enumerate(components):
        if monotonic() - start > MAX_SECONDS:
            raise ContractError("component render time budget exceeded")
        prefix = f"component-{i + 1:02d}"
        panel = component.panel
        source_name = prefix + ".json"
        files[source_name] = panel.section.content
        files[prefix + ".csv"] = panel.table_data().csv()
        html.append(panel.html())
        if component.kind is not None:
            plotted = component.options.metrics or PLOT_FIELDS.get(component.kind, ())
            if any(metric not in panel.table_data().columns for metric in plotted):
                raise ContractError(
                    "chart export table must include its plotted metrics"
                )
            figure = panel.figure(
                component.kind, options=component.options, page=component.page
            )
            for fmt in ("svg", "png"):
                files[f"{prefix}.{fmt}"] = figure_bytes(
                    figure, fmt, dpi=component.options.dpi
                )
            html.append(
                f"<figure><img style='max-width:100%' src='{prefix}.svg' "
                f"alt='{escape(component.kind)}'><figcaption>{escape(panel.caption)}</figcaption></figure>"
            )
        records.append(
            {
                "source": source_name,
                **panel.specification(),
                "kind": component.kind,
                "page": component.page,
                "options": asdict(component.options),
            }
        )
        if sum(map(len, files.values())) > MAX_BUNDLE_BYTES:
            raise ContractError("partial bundle byte budget exceeded")
    html.append("</body></html>")
    files["index.html"] = "".join(html).encode()
    manifest = {
        "schema_version": SCHEMA,
        "scope": "partial",
        "verdict": None,
        "code": source_identity(),
        "matplotlib": version("matplotlib"),
        "components": records,
        "csv": {
            "null": "\\N",
            "text_escape": "leading apostrophe",
            "values": "exact, unrounded",
        },
        "files": {name: digest(content) for name, content in sorted(files.items())},
    }
    files["manifest.json"] = canonical(manifest)
    if any(len(content) > MAX_BYTES for content in files.values()):
        raise ContractError("partial bundle file exceeds 16 MiB")
    return publish_bundle(files, Path(output_dir), verify_components)


def verify_components(output: Path) -> dict[str, object]:
    if output.is_symlink() or (output / "manifest.json").is_symlink():
        raise ContractError("partial bundle symlinks are forbidden")
    manifest = json_object(read_bytes(output / "manifest.json"))
    if (
        manifest.get("schema_version") != SCHEMA
        or manifest.get("scope") != "partial"
        or manifest.get("verdict") is not None
    ):
        raise ContractError("invalid partial manifest")
    records = sequence(manifest.get("components"))
    if not 1 <= len(records) <= 20:
        raise ContractError("invalid partial component count")
    files = mapping(manifest.get("files"))
    if not 3 <= len(files) <= 101:
        raise ContractError("invalid partial file count")
    required = {"index.html"}
    for i, value in enumerate(records):
        record = mapping(value)
        prefix = f"component-{i + 1:02d}"
        source = prefix + ".json"
        if record.get("source") != source:
            raise ContractError("invalid component source filename")
        required.update((source, prefix + ".csv"))
        if record.get("kind") is not None:
            if text_cell(record["kind"]) not in PLOT_FIELDS:
                raise ContractError("invalid component kind")
            required.update((prefix + ".svg", prefix + ".png"))
    if set(files) != required or {p.name for p in output.iterdir()} != {
        *required,
        "manifest.json",
    }:
        raise ContractError("partial bundle inventory mismatch")
    total = 0
    for name, expected in files.items():
        if (
            not re.fullmatch(
                r"(?:index|component-\d{2})\.(html|json|csv|svg|png)", name
            )
            or (output / name).is_symlink()
        ):
            raise ContractError("unsafe partial artifact")
        content = read_bytes(output / name)
        total += len(content)
        if total > MAX_BUNDLE_BYTES or digest(content) != expected:
            raise ContractError("partial bundle digest or size mismatch")
    for value in records:
        record = mapping(value)
        section = SectionResult(read_bytes(output / text_cell(record["source"])))
        if section.section_id != record.get("section_id"):
            raise ContractError("partial section identity mismatch")
        # Verify table data against the exact source and serialized display selection.
        selection = selection_from_dict(mapping(record.get("selection")))
        panel = section.select(selection)
        if panel.table_data().csv() != read_bytes(
            output / text_cell(record["source"]).replace(".json", ".csv")
        ):
            raise ContractError("partial table does not match section selection")
        options = options_from_dict(mapping(record.get("options")))
        if record.get("kind") is not None:
            # Validate configuration, not financial calculations or publisher identity.
            kind = text_cell(record["kind"])
            allowed = {
                "standalone": ("correlations", "coverage"),
                "coverage": ("coverage",),
                "economics": ("returns", "costs"),
                "quantiles": ("quantiles", "quantile_counts"),
            }[section.name]
            if kind not in allowed or any(
                metric not in PLOT_FIELDS[kind] for metric in options.metrics
            ):
                raise ContractError("partial plot incompatible with section")
            if any(
                metric not in panel.table_data().columns
                for metric in (options.metrics or PLOT_FIELDS[kind])
            ):
                raise ContractError("partial plot metrics missing from companion table")
        page = record.get("page")
        if (
            type(page) is not int
            or page < 0
            or page >= max(1, (len(panel.selected_data().rows) + 19) // 20)
        ):
            raise ContractError("invalid partial figure page")
    return manifest


def _strings(value: object) -> tuple[str, ...]:
    return tuple(text_cell(item) for item in sequence(value))


def selection_from_dict(value: dict[str, object]) -> Selection:
    if set(value) != set(asdict(Selection())):
        raise ContractError("invalid selection specification")
    if type(value["descending"]) is not bool or (
        value["precision"] is not None and type(value["precision"]) is not int
    ):
        raise ContractError("invalid selection types")

    return Selection(
        model_ids=_strings(value["model_ids"]),
        instrument_ids=_strings(value["instrument_ids"]),
        contract_ids=_strings(value["contract_ids"]),
        portfolio_ids=_strings(value["portfolio_ids"]),
        decision_times=_strings(value["decision_times"]),
        columns=_strings(value["columns"]),
        sort_by=None if value["sort_by"] is None else text_cell(value["sort_by"]),
        descending=value["descending"],
        precision=value["precision"],
    )


def options_from_dict(value: dict[str, object]) -> PlotOptions:
    from typing import cast

    from .visualization import number

    if (
        set(value) != set(asdict(PlotOptions()))
        or any(type(value[key]) is not bool for key in ("legend", "overlay"))
        or type(value["dpi"]) is not int
    ):
        raise ContractError("invalid plot specification")

    def pair(item: object) -> tuple[float, float]:
        items = sequence(item)
        if len(items) != 2:
            raise ContractError("expected two plot dimensions")
        return float(number(items[0])), float(number(items[1]))

    return PlotOptions(
        figsize=pair(value["figsize"]),
        dpi=value["dpi"],
        colors=_strings(value["colors"]),
        markers=_strings(value["markers"]),
        font_size=float(number(value["font_size"])),
        title=None if value["title"] is None else text_cell(value["title"]),
        xlabel=None if value["xlabel"] is None else text_cell(value["xlabel"]),
        legend=cast(bool, value["legend"]),
        metrics=_strings(value["metrics"]),
        ylim=None if value["ylim"] is None else pair(value["ylim"]),
        yscale=text_cell(value["yscale"]),
        label_prefix=text_cell(value["label_prefix"]),
        overlay=cast(bool, value["overlay"]),
    )
