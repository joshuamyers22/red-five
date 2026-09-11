"""Explicit Polars-to-Statsmodels regression boundary."""

from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
from typing import Literal, Protocol, cast

import numpy as np
import polars as pl
from numpy.typing import NDArray

CovarianceType = Literal["nonrobust", "HC3"]
FloatArray = NDArray[np.float64]


class _RegressionResults(Protocol):
    params: FloatArray
    bse: FloatArray
    pvalues: FloatArray
    rsquared: float
    rsquared_adj: float
    nobs: float
    resid: FloatArray
    condition_number: float

    def conf_int(self, *, alpha: float) -> FloatArray: ...

    def get_influence(self) -> _InfluenceResults: ...


class _InfluenceResults(Protocol):
    @property
    def cooks_distance(self) -> tuple[FloatArray, FloatArray]: ...


class _OlsModel(Protocol):
    def fit(self, *, cov_type: CovarianceType) -> _RegressionResults: ...


class _StatsmodelsApi(Protocol):
    def OLS(
        self,
        endog: FloatArray,
        exog: FloatArray,
        *,
        missing: Literal["raise"],
        hasconst: Literal[True],
    ) -> _OlsModel: ...


statsmodels = cast(_StatsmodelsApi, import_module("statsmodels.api"))


@dataclass(frozen=True, slots=True)
class Coefficient:
    name: str
    estimate: float
    standard_error: float
    confidence_interval_95: tuple[float, float]
    p_value: float


@dataclass(frozen=True, slots=True)
class OlsDiagnostics:
    adjusted_r_squared: float
    residual_root_mean_square: float
    durbin_watson: float
    condition_number: float
    maximum_cooks_distance: float


@dataclass(frozen=True, slots=True)
class OlsFit:
    intercept: float
    slope: float
    r_squared: float
    observations: int
    covariance_type: CovarianceType
    coefficients: tuple[Coefficient, Coefficient]
    diagnostics: OlsDiagnostics


def fit_simple_ols(
    frame: pl.DataFrame,
    *,
    response: str,
    predictor: str,
    covariance_type: CovarianceType = "HC3",
) -> OlsFit:
    """Fit an intercept and one slope after validating the modeling sample."""
    if response == predictor:
        raise ValueError("response and predictor must differ")
    missing_columns = {response, predictor} - set(frame.columns)
    if missing_columns:
        raise ValueError(f"missing regression columns: {sorted(missing_columns)}")

    try:
        sample = frame.select(
            pl.col(response).cast(pl.Float64, strict=True),
            pl.col(predictor).cast(pl.Float64, strict=True),
        )
    except pl.exceptions.PolarsError as error:
        raise ValueError("regression columns must be numeric") from error
    if sample.height < 3:
        raise ValueError("regression requires at least three observations")
    if any(count != 0 for count in sample.null_count().row(0)):
        raise ValueError("regression sample cannot contain nulls")

    y: FloatArray = np.asarray(sample.get_column(response).to_numpy(), dtype=np.float64)
    x: FloatArray = np.asarray(
        sample.get_column(predictor).to_numpy(), dtype=np.float64
    )
    if not np.isfinite(y).all() or not np.isfinite(x).all():
        raise ValueError("regression sample must contain only finite values")
    if all(float(value) == float(x[0]) for value in x[1:]):
        raise ValueError("predictor must vary")

    design: FloatArray = np.empty((x.size, 2), dtype=np.float64)
    design[:, 0] = 1.0
    design[:, 1] = x
    fitted = statsmodels.OLS(y, design, missing="raise", hasconst=True).fit(
        cov_type=covariance_type
    )
    parameters = np.asarray(fitted.params, dtype=np.float64)
    standard_errors = np.asarray(fitted.bse, dtype=np.float64)
    p_values = np.asarray(fitted.pvalues, dtype=np.float64)
    confidence_intervals = np.asarray(fitted.conf_int(alpha=0.05), dtype=np.float64)
    residuals = np.asarray(fitted.resid, dtype=np.float64)
    cooks_distance = np.asarray(
        fitted.get_influence().cooks_distance[0], dtype=np.float64
    )
    residual_values = [float(value) for value in residuals]
    squared_residual_sum = sum(value * value for value in residual_values)
    squared_residual_difference_sum = sum(
        (current - previous) ** 2
        for previous, current in zip(residual_values, residual_values[1:], strict=False)
    )
    durbin_watson = (
        squared_residual_difference_sum / squared_residual_sum
        if squared_residual_sum > 0.0
        else 0.0
    )
    coefficient_names = ("intercept", predictor)
    coefficients = tuple(
        Coefficient(
            name=name,
            estimate=float(parameters[index]),
            standard_error=float(standard_errors[index]),
            confidence_interval_95=(
                float(confidence_intervals[index, 0]),
                float(confidence_intervals[index, 1]),
            ),
            p_value=float(p_values[index]),
        )
        for index, name in enumerate(coefficient_names)
    )
    return OlsFit(
        intercept=float(parameters[0]),
        slope=float(parameters[1]),
        r_squared=float(fitted.rsquared),
        observations=int(fitted.nobs),
        covariance_type=covariance_type,
        coefficients=cast(tuple[Coefficient, Coefficient], coefficients),
        diagnostics=OlsDiagnostics(
            adjusted_r_squared=float(fitted.rsquared_adj),
            residual_root_mean_square=float(np.sqrt(squared_residual_sum / x.size)),
            durbin_watson=durbin_watson,
            condition_number=float(fitted.condition_number),
            maximum_cooks_distance=float(np.max(cooks_distance)),
        ),
    )
