"""Independent, immutable report sections using the existing numerical functions."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import TYPE_CHECKING, Literal, cast

from .contracts import ContractError, EvaluationConfig
from .economics import account_weights
from .quantiles import QUANTILE_FIELDS, QuantileConfig, evaluate_quantiles
from .reporting import canonical, software_versions, source_identity, verify_report
from .signal_io import MAX_BYTES, digest, json_object, parse_predictions, parse_weights
from .standalone import evaluate_groups
from .visualization import Cell, ReportView, Table, mapping, number, sequence, text_cell

if TYPE_CHECKING:
    from .composition import Panel, Selection

SectionName = Literal["standalone", "coverage", "economics", "quantiles"]
SCHEMA = "red-five-section/v1"
QUANTILE_SCHEMA = "red-five-section/v2"
COUNTS = (
    "observations",
    "eligible_observations",
    "immature_labels",
    "missing_mature_labels",
)
METRICS = ("pearson_ic", "rank_ic", "status", "reason")
ECONOMICS = (
    "portfolio_id",
    "decision_time",
    "label_start",
    "label_end",
    "constituents",
    "gross_return",
    "trading_cost_return",
    "holding_cost_return",
    "net_return",
    "turnover_absolute",
)


def group_columns(config: EvaluationConfig) -> tuple[str, ...]:
    return (
        ("model_id", "instrument_id", "contract_id")
        if config.mode == "time_series"
        else ("model_id", "decision_time")
    )


def cell(value: object) -> Cell:
    if value is None or isinstance(value, str):
        return None if value is None else text_cell(value)
    return number(value)


@dataclass(frozen=True, init=False)
class SectionResult:
    """Versioned section evidence. A successful section is never a full verdict."""

    content: bytes
    section_id: str
    name: SectionName
    config: EvaluationConfig
    data: Table
    status: str

    def __init__(self, content: bytes) -> None:
        if len(content) > MAX_BYTES:
            raise ContractError("section exceeds 16 MiB")
        value = json_object(content)
        section_id = value.pop("section_id", None)
        if value.get("schema_version") not in (
            SCHEMA,
            QUANTILE_SCHEMA,
        ) or section_id != digest(canonical(value)):
            raise ContractError("section schema or digest mismatch")
        name = value.get("name")
        if name not in ("standalone", "coverage", "economics", "quantiles"):
            raise ContractError("section is not implemented")
        if (name == "quantiles") != (value["schema_version"] == QUANTILE_SCHEMA):
            raise ContractError("quantile sections require schema v2")
        config = EvaluationConfig.parse(
            mapping(mapping(value.get("identity")).get("config"))
        )
        table = mapping(value.get("table"))
        columns = tuple(text_cell(c) for c in sequence(table.get("columns")))
        expected = (
            ECONOMICS
            if name == "economics"
            else (*group_columns(config), *QUANTILE_FIELDS)
            if name == "quantiles"
            else (
                *group_columns(config),
                *COUNTS,
                *(METRICS if name == "standalone" else ()),
            )
        )
        if columns != expected:
            raise ContractError("section table schema mismatch")
        rows = tuple(
            tuple(cell(c) for c in sequence(row)) for row in sequence(table.get("rows"))
        )
        if any(len(row) != len(columns) for row in rows):
            raise ContractError("section row width mismatch")
        for row in rows:
            for key, entry in zip(columns, row, strict=True):
                if key in (
                    *COUNTS,
                    "constituents",
                    "bin",
                    "requested_bins",
                    "effective_bins",
                    "training_observations",
                    "out_of_range",
                ):
                    number(entry, count=True)
                elif key in ("pearson_ic", "rank_ic"):
                    if entry is not None and abs(number(entry)) > 1:
                        raise ContractError("invalid section correlation")
                elif key in ("mean_return", "spread"):
                    if entry is not None:
                        number(entry)
                elif key in ECONOMICS[5:]:
                    try:
                        amount = Decimal(text_cell(entry))
                        if not amount.is_finite() or abs(amount) > Decimal("1e30"):
                            raise ContractError("invalid section accounting amount")
                    except InvalidOperation as error:
                        raise ContractError(
                            "invalid section accounting amount"
                        ) from error
                elif (
                    key
                    not in (
                        "reason",
                        "spread_reason",
                        "monotonicity",
                        "monotonicity_reason",
                    )
                    or entry is not None
                ):
                    text_cell(entry)
        if name == "quantiles":
            details = mapping(value.get("diagnostics"))
            policy = mapping(details.get("policy"))
            if set(policy) != {
                "training_end",
                "bins",
                "minimum_training",
                "minimum_bin",
            }:
                raise ContractError("quantile policy missing from evidence")
            if any(
                type(policy[k]) is not int
                for k in ("bins", "minimum_training", "minimum_bin")
            ):
                raise ContractError("invalid quantile policy types")
            QuantileConfig(
                text_cell(policy["training_end"]),
                cast(int, policy["bins"]),
                cast(int, policy["minimum_training"]),
                cast(int, policy["minimum_bin"]),
            )
        if (
            value.get("status") not in ("computed", "unavailable")
            or value.get("verdict") is not None
            or value.get("scope") != "partial"
        ):
            raise ContractError("invalid partial section status")
        for key, item in {
            "content": content,
            "section_id": section_id,
            "name": name,
            "config": config,
            "data": Table(columns, rows),
            "status": value["status"],
        }.items():
            object.__setattr__(self, key, item)

    def select(self, selection: Selection | None = None) -> Panel:
        from .composition import Panel, Selection

        return Panel(self, selection or Selection())

    def _repr_html_(self) -> str:
        return self.select().html()

    @property
    def diagnostics(self) -> dict[str, object]:
        """A fresh copy of fit metadata; editing it cannot mutate section evidence."""
        return mapping(json_object(self.content).get("diagnostics", {}))


def seal_section(
    name: SectionName,
    config: dict[str, object],
    data: Table,
    identity: dict[str, object],
    status: str = "computed",
    diagnostics: dict[str, object] | None = None,
) -> SectionResult:
    value: dict[str, object] = {
        "schema_version": QUANTILE_SCHEMA if name == "quantiles" else SCHEMA,
        "name": name,
        "scope": "partial",
        "status": status,
        "verdict": None,
        "not_requested": [
            n for n in ("standalone", "coverage", "economics", "quantiles") if n != name
        ],
        "identity": {**identity, "config": config},
        "table": {"columns": data.columns, "rows": data.rows},
    }
    if diagnostics is not None:
        value["diagnostics"] = diagnostics
    return SectionResult(canonical({**value, "section_id": digest(canonical(value))}))


def evaluate_section(
    name: SectionName,
    signal_bytes: bytes,
    config_bytes: bytes,
    plan_bytes: bytes,
    lock_bytes: bytes,
    *,
    weight_bytes: bytes | None = None,
    quantiles: QuantileConfig | None = None,
) -> SectionResult:
    """Compute one section in memory; new numerical samples require new inputs."""
    if name not in ("standalone", "coverage", "economics", "quantiles"):
        raise ContractError("section is not implemented")
    if (name == "quantiles") != (quantiles is not None):
        raise ContractError("supply quantile options exactly when requesting quantiles")
    if name != "economics" and weight_bytes is not None:
        raise ContractError("weights are not an input to non-economics sections")
    for content in (signal_bytes, config_bytes, plan_bytes, lock_bytes, weight_bytes):
        if content is not None and (not content.strip() or len(content) > MAX_BYTES):
            raise ContractError("section inputs must be nonempty and at most 16 MiB")
    declaration = json_object(config_bytes)
    config = EvaluationConfig.parse(declaration)
    predictions = parse_predictions(signal_bytes, config)
    status = "computed"
    diagnostics: dict[str, object] | None = None
    if name == "quantiles":
        assert quantiles is not None
        table, diagnostics = evaluate_quantiles(predictions, config, quantiles)
        if not table.rows or all(
            row[table.columns.index("status")] == "unavailable" for row in table.rows
        ):
            status = "unavailable"
    elif name == "economics":
        if weight_bytes is None:
            raise ContractError("economics requires supplied weights")
        weights = parse_weights(weight_bytes, config)
        periods = {
            (
                r.instrument_id,
                r.contract_id,
                r.decision_time,
                r.label_start,
                r.label_end,
            )
            for r in predictions
        }
        if any(
            (
                r.instrument_id,
                r.contract_id,
                r.decision_time,
                r.label_start,
                r.label_end,
            )
            not in periods
            for r in weights
        ):
            raise ContractError(
                "supplied weight interval is not represented in the signal panel"
            )
        values = sequence(account_weights(weights)["periods"])
        table = Table(
            ECONOMICS,
            tuple(
                tuple(cell(mapping(row)[key]) for key in ECONOMICS) for row in values
            ),
        )
    else:
        values = evaluate_groups(predictions, config, coverage_only=name == "coverage")
        columns = (
            *group_columns(config),
            *COUNTS,
            *(METRICS if name == "standalone" else ()),
        )
        table = Table(
            columns,
            tuple(
                tuple(cell(c) for c in sequence(row["group"]))
                + tuple(cell(row[key]) for key in columns[len(group_columns(config)) :])
                for row in values
            ),
        )
        if name == "standalone" and all(
            row["status"] == "unavailable" for row in values
        ):
            status = "unavailable"
    return seal_section(
        name,
        declaration,
        table,
        {
            "signals_sha256": digest(signal_bytes),
            "weights_sha256": None if weight_bytes is None else digest(weight_bytes),
            "config_sha256": digest(config_bytes),
            "analysis_plan_sha256": digest(plan_bytes),
            "lock_sha256": digest(lock_bytes),
            "code": source_identity(),
            "software": software_versions(),
        },
        status,
        diagnostics,
    )


def section_from_report(view: ReportView, name: SectionName) -> SectionResult:
    """Extract values without reevaluation; preserve the original report lineage."""
    if name == "quantiles":
        raise ContractError(
            "full report v1 has no quantile evidence; use evaluate_section"
        )
    if name not in ("standalone", "coverage", "economics"):
        raise ContractError("section is not implemented")
    table = view.tables["economics" if name == "economics" else "signals"]
    if name == "coverage":
        indices = [
            table.columns.index(key) for key in (*group_columns(view.config), *COUNTS)
        ]
        table = Table(
            tuple(table.columns[i] for i in indices),
            tuple(tuple(row[i] for i in indices) for row in table.rows),
        )
    report = verify_report(view.content)
    identity = mapping(report["identity"])
    status = "computed" if table.rows else "unavailable"
    if name == "standalone" and all(
        row[table.columns.index("status")] == "unavailable" for row in table.rows
    ):
        status = "unavailable"
    return seal_section(
        name,
        mapping(identity["config"]),
        table,
        {
            **identity,
            "source_report_sha256": digest(view.content),
            "source_run_id": view.run_id,
        },
        status,
    )


def load_section(path: str | Path) -> SectionResult:
    from .signal_io import read_bytes

    return SectionResult(read_bytes(Path(path)))
