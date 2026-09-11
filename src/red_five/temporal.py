"""Declared fold partitions for supplied predictions, without upstream model fitting."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import timedelta
from typing import Literal

from .contracts import (
    ContractError,
    EvaluationConfig,
    Prediction,
    identifier,
    timestamp,
)
from .quantiles import QuantileConfig, evaluate_quantiles
from .reporting import canonical, software_versions, source_identity
from .sections import COUNTS, METRICS, SectionResult, cell, group_columns, seal_section
from .signal_io import MAX_BYTES, digest, json_object, parse_predictions
from .standalone import evaluate_groups
from .visualization import Cell, Table, sequence

FoldSection = Literal["standalone", "coverage", "quantiles"]


@dataclass(frozen=True)
class FoldSpec:
    fold_id: str
    train_start: str
    test_start: str
    test_end: str
    gap_seconds: int = 0

    def __post_init__(self) -> None:
        identifier(self.fold_id, "fold_id")
        for key in ("train_start", "test_start", "test_end"):
            object.__setattr__(
                self, key, timestamp(getattr(self, key), key).isoformat()
            )
        if type(self.gap_seconds) is not int or not 0 <= self.gap_seconds <= 31536000:
            raise ContractError("gap_seconds must be an integer in [0, 31536000]")
        start = timestamp(self.train_start, "train_start")
        test = timestamp(self.test_start, "test_start")
        end = timestamp(self.test_end, "test_end")
        if not start < test < end or (test - start).total_seconds() <= self.gap_seconds:
            raise ContractError(
                "fold must have train_start < training cutoff <= test_start < test_end"
            )

    @property
    def training_cutoff(self) -> str:
        return (
            timestamp(self.test_start, "test_start")
            - timedelta(seconds=self.gap_seconds)
        ).isoformat()


ROLES = (
    "training",
    "gap",
    "unavailable_training_label",
    "missing_training_label",
    "test",
    "outside_window",
)


def _role(row: Prediction, fold: FoldSpec) -> str:
    start = timestamp(fold.train_start, "train_start")
    test = timestamp(fold.test_start, "test_start")
    end = timestamp(fold.test_end, "test_end")
    boundary = timestamp(fold.training_cutoff, "training_cutoff")
    if test <= row.decision_time < end:
        return "test"
    if not start <= row.decision_time < test:
        return "outside_window"
    if row.decision_time >= boundary:
        return "gap"
    if row.label_available_at >= boundary:
        return "unavailable_training_label"
    if row.forward_return is None:
        return "missing_training_label"
    return "training"


@dataclass(frozen=True)
class FoldAudit:
    """Immutable tables; membership retains one row per input and declared fold."""

    folds: tuple[FoldSpec, ...]
    summary: Table
    membership: Table
    signals_sha256: str
    config_sha256: str


def _inputs(
    signal_bytes: bytes, config_bytes: bytes
) -> tuple[EvaluationConfig, tuple[Prediction, ...]]:
    for content in (signal_bytes, config_bytes):
        if not content.strip() or len(content) > MAX_BYTES:
            raise ContractError("fold inputs must be nonempty and at most 16 MiB")
    config = EvaluationConfig.parse(json_object(config_bytes))
    return config, parse_predictions(signal_bytes, config)


def audit_folds(
    signal_bytes: bytes, config_bytes: bytes, folds: tuple[FoldSpec, ...]
) -> FoldAudit:
    config, rows = _inputs(signal_bytes, config_bytes)
    if type(folds) is not tuple or not 1 <= len(folds) <= 20:
        raise ContractError("declare an immutable tuple of 1 to 20 folds")
    if len({f.fold_id for f in folds}) != len(folds):
        raise ContractError("duplicate fold_id")
    if len(rows) * len(folds) > 100000:
        raise ContractError("fold membership exceeds 100000 rows")
    for i, fold in enumerate(folds):
        if timestamp(fold.test_end, "test_end") > config.as_of:
            raise ContractError("test_end exceeds report as_of")
        if i and timestamp(fold.test_start, "test_start") < timestamp(
            folds[i - 1].test_end, "test_end"
        ):
            raise ContractError("test windows must be ordered and nonoverlapping")
    members: list[tuple[Cell, ...]] = []
    summaries: list[tuple[Cell, ...]] = []
    for fold in folds:
        counts: dict[tuple[str, ...], dict[str, int]] = defaultdict(
            lambda: dict.fromkeys(ROLES, 0)
        )
        for row in rows:
            group = (
                (row.model_id, row.instrument_id, row.contract_id)
                if config.mode == "time_series"
                else (row.model_id,)
            )
            role = _role(row, fold)
            counts[group][role] += 1
            members.append(
                (
                    fold.fold_id,
                    row.model_id,
                    row.instrument_id,
                    row.contract_id,
                    row.decision_time.isoformat(),
                    row.label_start.isoformat(),
                    row.label_end.isoformat(),
                    row.label_available_at.isoformat(),
                    role,
                )
            )
        for group, values in sorted(counts.items()):
            summaries.append(
                (
                    fold.fold_id,
                    *group,
                    fold.training_cutoff,
                    fold.test_start,
                    fold.test_end,
                    *(values[k] for k in ROLES),
                )
            )
    return FoldAudit(
        folds,
        Table(
            (
                "fold_id",
                *(
                    group_columns(config)
                    if config.mode == "time_series"
                    else ("model_id",)
                ),
                "training_cutoff",
                "test_start",
                "test_end",
                *ROLES,
            ),
            tuple(summaries),
        ),
        Table(
            (
                "fold_id",
                "model_id",
                "instrument_id",
                "contract_id",
                "decision_time",
                "label_start",
                "label_end",
                "label_available_at",
                "role",
            ),
            tuple(members),
        ),
        digest(signal_bytes),
        digest(config_bytes),
    )


def evaluate_fold_section(
    name: FoldSection,
    signal_bytes: bytes,
    config_bytes: bytes,
    plan_bytes: bytes,
    lock_bytes: bytes,
    *,
    fold: FoldSpec,
    quantiles: QuantileConfig | None = None,
) -> SectionResult:
    """Evaluate supplied test predictions; only quantile boundaries are fitted here."""
    if name not in ("standalone", "coverage", "quantiles"):
        raise ContractError("fold section must be standalone, coverage or quantiles")
    if (name == "quantiles") != (quantiles is not None):
        raise ContractError("supply quantile options exactly for quantiles")
    if quantiles is not None and quantiles.training_end != fold.test_start:
        raise ContractError("quantile training_end must equal fold test_start")
    for content in (plan_bytes, lock_bytes):
        if not content.strip() or len(content) > MAX_BYTES:
            raise ContractError("fold plan/lock must be nonempty and at most 16 MiB")
    audit = audit_folds(signal_bytes, config_bytes, (fold,))
    config, rows = _inputs(signal_bytes, config_bytes)
    test = tuple(r for r in rows if _role(r, fold) == "test")
    details: dict[str, object] = {
        "fold": asdict(fold),
        "training_cutoff": fold.training_cutoff,
        "training_label_policy": (
            "available-strictly-before-cutoff; nonmissing; no post-test training"
        ),
        "upstream_out_of_sample": "unverified",
        "audit": {"columns": audit.summary.columns, "rows": audit.summary.rows},
        "membership_sha256": digest(canonical(audit.membership.rows)),
        "test_keys": [
            (r.model_id, r.instrument_id, r.contract_id, r.decision_time.isoformat())
            for r in test
        ],
    }
    if quantiles is not None:
        training = tuple(r for r in rows if _role(r, fold) == "training")
        table, fit = evaluate_quantiles(training + test, config, quantiles)
        details.update(fit)
    else:
        columns = (
            *group_columns(config),
            *COUNTS,
            *(METRICS if name == "standalone" else ()),
        )
        values = evaluate_groups(test, config, coverage_only=name == "coverage")
        table = Table(
            columns,
            tuple(
                tuple(cell(c) for c in sequence(r["group"]))
                + tuple(cell(r[k]) for k in columns[len(group_columns(config)) :])
                for r in values
            ),
        )
    status = (
        "unavailable"
        if not table.rows
        or (
            "status" in table.columns
            and all(
                r[table.columns.index("status")] == "unavailable" for r in table.rows
            )
        )
        else "computed"
    )
    return seal_section(
        name,
        json_object(config_bytes),
        table,
        {
            "signals_sha256": digest(signal_bytes),
            "config_sha256": digest(config_bytes),
            "analysis_plan_sha256": digest(plan_bytes),
            "lock_sha256": digest(lock_bytes),
            "fold": asdict(fold),
            "code": source_identity(),
            "software": software_versions(),
        },
        status,
        details,
    )
