"""Deterministic, reviewable evidence for a simple Statsmodels analysis."""

from __future__ import annotations

import hashlib
import io
import json
import platform
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from importlib.metadata import version
from pathlib import Path
from typing import Protocol

import polars as pl

from .regression import CovarianceType, OlsFit, fit_simple_ols

SCHEMA_VERSION = "quant-regression-evidence/v1"


class JsonArtifact(Protocol):
    def to_json_bytes(self) -> bytes: ...


@dataclass(frozen=True, slots=True)
class SoftwareVersions:
    python: str
    numpy: str
    polars: str
    statsmodels: str

    @classmethod
    def current(cls) -> SoftwareVersions:
        return cls(
            python=platform.python_version(),
            numpy=version("numpy"),
            polars=version("polars"),
            statsmodels=version("statsmodels"),
        )


@dataclass(frozen=True, slots=True)
class AnalysisDeclaration:
    analysis_id: str
    code_revision: str
    evaluated_at_utc: datetime
    sample_filters: str
    validation_design: str
    leakage_controls: str

    def __post_init__(self) -> None:
        required = {
            "analysis_id": self.analysis_id,
            "code_revision": self.code_revision,
            "sample_filters": self.sample_filters,
            "validation_design": self.validation_design,
            "leakage_controls": self.leakage_controls,
        }
        missing = sorted(name for name, value in required.items() if not value.strip())
        if missing:
            raise ValueError(f"analysis declarations cannot be blank: {missing}")
        if self.evaluated_at_utc.utcoffset() != timedelta(0):
            raise ValueError("evaluation time must use UTC")


@dataclass(frozen=True, slots=True)
class RegressionEvidence:
    declaration: AnalysisDeclaration
    input_path: str
    input_sha256: str
    analysis_plan_path: str
    analysis_plan_sha256: str
    response: str
    predictor: str
    fit: OlsFit
    software: SoftwareVersions

    def as_dict(self) -> dict[str, object]:
        coefficients = [
            {
                "name": item.name,
                "estimate": item.estimate,
                "standard_error": item.standard_error,
                "confidence_interval_95": list(item.confidence_interval_95),
                "p_value": item.p_value,
            }
            for item in self.fit.coefficients
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
            },
            "specification": {
                "model": "statsmodels.api.OLS",
                "response": self.response,
                "ordered_design_matrix": ["intercept", self.predictor],
                "intercept": "explicit",
                "missing_data": "raise",
                "covariance_type": self.fit.covariance_type,
            },
            "results": {
                "observations": self.fit.observations,
                "r_squared": self.fit.r_squared,
                "adjusted_r_squared": self.fit.diagnostics.adjusted_r_squared,
                "coefficients": coefficients,
                "diagnostics": {
                    "residual_root_mean_square": (
                        self.fit.diagnostics.residual_root_mean_square
                    ),
                    "durbin_watson": self.fit.diagnostics.durbin_watson,
                    "condition_number": self.fit.diagnostics.condition_number,
                    "maximum_cooks_distance": (
                        self.fit.diagnostics.maximum_cooks_distance
                    ),
                },
            },
            "validation": {
                "design": self.declaration.validation_design,
                "leakage_controls": self.declaration.leakage_controls,
            },
            "software": {
                "python": self.software.python,
                "numpy": self.software.numpy,
                "polars": self.software.polars,
                "statsmodels": self.software.statsmodels,
            },
            "limitations": [
                "Diagnostics are indicators for review, not automatic model approval.",
                "The caller must verify identification, stability, and "
                "fit-for-purpose validation.",
            ],
        }

    def to_json_bytes(self) -> bytes:
        text = (
            json.dumps(self.as_dict(), allow_nan=False, indent=2, sort_keys=True) + "\n"
        )
        return text.encode("utf-8")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_regression_csv(path: Path) -> tuple[pl.DataFrame, str]:
    """Read all CSV fields as strings so model conversion remains explicit."""
    content = path.read_bytes()
    try:
        frame = pl.read_csv(
            io.BytesIO(content),
            infer_schema=False,
            try_parse_dates=False,
            ignore_errors=False,
        )
    except pl.exceptions.PolarsError as error:
        raise ValueError("invalid regression CSV input") from error
    return frame, hashlib.sha256(content).hexdigest()


def build_regression_evidence(
    frame: pl.DataFrame,
    *,
    declaration: AnalysisDeclaration,
    input_path: str,
    input_sha256: str,
    analysis_plan_path: str,
    analysis_plan_sha256: str,
    response: str,
    predictor: str,
    covariance_type: CovarianceType = "HC3",
    software: SoftwareVersions | None = None,
) -> RegressionEvidence:
    validate_sha256("input_sha256", input_sha256)
    validate_sha256("analysis_plan_sha256", analysis_plan_sha256)
    fit = fit_simple_ols(
        frame,
        response=response,
        predictor=predictor,
        covariance_type=covariance_type,
    )
    return RegressionEvidence(
        declaration=declaration,
        input_path=input_path,
        input_sha256=input_sha256,
        analysis_plan_path=analysis_plan_path,
        analysis_plan_sha256=analysis_plan_sha256,
        response=response,
        predictor=predictor,
        fit=fit,
        software=software or SoftwareVersions.current(),
    )


def validate_sha256(name: str, digest: str) -> None:
    if len(digest) != 64 or any(
        character not in "0123456789abcdef" for character in digest
    ):
        raise ValueError(f"{name} must be a lowercase SHA-256 digest")


def write_artifact(path: Path, artifact: JsonArtifact) -> str:
    """Atomically write a JSON artifact and return its SHA-256 digest."""
    content = artifact.to_json_bytes()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_name = ""
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as temporary:
            temporary.write(content)
            temporary.flush()
            temporary_name = temporary.name
        Path(temporary_name).replace(path)
    finally:
        if temporary_name:
            Path(temporary_name).unlink(missing_ok=True)
    return hashlib.sha256(content).hexdigest()


def write_evidence(path: Path, evidence: RegressionEvidence) -> str:
    """Atomically write regression evidence and return its SHA-256 digest."""
    return write_artifact(path, evidence)
