"""Bounded, explicit CSV/JSON trust boundaries for signal evaluation."""

from __future__ import annotations

import hashlib
import io
import json
from dataclasses import fields
from pathlib import Path
from typing import cast

import polars as pl

from .contracts import ContractError, EvaluationConfig, Prediction, WeightObservation

MAX_BYTES = 16 * 1024 * 1024
MAX_ROWS = 100_000


def read_bytes(path: Path) -> bytes:
    with path.open("rb") as source:
        content = source.read(MAX_BYTES + 1)
    if len(content) > MAX_BYTES:
        raise ContractError("input exceeds 16 MiB limit")
    if not content.strip():
        raise ContractError("input cannot be empty")
    return content


def digest(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ContractError("duplicate JSON key")
        result[key] = value
    return result


def json_object(content: bytes) -> dict[str, object]:
    try:
        result = cast(object, json.loads(content, object_pairs_hook=_unique_object))
    except (ValueError, UnicodeDecodeError) as error:
        raise ContractError("invalid JSON object") from error
    if not isinstance(result, dict):
        raise ContractError("JSON root must be an object")
    return cast(dict[str, object], result)


def csv_rows(content: bytes, columns: list[str]) -> list[dict[str, object]]:
    try:
        frame = pl.read_csv(
            io.BytesIO(content), infer_schema=False, n_rows=MAX_ROWS + 1
        )
    except pl.exceptions.PolarsError as error:
        raise ContractError("invalid CSV input") from error
    if frame.columns != columns:
        raise ContractError("CSV columns/order do not match the declared schema")
    if frame.height > MAX_ROWS:
        raise ContractError("CSV exceeds 100000 row limit")
    if frame.is_empty():
        raise ContractError("CSV must contain observations")
    return cast(list[dict[str, object]], frame.to_dicts())


def parse_predictions(
    content: bytes, config: EvaluationConfig
) -> tuple[Prediction, ...]:
    rows = tuple(
        Prediction.parse(row, config)
        for row in csv_rows(content, [field.name for field in fields(Prediction)])
    )
    keys = {(r.model_id, r.instrument_id, r.contract_id, r.decision_time) for r in rows}
    if len(keys) != len(rows):
        raise ContractError("duplicate prediction key")
    if config.mode == "time_series":
        identities: dict[str, tuple[str, str]] = {}
        for row in rows:
            pair = row.instrument_id, row.contract_id
            if identities.setdefault(row.model_id, pair) != pair:
                raise ContractError(
                    "time-series model_id must identify one instrument/contract"
                )
    return tuple(
        sorted(
            rows,
            key=lambda r: (r.model_id, r.instrument_id, r.contract_id, r.decision_time),
        )
    )


def parse_weights(
    content: bytes, config: EvaluationConfig
) -> tuple[WeightObservation, ...]:
    rows = tuple(
        WeightObservation.parse(row, config)
        for row in csv_rows(
            content, [field.name for field in fields(WeightObservation)]
        )
    )
    keys = {
        (r.portfolio_id, r.instrument_id, r.contract_id, r.decision_time) for r in rows
    }
    if len(keys) != len(rows):
        raise ContractError("duplicate supplied-weight key")
    intervals: dict[tuple[str, object], tuple[object, object]] = {}
    for row in rows:
        key = row.portfolio_id, row.decision_time
        span = row.label_start, row.label_end
        if intervals.setdefault(key, span) != span:
            raise ContractError("portfolio constituents must share a return interval")
    return tuple(
        sorted(
            rows,
            key=lambda r: (
                r.portfolio_id,
                r.decision_time,
                r.instrument_id,
                r.contract_id,
            ),
        )
    )
