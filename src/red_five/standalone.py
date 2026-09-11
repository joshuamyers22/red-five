"""Descriptive correlations with explicit grouping and coverage."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from math import isfinite

import numpy as np
import polars as pl
from numpy.typing import NDArray

from .contracts import ContractError, EvaluationConfig, Prediction


@dataclass(frozen=True, slots=True)
class CorrelationMetrics:
    pearson_ic: float | None
    rank_ic: float | None
    reason: str | None


def correlations(x: list[float], y: list[float], minimum: int) -> CorrelationMetrics:
    if len(x) != len(y) or minimum < 3:
        raise ContractError("correlation requires paired samples and minimum >= 3")
    if not all(isfinite(v) for v in (*x, *y)):
        raise ContractError("correlation requires finite values")
    if len(x) < minimum:
        return CorrelationMetrics(None, None, "too-few-observations")
    if len(set(x)) == 1 or len(set(y)) == 1:
        return CorrelationMetrics(None, None, "constant-score-or-target")

    def pearson(a: list[float], b: list[float]) -> float | None:
        left: NDArray[np.float64] = np.asarray(a, dtype=np.float64)
        right: NDArray[np.float64] = np.asarray(b, dtype=np.float64)
        # Scale before centering to avoid overflow on otherwise finite inputs.
        left = left / np.max(np.abs(left))
        right = right / np.max(np.abs(right))
        left = left - left.mean()
        right = right - right.mean()
        denominator = float(np.linalg.norm(left) * np.linalg.norm(right))
        if denominator == 0:
            return None
        value = float(np.dot(left, right) / denominator)
        if not isfinite(value):
            return None
        return max(-1.0, min(1.0, value))

    xr = [float(v) for v in pl.Series(x).rank(method="average").to_list()]
    yr = [float(v) for v in pl.Series(y).rank(method="average").to_list()]
    linear, rank = pearson(x, y), pearson(xr, yr)
    reason = "numerical-degeneracy" if linear is None or rank is None else None
    return CorrelationMetrics(linear, rank, reason)


def evaluate_groups(
    rows: tuple[Prediction, ...], config: EvaluationConfig
) -> list[dict[str, object]]:
    groups: dict[tuple[str, ...], list[Prediction]] = defaultdict(list)
    for row in rows:
        key = (
            (row.model_id, row.instrument_id, row.contract_id)
            if config.mode == "time_series"
            else (row.model_id, row.decision_time.isoformat())
        )
        groups[key].append(row)
    results: list[dict[str, object]] = []
    for key, sample in sorted(groups.items()):
        ready = [r for r in sample if r.label_available_at <= config.as_of]
        eligible = [r for r in ready if r.forward_return is not None]
        metrics = correlations(
            [r.signal for r in eligible],
            [r.forward_return for r in eligible if r.forward_return is not None],
            config.minimum_observations,
        )
        results.append(
            {
                "group": list(key),
                "observations": len(sample),
                "eligible_observations": len(eligible),
                "immature_labels": len(sample) - len(ready),
                "missing_mature_labels": len(ready) - len(eligible),
                "pearson_ic": metrics.pearson_ic,
                "rank_ic": metrics.rank_ic,
                "status": "available" if metrics.reason is None else "unavailable",
                "reason": metrics.reason,
            }
        )
    return results
