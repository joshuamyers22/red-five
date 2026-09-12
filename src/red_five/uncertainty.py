"""Conditional moving-block percentile intervals, never a selection verdict."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, dataclass
from math import ceil
from typing import Literal, cast

import numpy as np

from .contracts import ContractError, EvaluationConfig, Prediction
from .reporting import canonical
from .signal_io import digest
from .standalone import correlations, evaluate_groups
from .visualization import Cell, Table

UNCERTAINTY_FIELDS = (
    "metric",
    "estimand",
    "time_points",
    "eligible_time_points",
    "observations",
    "eligible_observations",
    "immature_labels",
    "missing_mature_labels",
    "block_length",
    "replicates",
    "valid_replicates",
    "estimate",
    "lower",
    "upper",
    "standard_error",
    "status",
    "reason",
)


@dataclass(frozen=True)
class BootstrapConfig:
    metric: Literal["pearson_ic", "rank_ic"]
    block_length: int
    replicates: int
    seed: int
    confidence: float
    step_seconds: int
    minimum_time_points: int

    @classmethod
    def parse(cls, value: dict[str, object]) -> BootstrapConfig:
        if set(value) != {
            "metric",
            "block_length",
            "replicates",
            "seed",
            "confidence",
            "step_seconds",
            "minimum_time_points",
        }:
            raise ContractError("bootstrap policy fields do not match")
        return cls(
            cast(Literal["pearson_ic", "rank_ic"], value["metric"]),
            cast(int, value["block_length"]),
            cast(int, value["replicates"]),
            cast(int, value["seed"]),
            cast(float, value["confidence"]),
            cast(int, value["step_seconds"]),
            cast(int, value["minimum_time_points"]),
        )

    def __post_init__(self) -> None:
        if self.metric not in ("pearson_ic", "rank_ic"):
            raise ContractError("bootstrap metric must be pearson_ic or rank_ic")
        for name, low, high in (
            ("block_length", 1, 1000),
            ("replicates", 200, 2000),
            ("seed", 0, 2**32 - 1),
            ("step_seconds", 1, 31536000),
            ("minimum_time_points", 10, 100000),
        ):
            value = getattr(self, name)
            if type(value) is not int or not low <= value <= high:
                raise ContractError(f"{name} must be an integer in [{low}, {high}]")
        if type(self.confidence) is not float or not 0.8 <= self.confidence <= 0.99:
            raise ContractError("confidence must be a float in [0.8, 0.99]")
        if self.replicates * (1 - self.confidence) / 2 < 5 - 1e-10:
            raise ContractError("bootstrap needs at least five expected draws per tail")


def _correlation(x: list[float], y: list[float], metric: str) -> float | None:
    result = correlations(x, y, 3)
    return result.pearson_ic if metric == "pearson_ic" else result.rank_ic


def evaluate_uncertainty(
    rows: tuple[Prediction, ...], config: EvaluationConfig, options: BootstrapConfig
) -> tuple[Table, dict[str, object]]:
    if len(rows) * options.replicates > 2_000_000:
        raise ContractError("bootstrap work exceeds 2000000 row-replicates")
    groups: dict[tuple[str, ...], list[Prediction]] = defaultdict(list)
    for row in rows:
        key = (
            (row.model_id, row.instrument_id, row.contract_id)
            if config.mode == "time_series"
            else (row.model_id,)
        )
        groups[key].append(row)
    output: list[tuple[Cell, ...]] = []
    evidence: list[dict[str, object]] = []
    for key, sample in sorted(groups.items()):
        sample.sort(key=lambda r: (r.decision_time, r.instrument_id, r.contract_id))
        times = sorted({r.decision_time for r in sample})
        n = len(times)
        ready = [r for r in sample if r.label_available_at <= config.as_of]
        eligible = [r for r in ready if r.forward_return is not None]
        x: list[float] = []
        y: list[float] = []
        if config.mode == "time_series":
            x = [r.signal for r in eligible]
            y = [r.forward_return for r in eligible if r.forward_return is not None]
            values: list[float] = []
            usable = len(eligible)
            estimate = _correlation(x, y, options.metric)
            estimand = "within-model-temporal-correlation"
            dated: list[dict[str, object]] = []
        else:
            dated = evaluate_groups(tuple(sample), config)
            values = []
            for record in dated:
                value = record[options.metric]
                if isinstance(value, (int, float)):
                    values.append(float(value))
            usable = len(values)
            estimate = float(np.mean(values)) if values else None
            estimand = "equal-date-mean-cross-sectional-ic"
        overlap_steps = max(
            ceil((r.label_end - r.label_start).total_seconds() / options.step_seconds)
            for r in sample
        )
        reason = (
            "incomplete-time-grid"
            if usable != n
            else "irregular-time-grid"
            if any(
                (b - a).total_seconds() != options.step_seconds
                for a, b in zip(times, times[1:], strict=False)
            )
            else "too-few-time-points"
            if n < options.minimum_time_points
            or (config.mode == "time_series" and n < config.minimum_observations)
            else "too-few-blocks"
            if n < 3 * options.block_length
            else "block-shorter-than-label-span"
            if options.block_length < overlap_steps
            else "constant-score-or-target"
            if estimate is None
            else None
        )
        draws: list[float] = []
        lower: float | None = None
        upper: float | None = None
        standard_error: float | None = None
        if reason is None:
            group_seed = int(digest(canonical(key))[:8], 16)
            rng = np.random.default_rng(
                np.random.SeedSequence([options.seed, group_seed])
            )
            for _ in range(options.replicates):
                starts = rng.integers(
                    0, n - options.block_length + 1, size=ceil(n / options.block_length)
                )
                indices = [
                    int(start) + offset
                    for start in starts
                    for offset in range(options.block_length)
                ][:n]
                value = (
                    _correlation(
                        [x[i] for i in indices], [y[i] for i in indices], options.metric
                    )
                    if config.mode == "time_series"
                    else float(np.mean([values[i] for i in indices]))
                )
                if value is not None:
                    draws.append(value)
            if len(draws) != options.replicates:
                reason = "degenerate-replicates"
            elif float(np.ptp(draws)) <= 1e-12:
                reason = "degenerate-bootstrap"
            else:
                tail = (1 - options.confidence) / 2
                bounds = np.quantile(draws, [tail, 1 - tail], method="linear")
                lower, upper = float(bounds[0]), float(bounds[1])
                standard_error = float(np.std(draws, ddof=1))
        output.append(
            (
                *key,
                options.metric,
                estimand,
                n,
                usable,
                len(sample),
                len(eligible),
                len(sample) - len(ready),
                len(ready) - len(eligible),
                options.block_length,
                options.replicates,
                len(draws),
                estimate,
                lower,
                upper,
                standard_error,
                "available" if reason is None else "unavailable",
                reason,
            )
        )
        evidence.append(
            {
                "group": key,
                "times": [t.isoformat() for t in times],
                "label_span_steps": overlap_steps,
                "per_date": dated,
            }
        )
    return Table(
        (
            *(
                ("model_id", "instrument_id", "contract_id")
                if config.mode == "time_series"
                else ("model_id",)
            ),
            *UNCERTAINTY_FIELDS,
        ),
        tuple(output),
    ), {
        "policy": asdict(options),
        "method": "moving-block/percentile/linear-quantile",
        "resampling": (
            "noncircular overlapping blocks; concatenate then truncate to n; "
            "paired TS rows or CS date ICs"
        ),
        "groups": evidence,
        "selection_adjusted": False,
        "upstream_out_of_sample": "unverified",
        "assumptions": (
            "regular elapsed-time grid; approximate stationarity/weak dependence; "
            "declared block adequacy unverified"
        ),
    }
