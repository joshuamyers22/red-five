"""Boundary parsing with source provenance."""

from __future__ import annotations

import hashlib
import io
from dataclasses import dataclass
from pathlib import Path

import polars as pl

from .model import Observation

REQUIRED_COLUMNS = ("timestamp", "instrument", "value", "unit")


@dataclass(frozen=True, slots=True)
class Dataset:
    observations: tuple[Observation, ...]
    source_sha256: str


def load_csv(path: Path) -> Dataset:
    """Load a strict CSV with Polars while recording exact input identity."""
    content = path.read_bytes()
    digest = hashlib.sha256(content).hexdigest()
    try:
        frame = pl.read_csv(
            io.BytesIO(content),
            infer_schema=False,
            try_parse_dates=False,
            ignore_errors=False,
        )
    except pl.exceptions.PolarsError as error:
        raise ValueError("invalid CSV input") from error
    if set(frame.columns) != set(REQUIRED_COLUMNS) or len(frame.columns) != len(
        REQUIRED_COLUMNS
    ):
        raise ValueError(f"columns must be exactly {sorted(REQUIRED_COLUMNS)}")
    observations: list[Observation] = []
    for row in frame.select(REQUIRED_COLUMNS).iter_rows():
        if len(row) != len(REQUIRED_COLUMNS) or not all(
            isinstance(value, str) for value in row
        ):
            raise ValueError("required CSV fields cannot be null")
        timestamp, instrument, value, unit = row
        observations.append(Observation.parse(timestamp, instrument, value, unit))
    return Dataset(tuple(observations), digest)
