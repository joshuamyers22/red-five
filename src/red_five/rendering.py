"""Headless figures, offline HTML and completion-marked local report bundles."""

# Matplotlib's public artist methods have untyped **kwargs. Keep this exception
# within the plotting adapter; project inputs/outputs and domain code remain strict.
# pyright: reportUnknownMemberType=false

from __future__ import annotations

import io
import math
import re
import shutil
from collections.abc import Callable
from html import escape
from importlib.metadata import version
from pathlib import Path
from textwrap import fill
from time import monotonic
from weakref import WeakKeyDictionary

import matplotlib as mpl
from matplotlib.axes import Axes
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
from matplotlib.typing import RcKeyType

from .composition import DEFAULT_PLOT, PlotOptions, PlotSource
from .contracts import ContractError
from .reporting import canonical, source_identity
from .signal_io import digest, json_object, read_bytes
from .visualization import PAGE_SIZE, ReportView, mapping, text_cell

SCHEMA = "red-five-render/v1"
MAX_BUNDLE_BYTES = 32 * 1024 * 1024
MAX_SECONDS = 60
KINDS = ("correlations", "coverage", "returns", "costs")
STYLE: dict[RcKeyType, object] = {
    "font.family": "DejaVu Sans",
    "font.size": 9,
    "svg.hashsalt": "red-five-render-v1",
    "svg.fonttype": "none",
    "text.usetex": False,
    "text.parse_math": False,
    "axes.facecolor": "#f4f4f4",
    "axes.grid": True,
    "grid.color": "white",
    "axes.axisbelow": True,
}
AXIS_CONTEXT: WeakKeyDictionary[Axes, tuple[object, ...]] = WeakKeyDictionary()


def table_for(kind: str) -> str:
    if kind not in KINDS:
        raise ContractError(
            "unknown figure; use correlations, coverage, returns or costs"
        )
    return "signals" if kind in KINDS[:2] else "economics"


def make_figure(
    view: PlotSource,
    kind: str,
    page: int = 0,
    *,
    ax: Axes | None = None,
    options: PlotOptions = DEFAULT_PLOT,
) -> Figure:
    table_name = table_for(kind)
    if table_name not in view.tables:
        raise ContractError("plot evidence not requested")
    table = view.tables[table_name]
    pages = max(1, math.ceil(len(table.rows) / PAGE_SIZE))
    if type(page) is not int or not 0 <= page < pages:
        raise ContractError("figure page outside available range")
    rows = table.rows[page * PAGE_SIZE : (page + 1) * PAGE_SIZE]
    allowed = {
        "correlations": ("pearson_ic", "rank_ic"),
        "coverage": (
            "eligible_observations",
            "immature_labels",
            "missing_mature_labels",
        ),
        "returns": ("gross_return", "net_return"),
        "costs": ("trading_cost_return", "holding_cost_return"),
    }[kind]
    fields = options.metrics or allowed
    if any(field not in allowed or field not in table.columns for field in fields):
        raise ContractError("metric not available for this plot")
    identity_count = (
        2 if table_name == "economics" or view.config.mode == "cross_sectional" else 3
    )
    context = (
        kind,
        view.config.mode,
        view.config.return_kind,
        view.config.horizon,
        view.config.calendar,
        tuple(row[:identity_count] for row in rows),
        options.yscale,
        options.ylim,
    )
    if (
        ax is not None
        and ax.has_data()
        and (not options.overlay or AXIS_CONTEXT.get(ax) != context)
    ):
        raise ContractError("occupied axes require an explicitly compatible overlay")
    with mpl.rc_context({**STYLE, "font.size": options.font_size}):
        if ax is None:
            fig = Figure(figsize=options.figsize, dpi=options.dpi, layout="constrained")
            fig.set_label(f"{view.run_id}-{kind}-{page}")
            fig.suptitle(fill(view.caption, width=115), fontsize=8)
            FigureCanvasAgg(fig)
            ax = fig.subplots()
        else:
            owner = ax.get_figure()
            if not isinstance(owner, Figure):
                raise ContractError("axes must belong to a Figure")
            fig = owner
            ax.text(
                0, -0.55, fill(view.caption, 100), transform=ax.transAxes, fontsize=6
            )
        AXIS_CONTEXT[ax] = context
        ax.set_title(options.title or f"{kind.title()} — page {page + 1}/{pages}")
        ax.set_xlabel(
            options.xlabel
            or "Evaluation group (full identity and exact values in table)"
        )
        if not rows:
            ax.text(
                0.5,
                0.5,
                "Unavailable: no supplied intervals/groups",
                transform=ax.transAxes,
                ha="center",
            )
            return fig
        colors = options.colors
        width = 0.8 / len(fields)
        for j, field in enumerate(fields):
            index = table.columns.index(field)
            positions: list[float] = []
            values: list[float] = []
            for i, row in enumerate(rows):
                value = row[index]
                if value is not None:
                    positions.append(i + (j - (len(fields) - 1) / 2) * width)
                    values.append(float(value))
            if kind == "correlations":
                ax.scatter(
                    positions,
                    values,
                    label=options.label_prefix + field,
                    color=colors[j % len(colors)],
                    marker=options.markers[j % len(options.markers)],
                )
            else:
                ax.bar(
                    positions,
                    values,
                    width=width,
                    label=options.label_prefix + field,
                    color=colors[j % len(colors)],
                    hatch=("", "//", "..")[j],
                )
        labels = [" / ".join(str(v) for v in row[:identity_count]) for row in rows]
        ax.set_xticks(
            list(range(len(rows))),
            [label if len(label) <= 45 else label[:42] + "…" for label in labels],
            rotation=35,
            ha="right",
        )
        ax.axhline(0, color="#333333", linewidth=0.7)
        if kind == "correlations":
            ax.set_ylim(-1.05, 1.05)
            ax.set_ylabel("Descriptive correlation (no significance claim)")
            for i, row in enumerate(rows):
                if row[table.columns.index("status")] == "unavailable":
                    ax.text(i, -0.95, "unavailable", rotation=90, fontsize=7)
        else:
            ax.set_ylabel(
                "Observations"
                if kind == "coverage"
                else "Fraction of pre-trade NAV; supplied total-return intervals"
            )
        ax.set_yscale(options.yscale)
        if options.ylim is not None:
            ax.set_ylim(options.ylim)
        if options.ylim is not None or options.yscale != "linear":
            ax.text(
                0.01,
                0.01,
                "Custom axis range/scale; values may be clipped. See exact table.",
                transform=ax.transAxes,
                fontsize=7,
            )
        if options.legend:
            ax.legend(loc="best")
        return fig


def figure_bytes(figure: Figure, fmt: str, *, dpi: int = 120) -> bytes:
    buffer = io.BytesIO()
    with mpl.rc_context({**STYLE, "svg.hashsalt": figure.get_label()}):
        figure.savefig(
            buffer,
            format=fmt,
            dpi=dpi,
            metadata={"Date": None} if fmt == "svg" else {"Software": "Red Five"},
        )
    return buffer.getvalue()


def figure_ids(view: ReportView) -> list[tuple[str, str, int]]:
    return [
        (f"{kind}-{page + 1:02d}", kind, page)
        for kind in KINDS
        for page in range(
            max(1, math.ceil(len(view.tables[table_for(kind)].rows) / PAGE_SIZE))
        )
    ]


def html_report(view: ReportView, svgs: dict[str, bytes] | None = None) -> str:
    start = monotonic()
    parts = [
        '<section class="red-five"><style>'
        ".red-five{font:14px system-ui;color:#17212b;background:white;padding:1em}"
        ".red-five table{border-collapse:collapse;font-size:12px}"
        ".red-five th,.red-five td{padding:6px;border:1px solid #bbb;text-align:left}"
        ".red-five .rf-scroll{overflow:auto}.red-five svg{width:100%;height:auto}"
        ".red-five caption{text-align:left;font-weight:bold;padding:8px}"
        "@media print{.red-five .rf-scroll{overflow:visible}"
        ".red-five figure{break-inside:avoid}}"
        "</style><h1>Red Five — descriptive signal report</h1>",
        f"<p>{escape(view.caption)}</p>",
        "<p>No acceptance verdict. Quantiles, breadth, uncertainty, marginal value, "
        "NAV and drawdown are unavailable in this slice. Tables preserve full values; "
        "plots convert accounting decimals to floating point for display only.</p>",
    ]
    for name, table in view.tables.items():
        parts.append(f'<h2 id="{name}">{name.title()}</h2>')
        parts.append(table.html(f"{name.title()} — {view.caption}"))
    for figure_id, kind, page in figure_ids(view):
        if monotonic() - start > MAX_SECONDS:
            raise ContractError("render time budget exceeded")
        svg = (
            svgs[figure_id]
            if svgs is not None
            else figure_bytes(make_figure(view, kind, page), "svg")
        )
        # Strip the XML declaration/DTD from locally generated SVG.
        markup = svg.decode("utf-8")
        markup = markup[markup.index("<svg") :]
        parts.append(
            f'<figure id="{figure_id}">{markup}<figcaption>'
            f"{escape(figure_id + ' — ' + view.caption)}. "
            f'<a href="#{table_for(kind)}">Exact values and reasons</a>'
            "</figcaption></figure>"
        )
    parts.append("</section>")
    result = "".join(parts)
    if len(result.encode()) > MAX_BUNDLE_BYTES:
        raise ContractError("HTML exceeds render byte budget")
    return result


def export_bundle(view: ReportView, output: Path) -> Path:
    start = monotonic()
    files = {"report.json": view.content}
    files.update({f"{name}.csv": table.csv() for name, table in view.tables.items()})
    svgs: dict[str, bytes] = {}
    for figure_id, kind, page in figure_ids(view):
        if monotonic() - start > MAX_SECONDS:
            raise ContractError("render time budget exceeded")
        figure = make_figure(view, kind, page)
        for fmt in ("svg", "png"):
            files[f"{figure_id}.{fmt}"] = figure_bytes(figure, fmt)
        svgs[figure_id] = files[f"{figure_id}.svg"]
        if sum(map(len, files.values())) > MAX_BUNDLE_BYTES:
            raise ContractError("bundle exceeds render byte budget")
    files["index.html"] = (
        "<!doctype html><html lang='en'><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width'>"
        "<title>Red Five</title><body>" + html_report(view, svgs) + "</body></html>"
    ).encode()
    manifest = {
        "schema_version": SCHEMA,
        "source_sha256": digest(view.content),
        "run_id": view.run_id,
        "renderer": "red-five-v1",
        "code": source_identity(),
        "matplotlib": version("matplotlib"),
        "page_size": PAGE_SIZE,
        "csv": {
            "null": "\\N",
            "text_escape": "leading apostrophe; strip one to decode",
            "decimal_amounts": "text; exact",
            "numeric_format": "unrounded",
        },
        "files": {name: digest(content) for name, content in sorted(files.items())},
    }
    files["manifest.json"] = canonical(manifest)
    return publish_bundle(files, output, verify_bundle)


def publish_bundle(
    files: dict[str, bytes], output: Path, verifier: Callable[[Path], dict[str, object]]
) -> Path:
    if sum(map(len, files.values())) > MAX_BUNDLE_BYTES:
        raise ContractError("bundle exceeds render byte budget")
    if output.is_symlink():
        raise ContractError("bundle output may not be a symlink")
    if output.exists():
        verifier(output)
        if all(
            (output / name).read_bytes() == content for name, content in files.items()
        ):
            return output / "index.html"
        raise ContractError("output already contains different render evidence")
    output.parent.mkdir(parents=True, exist_ok=True)
    # Reserve exclusively. Consumers require the manifest, written last, before reading.
    output.mkdir()
    try:
        for name, content in files.items():
            with (output / name).open("xb") as stream:
                stream.write(content)
        verifier(output)
    except BaseException:
        shutil.rmtree(output)
        raise
    return output / "index.html"


def verify_bundle(output: Path) -> dict[str, object]:
    if output.is_symlink() or (output / "manifest.json").is_symlink():
        raise ContractError("bundle symlinks are forbidden")
    manifest = json_object(read_bytes(output / "manifest.json"))
    if manifest.get("schema_version") == "red-five-components/v1":
        from .component_export import verify_components

        return verify_components(output)
    if manifest.get("schema_version") != SCHEMA:
        raise ContractError("unsupported render manifest")
    files = mapping(manifest.get("files"))
    if (
        not 5 <= len(files) <= 90
        or "report.json" not in files
        or "index.html" not in files
    ):
        raise ContractError("invalid bundle file inventory")
    total = 0
    for name, expected in files.items():
        if not re.fullmatch(r"[a-z][a-z0-9-]*\.(json|html|csv|svg|png)", name):
            raise ContractError("unsafe bundle filename")
        path = output / name
        if path.is_symlink():
            raise ContractError("bundle symlinks are forbidden")
        content = read_bytes(path)
        total += len(content)
        if total > MAX_BUNDLE_BYTES or digest(content) != text_cell(expected):
            raise ContractError("bundle size or content digest mismatch")
    if {p.name for p in output.iterdir()} != {*files, "manifest.json"}:
        raise ContractError("bundle contains unlisted files")
    view = ReportView(read_bytes(output / "report.json"))
    if digest(view.content) != manifest.get(
        "source_sha256"
    ) or view.run_id != manifest.get("run_id"):
        raise ContractError("bundle source identity mismatch")
    return manifest
