"""Leakage-aware ordered validation for a simple time-indexed regression."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import UTC, datetime

import polars as pl

from .regression import CovarianceType, fit_simple_ols


@dataclass(frozen=True, slots=True)
class WalkForwardConfig:
    initial_test_index: int
    test_size: int
    step_size: int

    def __post_init__(self) -> None:
        if self.initial_test_index < 3:
            raise ValueError("initial_test_index must leave at least three candidates")
        if self.test_size < 1 or self.step_size < 1:
            raise ValueError("test_size and step_size must be positive")
        if self.step_size < self.test_size:
            raise ValueError("step_size must prevent overlapping test windows")


@dataclass(frozen=True, slots=True)
class ValidationMetrics:
    observations: int
    model_root_mean_square_error: float
    model_mean_absolute_error: float
    baseline_root_mean_square_error: float
    baseline_mean_absolute_error: float
    relative_mean_square_skill: float | None


@dataclass(frozen=True, slots=True)
class ValidationPrediction:
    prediction_time_utc: datetime
    actual: float
    model_prediction: float
    baseline_prediction: float


@dataclass(frozen=True, slots=True)
class ValidationFold:
    number: int
    training_start_utc: datetime
    training_end_utc: datetime
    test_start_utc: datetime
    test_end_utc: datetime
    training_observations: int
    purged_training_candidates: int
    test_observations: int
    intercept: float
    slope: float
    metrics: ValidationMetrics
    predictions: tuple[ValidationPrediction, ...]


@dataclass(frozen=True, slots=True)
class WalkForwardResult:
    folds: tuple[ValidationFold, ...]
    metrics: ValidationMetrics
    input_observations: int
    evaluated_observations: int
    skipped_evaluation_observations: int
    leakage_checks: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class _TimedObservation:
    prediction_time: datetime
    feature_available_at: datetime
    target_available_at: datetime
    predictor: float
    response: float


def _parse_utc(value: object, *, column: str, row_number: int) -> datetime:
    if not isinstance(value, str):
        raise ValueError(f"{column} row {row_number} must be ISO-8601 text")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError(
            f"{column} row {row_number} is not a valid timestamp"
        ) from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{column} row {row_number} must include an offset")
    return parsed.astimezone(UTC)


def _parse_finite(value: object, *, column: str, row_number: int) -> float:
    if isinstance(value, bool) or not isinstance(value, str | int | float):
        raise ValueError(f"{column} row {row_number} must be numeric")
    try:
        parsed = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{column} row {row_number} must be numeric") from error
    if not math.isfinite(parsed):
        raise ValueError(f"{column} row {row_number} must be finite")
    return parsed


def _validated_observations(
    frame: pl.DataFrame,
    *,
    response: str,
    predictor: str,
    prediction_time: str,
    feature_available_at: str,
    target_available_at: str,
) -> tuple[_TimedObservation, ...]:
    columns = (
        prediction_time,
        feature_available_at,
        target_available_at,
        predictor,
        response,
    )
    if len(set(columns)) != len(columns):
        raise ValueError("time, predictor, and response columns must be distinct")
    missing = set(columns) - set(frame.columns)
    if missing:
        raise ValueError(f"missing validation columns: {sorted(missing)}")

    observations: list[_TimedObservation] = []
    for row_number, row in enumerate(frame.select(columns).iter_rows(), start=2):
        prediction = _parse_utc(row[0], column=prediction_time, row_number=row_number)
        feature_time = _parse_utc(
            row[1], column=feature_available_at, row_number=row_number
        )
        target_time = _parse_utc(
            row[2], column=target_available_at, row_number=row_number
        )
        if feature_time > prediction:
            raise ValueError(
                f"feature is unavailable at prediction time on row {row_number}"
            )
        if target_time <= prediction:
            raise ValueError(
                f"target must become available after prediction on row {row_number}"
            )
        observations.append(
            _TimedObservation(
                prediction_time=prediction,
                feature_available_at=feature_time,
                target_available_at=target_time,
                predictor=_parse_finite(
                    row[3], column=predictor, row_number=row_number
                ),
                response=_parse_finite(row[4], column=response, row_number=row_number),
            )
        )
    if not observations:
        raise ValueError("validation input cannot be empty")
    for previous, current in zip(observations, observations[1:], strict=False):
        if current.prediction_time <= previous.prediction_time:
            raise ValueError("prediction times must be unique and strictly increasing")
    return tuple(observations)


def _metrics(
    actual: list[float], predictions: list[float], baselines: list[float]
) -> ValidationMetrics:
    if not actual or len(actual) != len(predictions) or len(actual) != len(baselines):
        raise ValueError("metric inputs must be nonempty and aligned")
    model_errors = [
        predicted - observed
        for observed, predicted in zip(actual, predictions, strict=True)
    ]
    baseline_errors = [
        baseline - observed
        for observed, baseline in zip(actual, baselines, strict=True)
    ]
    model_squared_error = sum(error * error for error in model_errors)
    baseline_squared_error = sum(error * error for error in baseline_errors)
    count = len(actual)
    return ValidationMetrics(
        observations=count,
        model_root_mean_square_error=math.sqrt(model_squared_error / count),
        model_mean_absolute_error=sum(abs(error) for error in model_errors) / count,
        baseline_root_mean_square_error=math.sqrt(baseline_squared_error / count),
        baseline_mean_absolute_error=sum(abs(error) for error in baseline_errors)
        / count,
        relative_mean_square_skill=(
            1.0 - model_squared_error / baseline_squared_error
            if baseline_squared_error > 0.0
            else None
        ),
    )


def validate_walk_forward(
    frame: pl.DataFrame,
    *,
    response: str,
    predictor: str,
    prediction_time: str,
    feature_available_at: str,
    target_available_at: str,
    config: WalkForwardConfig,
    covariance_type: CovarianceType = "HC3",
) -> WalkForwardResult:
    """Run non-overlapping expanding-window folds using only available labels."""
    rows = _validated_observations(
        frame,
        response=response,
        predictor=predictor,
        prediction_time=prediction_time,
        feature_available_at=feature_available_at,
        target_available_at=target_available_at,
    )
    if config.initial_test_index >= len(rows):
        raise ValueError("initial_test_index must be smaller than the input")

    folds: list[ValidationFold] = []
    all_actual: list[float] = []
    all_predictions: list[float] = []
    all_baselines: list[float] = []
    for fold_number, test_start in enumerate(
        range(config.initial_test_index, len(rows), config.step_size), start=1
    ):
        test_rows = rows[test_start : test_start + config.test_size]
        test_start_time = test_rows[0].prediction_time
        candidates = rows[:test_start]
        training_rows = tuple(
            row for row in candidates if row.target_available_at < test_start_time
        )
        if len(training_rows) < 3:
            raise ValueError(
                f"fold {fold_number} has fewer than three available training labels"
            )
        training_frame = pl.DataFrame(
            {
                predictor: [row.predictor for row in training_rows],
                response: [row.response for row in training_rows],
            }
        )
        fit = fit_simple_ols(
            training_frame,
            response=response,
            predictor=predictor,
            covariance_type=covariance_type,
        )
        baseline = sum(row.response for row in training_rows) / len(training_rows)
        actual = [row.response for row in test_rows]
        predictions = [fit.intercept + fit.slope * row.predictor for row in test_rows]
        baselines = [baseline for _ in test_rows]
        fold_metrics = _metrics(actual, predictions, baselines)
        all_actual.extend(actual)
        all_predictions.extend(predictions)
        all_baselines.extend(baselines)
        folds.append(
            ValidationFold(
                number=fold_number,
                training_start_utc=training_rows[0].prediction_time,
                training_end_utc=training_rows[-1].prediction_time,
                test_start_utc=test_start_time,
                test_end_utc=test_rows[-1].prediction_time,
                training_observations=len(training_rows),
                purged_training_candidates=len(candidates) - len(training_rows),
                test_observations=len(test_rows),
                intercept=fit.intercept,
                slope=fit.slope,
                metrics=fold_metrics,
                predictions=tuple(
                    ValidationPrediction(
                        prediction_time_utc=row.prediction_time,
                        actual=observed,
                        model_prediction=predicted,
                        baseline_prediction=baseline_prediction,
                    )
                    for row, observed, predicted, baseline_prediction in zip(
                        test_rows, actual, predictions, baselines, strict=True
                    )
                ),
            )
        )
    return WalkForwardResult(
        folds=tuple(folds),
        metrics=_metrics(all_actual, all_predictions, all_baselines),
        input_observations=len(rows),
        evaluated_observations=len(all_actual),
        skipped_evaluation_observations=(
            len(rows) - config.initial_test_index - len(all_actual)
        ),
        leakage_checks=(
            "input_prediction_times_strictly_increasing",
            "features_available_by_prediction_time",
            "targets_available_after_prediction_time",
            "training_labels_available_strictly_before_test_window",
            "test_windows_non_overlapping",
        ),
    )
