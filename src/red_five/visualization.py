"""Verified report views for notebooks and offline exports; no model fitting."""

from __future__ import annotations

import csv
import io
import math
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from html import escape
from pathlib import Path
from types import MappingProxyType
from typing import TYPE_CHECKING, cast

import polars as pl

if TYPE_CHECKING:
    from matplotlib.figure import Figure

from .contracts import ContractError, EvaluationConfig
from .reporting import verify_report
from .signal_io import MAX_BYTES, read_bytes

MAX_ROWS = 200
PAGE_SIZE = 20
Cell = str | int | float | None


def mapping(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ContractError("render evidence requires an object")
    return cast(dict[str, object], value)


def sequence(value: object) -> list[object]:
    if not isinstance(value, list):
        raise ContractError("render evidence requires a list")
    result = cast(list[object], value)
    if len(result) > MAX_ROWS:
        raise ContractError("render list missing or exceeds 200-row limit")
    return result


def text_cell(value: object) -> str:
    if not isinstance(value, str) or len(value) > 1024:
        raise ContractError("render text missing or exceeds 1024 characters")
    return value


def number(value: object, *, count: bool = False) -> int | float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ContractError("invalid render number")
    try:
        finite = math.isfinite(value)
    except OverflowError:
        finite = False
    if not finite:
        raise ContractError("nonfinite render number")
    if count and (not isinstance(value, int) or not 0 <= value <= 100000):
        raise ContractError("invalid observation count")
    return value


@dataclass(frozen=True)
class Table:
    columns: tuple[str, ...]
    rows: tuple[tuple[Cell, ...], ...]

    def dataframe(self) -> pl.DataFrame:
        """Return a new frame; Decimal accounting remains exact text."""
        return pl.DataFrame(
            {name: [row[i] for row in self.rows] for i, name in enumerate(self.columns)}
        )

    def csv(self) -> bytes:
        def safe(cell: Cell) -> Cell:
            if isinstance(cell, str):
                # Escape the escape marker too, making this transformation reversible.
                if cell.lstrip().startswith(("=", "+", "-", "@", "'", "\\")):
                    return "'" + cell
                if any(char in cell for char in "\t\r\n"):
                    return "'" + cell
            return "\\N" if cell is None else cell

        output = io.StringIO(newline="")
        writer = csv.writer(output, lineterminator="\n")
        writer.writerow(self.columns)
        writer.writerows([safe(cell) for cell in row] for row in self.rows)
        return output.getvalue().encode("utf-8")

    def html(self, caption: str) -> str:
        header = "".join(f'<th scope="col">{escape(c)}</th>' for c in self.columns)
        rows = "".join(
            "<tr>"
            + "".join(
                f"<td>{escape('unavailable' if c is None else str(c))}</td>"
                for c in row
            )
            + "</tr>"
            for row in self.rows
        )
        return (
            f'<div class="rf-scroll"><table><caption>{escape(caption)}</caption>'
            f"<thead><tr>{header}</tr></thead><tbody>{rows}</tbody></table></div>"
        )


@dataclass(frozen=True, init=False)
class ReportView:
    """Load once, verify once; display(view) works in Jupyter without a server."""

    content: bytes
    run_id: str
    status: str
    config: EvaluationConfig
    tables: Mapping[str, Table]

    def __init__(self, content: bytes) -> None:
        if len(content) > MAX_BYTES:
            raise ContractError("report exceeds 16 MiB input limit")
        report = verify_report(content)
        object.__setattr__(self, "content", content)
        object.__setattr__(self, "run_id", text_cell(report.get("run_id")))
        object.__setattr__(self, "status", text_cell(report.get("status")))
        if self.status != "insufficient-evidence" or report.get("verdict") is not None:
            raise ContractError("renderer v1 supports descriptive reports only")
        object.__setattr__(
            self,
            "config",
            EvaluationConfig.parse(mapping(mapping(report["identity"])["config"])),
        )
        if report.get("mode") != self.config.mode:
            raise ContractError("report mode disagrees with configuration")
        group_fields = (
            ("model_id", "instrument_id", "contract_id")
            if self.config.mode == "time_series"
            else ("model_id", "decision_time")
        )
        if report.get("group_fields") != list(group_fields):
            raise ContractError("unsupported report grouping")
        metric_fields = (
            "observations",
            "eligible_observations",
            "immature_labels",
            "missing_mature_labels",
            "pearson_ic",
            "rank_ic",
            "status",
            "reason",
        )
        signal_rows: list[tuple[Cell, ...]] = []
        for item in sequence(report.get("standalone")):
            row = mapping(item)
            group = tuple(text_cell(v) for v in sequence(row.get("group")))
            if len(group) != len(group_fields):
                raise ContractError("invalid group identity")
            counts = tuple(
                number(row.get(key), count=True) for key in metric_fields[:4]
            )
            metrics: list[Cell] = []
            for key in ("pearson_ic", "rank_ic"):
                value = row.get(key)
                if value is not None and abs(number(value)) > 1:
                    raise ContractError("correlation outside [-1, 1]")
                metrics.append(None if value is None else number(value))
            state = text_cell(row.get("status"))
            reason = row.get("reason")
            if state not in ("available", "unavailable"):
                raise ContractError("unknown metric status")
            if state == "unavailable" and not isinstance(reason, str):
                raise ContractError("unavailable metrics require a reason")
            signal_rows.append(
                (
                    *group,
                    *counts,
                    *metrics,
                    state,
                    None if reason is None else text_cell(reason),
                )
            )
        econ = mapping(report.get("economics"))
        money_fields = (
            "gross_return",
            "trading_cost_return",
            "holding_cost_return",
            "net_return",
            "turnover_absolute",
        )
        economic_rows: list[tuple[Cell, ...]] = []
        for item in sequence(econ.get("periods")):
            row = mapping(item)
            labels = tuple(
                text_cell(row.get(k))
                for k in ("portfolio_id", "decision_time", "label_start", "label_end")
            )
            amounts = tuple(text_cell(row.get(k)) for k in money_fields)
            for amount in amounts:
                try:
                    value = Decimal(amount)
                    valid = value.is_finite() and abs(value) <= Decimal("1e30")
                except InvalidOperation:
                    valid = False
                if not valid:
                    raise ContractError("invalid or unplottable accounting amount")
            economic_rows.append(
                (*labels, number(row.get("constituents"), count=True), *amounts)
            )
        tables = {
            "signals": Table((*group_fields, *metric_fields), tuple(signal_rows)),
            "economics": Table(
                (
                    "portfolio_id",
                    "decision_time",
                    "label_start",
                    "label_end",
                    "constituents",
                    *money_fields,
                ),
                tuple(economic_rows),
            ),
            "summary": Table(
                ("field", "value"),
                tuple(
                    (key, str(value))
                    for key, value in {
                        "run_id": self.run_id,
                        "status": self.status,
                        "mode": self.config.mode,
                        "as_of": self.config.as_of.isoformat(),
                        "target": self.config.return_kind,
                        "horizon": self.config.horizon,
                        "calendar": self.config.calendar,
                        "reason_codes": "; ".join(
                            text_cell(v) for v in sequence(report.get("reason_codes"))
                        ),
                        "economics_status": text_cell(econ.get("status")),
                        "economics_reason": econ.get("reason") or "not applicable",
                        "limitations": "; ".join(
                            text_cell(v) for v in sequence(report.get("limitations"))
                        ),
                    }.items()
                ),
            ),
        }
        object.__setattr__(self, "tables", MappingProxyType(tables))

    def table(self, name: str = "signals") -> pl.DataFrame:
        if name not in self.tables:
            raise ContractError("unknown table; use summary, signals or economics")
        return self.tables[name].dataframe()

    @property
    def caption(self) -> str:
        return (
            f"{self.config.mode}; {self.config.return_kind} signal target; "
            f"horizon {self.config.horizon}; as-of {self.config.as_of.isoformat()}; "
            f"{self.status}; run {self.run_id}"
        )

    def figure(self, kind: str = "correlations", page: int = 0) -> Figure:
        """Return an independent Matplotlib Figure; no pyplot/global backend changes."""
        from .rendering import make_figure

        return make_figure(self, kind, page)

    def _repr_html_(self) -> str:
        return self.html()

    def html(self) -> str:
        """Return the offline fragment used by Jupyter's rich display protocol."""
        from .rendering import html_report

        return html_report(self)

    def export(self, output_dir: str | Path) -> Path:
        from .rendering import export_bundle

        return export_bundle(self, Path(output_dir))


def load_report(path: str | Path) -> ReportView:
    """Load a verified report for display, tables, figures or export."""
    try:
        return ReportView(read_bytes(Path(path)))
    except (KeyError, TypeError, ValueError) as error:
        raise ContractError("unsupported or malformed rendering evidence") from error
