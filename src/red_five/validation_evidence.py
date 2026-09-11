"""Deterministic evidence for leakage-aware ordered validation."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC

import polars as pl

from .evidence import AnalysisDeclaration, SoftwareVersions, validate_sha256
from .regression import CovarianceType
from .validation import (
    ValidationMetrics,
    WalkForwardConfig,
    WalkForwardResult,
    validate_walk_forward,
)

SCHEMA_VERSION = "quant-time-validation-evidence/v1"


def _metrics_dict(metrics: ValidationMetrics) -> dict[str, object]:
    return {
        "observations": metrics.observations,
        "model_root_mean_square_error": metrics.model_root_mean_square_error,
        "model_mean_absolute_error": metrics.model_mean_absolute_error,
        "baseline_root_mean_square_error": metrics.baseline_root_mean_square_error,
        "baseline_mean_absolute_error": metrics.baseline_mean_absolute_error,
        "relative_mean_square_skill": metrics.relative_mean_square_skill,
    }


@dataclass(frozen=True, slots=True)
class TimeValidationEvidence:
    declaration: AnalysisDeclaration
    input_path: str
    input_sha256: str
    analysis_plan_path: str
    analysis_plan_sha256: str
    response: str
    predictor: str
    prediction_time: str
    feature_available_at: str
    target_available_at: str
    covariance_type: CovarianceType
    config: WalkForwardConfig
    result: WalkForwardResult
    software: SoftwareVersions

    def as_dict(self) -> dict[str, object]:
        folds = [
            {
                "number": fold.number,
                "training_start_utc": fold.training_start_utc.astimezone(UTC)
                .isoformat()
                .replace("+00:00", "Z"),
                "training_end_utc": fold.training_end_utc.astimezone(UTC)
                .isoformat()
                .replace("+00:00", "Z"),
                "test_start_utc": fold.test_start_utc.astimezone(UTC)
                .isoformat()
                .replace("+00:00", "Z"),
                "test_end_utc": fold.test_end_utc.astimezone(UTC)
                .isoformat()
                .replace("+00:00", "Z"),
                "training_observations": fold.training_observations,
                "purged_training_candidates": fold.purged_training_candidates,
                "test_observations": fold.test_observations,
                "coefficients": {
                    "intercept": fold.intercept,
                    self.predictor: fold.slope,
                },
                "metrics": _metrics_dict(fold.metrics),
                "predictions": [
                    {
                        "prediction_time_utc": item.prediction_time_utc.astimezone(UTC)
                        .isoformat()
                        .replace("+00:00", "Z"),
                        "actual": item.actual,
                        "model_prediction": item.model_prediction,
                        "baseline_prediction": item.baseline_prediction,
                    }
                    for item in fold.predictions
                ],
            }
            for fold in self.result.folds
        ]
        return {
            "schema_version": SCHEMA_VERSION,
            "analysis": {
                "id": self.declaration.analysis_id,
                "evaluated_at_utc": self.declaration.evaluated_at_utc.astimezone(UTC)
                .isoformat()
                .replace("+00:00", "Z"),
                "code_revision": self.declaration.code_revision,
                "analysis_plan": {
                    "path": self.analysis_plan_path,
                    "sha256": self.analysis_plan_sha256,
                },
            },
            "data": {
                "path": self.input_path,
                "sha256": self.input_sha256,
                "sample_filters": self.declaration.sample_filters,
                "input_observations": self.result.input_observations,
            },
            "specification": {
                "model": "statsmodels.api.OLS",
                "response": self.response,
                "ordered_design_matrix": ["intercept", self.predictor],
                "intercept": "explicit",
                "missing_data": "raise",
                "covariance_type": self.covariance_type,
                "prediction_time": self.prediction_time,
                "feature_available_at": self.feature_available_at,
                "target_available_at": self.target_available_at,
            },
            "validation": {
                "kind": "expanding_window_ordered",
                "declared_design": self.declaration.validation_design,
                "declared_leakage_controls": self.declaration.leakage_controls,
                "initial_test_index": self.config.initial_test_index,
                "test_size": self.config.test_size,
                "step_size": self.config.step_size,
                "training_label_cutoff": "strictly_before_test_start",
                "executed_leakage_checks": list(self.result.leakage_checks),
                "evaluated_observations": self.result.evaluated_observations,
                "skipped_evaluation_observations": (
                    self.result.skipped_evaluation_observations
                ),
                "folds": folds,
                "aggregate_metrics": _metrics_dict(self.result.metrics),
            },
            "baseline": {
                "kind": "training_response_mean",
                "refit_for_each_fold": True,
            },
            "software": {
                "python": self.software.python,
                "numpy": self.software.numpy,
                "polars": self.software.polars,
                "statsmodels": self.software.statsmodels,
            },
            "limitations": [
                "Availability timestamps are controls only if upstream metadata is "
                "truthful.",
                "This reference path does not model costs, capacity, dependence, or "
                "live execution.",
                "Model approval requires pre-specified thresholds and independent "
                "review.",
            ],
        }

    def to_json_bytes(self) -> bytes:
        text = (
            json.dumps(self.as_dict(), allow_nan=False, indent=2, sort_keys=True) + "\n"
        )
        return text.encode("utf-8")


def build_time_validation_evidence(
    frame: pl.DataFrame,
    *,
    declaration: AnalysisDeclaration,
    input_path: str,
    input_sha256: str,
    analysis_plan_path: str,
    analysis_plan_sha256: str,
    response: str,
    predictor: str,
    prediction_time: str,
    feature_available_at: str,
    target_available_at: str,
    config: WalkForwardConfig,
    covariance_type: CovarianceType = "HC3",
    software: SoftwareVersions | None = None,
) -> TimeValidationEvidence:
    validate_sha256("input_sha256", input_sha256)
    validate_sha256("analysis_plan_sha256", analysis_plan_sha256)
    result = validate_walk_forward(
        frame,
        response=response,
        predictor=predictor,
        prediction_time=prediction_time,
        feature_available_at=feature_available_at,
        target_available_at=target_available_at,
        config=config,
        covariance_type=covariance_type,
    )
    return TimeValidationEvidence(
        declaration=declaration,
        input_path=input_path,
        input_sha256=input_sha256,
        analysis_plan_path=analysis_plan_path,
        analysis_plan_sha256=analysis_plan_sha256,
        response=response,
        predictor=predictor,
        prediction_time=prediction_time,
        feature_available_at=feature_available_at,
        target_available_at=target_available_at,
        covariance_type=covariance_type,
        config=config,
        result=result,
        software=software or SoftwareVersions.current(),
    )
