"""Immutable presentation selections; all computations stay in section evaluation."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from decimal import Decimal
from html import escape
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

import polars as pl

from .contracts import ContractError, EvaluationConfig
from .sections import SectionResult
from .visualization import Cell, Table

if TYPE_CHECKING:
    from matplotlib.axes import Axes
    from matplotlib.figure import Figure


class PlotSource(Protocol):
    @property
    def tables(self) -> Mapping[str, Table]: ...
    @property
    def config(self) -> EvaluationConfig: ...
    @property
    def run_id(self) -> str: ...
    @property
    def caption(self) -> str: ...


@dataclass(frozen=True)
class PlotOptions:
    figsize: tuple[float, float] = (11, 5)
    dpi: int = 120
    colors: tuple[str, ...] = ("#0072B2", "#D55E00", "#009E73")
    markers: tuple[str, ...] = ("o", "x", "s")
    font_size: float = 9
    title: str | None = None
    xlabel: str | None = None
    legend: bool = True
    metrics: tuple[str, ...] = ()
    ylim: tuple[float, float] | None = None
    yscale: str = "linear"
    label_prefix: str = ""
    overlay: bool = False

    def __post_init__(self) -> None:
        if any(
            type(v) is not tuple
            for v in (self.figsize, self.colors, self.markers, self.metrics)
        ):
            raise ContractError("display sequences must be immutable tuples")
        if len(self.figsize) != 2 or not all(
            math.isfinite(v) and 2 <= v <= 24 for v in self.figsize
        ):
            raise ContractError("figure dimensions must be in [2, 24] inches")
        if (
            type(self.dpi) is not int
            or not 40 <= self.dpi <= 300
            or not 6 <= self.font_size <= 24
        ):
            raise ContractError("invalid display DPI or font size")
        if (
            not self.colors
            or len(self.colors) > 8
            or not self.markers
            or any(m not in ("o", "x", "s", "+", "D", "^", "v") for m in self.markers)
        ):
            raise ContractError("invalid palette or marker selection")
        if any(
            len(c) != 7
            or c[0] != "#"
            or any(x not in "0123456789abcdefABCDEF" for x in c[1:])
            for c in self.colors
        ):
            raise ContractError("colors must be #RRGGBB hex strings")
        if self.yscale not in ("linear", "symlog"):
            raise ContractError("supported scales are linear and symlog")
        if self.ylim is not None and (
            len(self.ylim) != 2
            or not all(math.isfinite(v) for v in self.ylim)
            or self.ylim[0] >= self.ylim[1]
        ):
            raise ContractError("invalid y-axis limits")
        if any(
            len(v) > 256
            for v in (self.title or "", self.xlabel or "", self.label_prefix)
        ):
            raise ContractError("display labels exceed 256 characters")
        if len(set(self.metrics)) != len(self.metrics):
            raise ContractError("duplicate display metrics")


DEFAULT_PLOT = PlotOptions()


@dataclass(frozen=True)
class Selection:
    """Select existing rows for display, never change a numerical sample."""

    model_ids: tuple[str, ...] = ()
    instrument_ids: tuple[str, ...] = ()
    contract_ids: tuple[str, ...] = ()
    portfolio_ids: tuple[str, ...] = ()
    decision_times: tuple[str, ...] = ()
    sort_by: str | None = None
    descending: bool = False
    columns: tuple[str, ...] = ()
    precision: int | None = None

    def __post_init__(self) -> None:
        for values in (
            self.model_ids,
            self.instrument_ids,
            self.contract_ids,
            self.portfolio_ids,
            self.decision_times,
            self.columns,
        ):
            if (
                type(values) is not tuple
                or len(values) > 200
                or any(len(v) > 256 for v in values)
            ):
                raise ContractError(
                    "selections require bounded immutable identifier tuples"
                )
        if self.precision is not None and (
            type(self.precision) is not int or not 0 <= self.precision <= 12
        ):
            raise ContractError("display precision must be an integer in [0, 12]")
        if len(set(self.columns)) != len(self.columns):
            raise ContractError("duplicate table columns")


@dataclass(frozen=True)
class Panel:
    section: SectionResult
    selection: Selection = Selection()

    def __post_init__(self) -> None:
        # Validate immediately, before any caller-owned figure is touched.
        self.selected_data()

    def selected_data(self) -> Table:
        source = self.section.data
        rows = list(source.rows)
        for field, values in (
            ("model_id", self.selection.model_ids),
            ("instrument_id", self.selection.instrument_ids),
            ("contract_id", self.selection.contract_ids),
            ("portfolio_id", self.selection.portfolio_ids),
            ("decision_time", self.selection.decision_times),
        ):
            if not values:
                continue
            if field not in source.columns:
                raise ContractError(f"{field} is not a display axis of this section")
            index = source.columns.index(field)
            rows = [row for row in rows if row[index] in values]
        if self.selection.sort_by is not None:
            if self.selection.sort_by not in source.columns:
                raise ContractError("unknown sort column")
            index = source.columns.index(self.selection.sort_by)
            present = [row for row in rows if row[index] is not None]
            missing = [row for row in rows if row[index] is None]
            numeric = self.selection.sort_by in (
                "gross_return",
                "net_return",
                "trading_cost_return",
                "holding_cost_return",
                "turnover_absolute",
            )

            def key(row: tuple[Cell, ...]) -> str | int | float | Decimal:
                value = row[index]
                assert value is not None
                return Decimal(str(value)) if numeric else value

            rows = sorted(present, key=key, reverse=self.selection.descending) + missing
        if any(c not in source.columns for c in self.selection.columns):
            raise ContractError("unknown selected table column")
        return Table(source.columns, tuple(rows))

    @property
    def tables(self) -> Mapping[str, Table]:
        return {
            "economics"
            if self.section.name == "economics"
            else "quantiles"
            if self.section.name == "quantiles"
            else "signals": self.selected_data()
        }

    @property
    def config(self) -> EvaluationConfig:
        return self.section.config

    @property
    def run_id(self) -> str:
        return self.section.section_id

    @property
    def caption(self) -> str:
        selected = self.selected_data()
        return (
            f"Partial {self.section.name}; {self.section.status}; no verdict; "
            f"displaying {len(selected.rows)}/{len(self.section.data.rows)} rows "
            f"({len(self.section.data.rows) - len(selected.rows)} omitted); "
            f"{self.config.mode}; {self.config.return_kind} signal target; "
            f"{self.config.horizon}; as-of {self.config.as_of.isoformat()}; "
            f"section {self.run_id}"
        )

    def table_data(self) -> Table:
        selected = self.selected_data()
        columns = self.selection.columns or selected.columns
        indices = [selected.columns.index(c) for c in columns]
        return Table(
            columns, tuple(tuple(row[i] for i in indices) for row in selected.rows)
        )

    def table(self) -> pl.DataFrame:
        """Exact, unrounded values for further notebook exploration."""
        return self.table_data().dataframe()

    def html(self) -> str:
        data = self.table_data()
        precision = self.selection.precision
        if precision is not None:
            numeric_text = {
                "gross_return",
                "net_return",
                "trading_cost_return",
                "holding_cost_return",
                "turnover_absolute",
            }
            data = Table(
                data.columns,
                tuple(
                    tuple(
                        f"{Decimal(str(value)):.{precision}f}"
                        if value is not None
                        and (
                            isinstance(value, float) or data.columns[i] in numeric_text
                        )
                        else value
                        for i, value in enumerate(row)
                    )
                    for row in data.rows
                ),
            )
        return (
            f"<section><p>{escape(self.caption)}</p>"
            + data.html("Selected values (display-only formatting)")
            + "</section>"
        )

    def _repr_html_(self) -> str:
        return self.html()

    def figure(
        self,
        kind: str | None = None,
        *,
        options: PlotOptions = DEFAULT_PLOT,
        page: int = 0,
    ) -> Figure:
        from .rendering import make_figure

        return make_figure(self, self._kind(kind), page, options=options)

    def plot(
        self,
        kind: str | None = None,
        *,
        ax: Axes,
        options: PlotOptions = DEFAULT_PLOT,
        page: int = 0,
    ) -> Axes:
        from .rendering import make_figure

        make_figure(self, self._kind(kind), page, ax=ax, options=options)
        return ax

    def _kind(self, kind: str | None) -> str:
        default = {
            "standalone": "correlations",
            "coverage": "coverage",
            "economics": "returns",
            "quantiles": "quantiles",
        }[self.section.name]
        result = kind or default
        allowed = {
            "standalone": ("correlations", "coverage"),
            "coverage": ("coverage",),
            "economics": ("returns", "costs"),
            "quantiles": ("quantiles", "quantile_counts"),
        }[self.section.name]
        if result not in allowed:
            raise ContractError("plot is not available for this section")
        return result

    def specification(self) -> dict[str, object]:
        return {"section_id": self.run_id, "selection": asdict(self.selection)}

    def export(
        self,
        output_dir: str | Path,
        *,
        kind: str | None = None,
        options: PlotOptions = DEFAULT_PLOT,
        page: int = 0,
    ) -> Path:
        """Export just this table, or one chart page plus its exact table."""
        from .component_export import Component, export_components

        return export_components([Component(self, kind, options, page)], output_dir)
