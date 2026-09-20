"""Pure, model-conditional risk-space alignment. No fitting or allocation policy."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from .contracts import ContractError

MAX_ASSETS = 256


class TransferError(ContractError):
    """Stable, non-sensitive failure reason for transfer diagnostics."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class AlignmentPolicy:
    max_condition_number: float = 1e10
    symmetry_relative_tolerance: float = 1e-12
    bound_tolerance: float = 1e-12
    diagonal_diagnostic: bool = False

    def __post_init__(self) -> None:
        for value, low, high in (
            (self.max_condition_number, 1.0, 1e12),
            (self.symmetry_relative_tolerance, 0.0, 1e-10),
            (self.bound_tolerance, 0.0, 1e-10),
        ):
            if type(value) not in (int, float) or not math.isfinite(value):
                raise TransferError("TRANSFER_INVALID_CONFIG")
            if not low <= value <= high:
                raise TransferError("TRANSFER_INVALID_CONFIG")
        if type(self.diagonal_diagnostic) is not bool:
            raise TransferError("TRANSFER_INVALID_CONFIG")


@dataclass(frozen=True, slots=True)
class AlignmentInput:
    asset_ids: tuple[str, ...]
    covariance_asset_ids: tuple[str, ...]
    expected_excess_returns: tuple[float, ...]
    implemented_weights: tuple[float, ...]
    covariance: tuple[tuple[float, ...], ...]


@dataclass(frozen=True, slots=True)
class AlignmentResult:
    status: str
    reason_code: str | None
    ex_ante_transfer_alignment: float | None
    model_sharpe: float | None
    optimal_model_sharpe: float | None
    expected_return_dot_weight: float | None
    portfolio_risk: float | None
    condition_number: float
    symmetry_relative_error: float
    asset_count: int
    risk_adjusted_alpha_mean: float | None = None
    risk_weight_mean: float | None = None
    pearson_diagnostic: float | None = None
    cosine_minus_pearson: float | None = None


def calculate_alignment(
    snapshot: AlignmentInput, policy: AlignmentPolicy | None = None
) -> AlignmentResult:
    """Use Cholesky risk coordinates; never explicitly invert covariance.

    Covariance must be exactly symmetric for a successful calculation. The declared
    tolerance classifies material asymmetry; smaller nonzero asymmetry also fails
    (with a separate reason) rather than silently repairing or selecting a triangle.
    """
    policy = policy or AlignmentPolicy()
    ids = snapshot.asset_ids
    n = len(ids)
    if not 1 <= n <= MAX_ASSETS:
        raise TransferError("TRANSFER_INVALID_DIMENSIONS")
    if (
        any(type(x) is not str or not x.strip() for x in ids)
        or len(set(ids)) != n
        or ids != snapshot.covariance_asset_ids
    ):
        raise TransferError("TRANSFER_ASSET_SET_MISMATCH")
    if (
        len(snapshot.expected_excess_returns) != n
        or len(snapshot.implemented_weights) != n
        or len(snapshot.covariance) != n
        or any(len(row) != n for row in snapshot.covariance)
    ):
        raise TransferError("TRANSFER_INVALID_DIMENSIONS")
    values = (
        *snapshot.expected_excess_returns,
        *snapshot.implemented_weights,
        *(x for row in snapshot.covariance for x in row),
    )
    if any(type(x) not in (int, float) for x in values):
        raise TransferError("TRANSFER_NONFINITE_INPUT")
    try:
        alpha = np.array(snapshot.expected_excess_returns, dtype=np.float64)
        weights = np.array(snapshot.implemented_weights, dtype=np.float64)
        sigma = np.array(snapshot.covariance, dtype=np.float64)
    except (ValueError, OverflowError) as error:
        raise TransferError("TRANSFER_NONFINITE_INPUT") from error
    if not all(bool(np.isfinite(x).all()) for x in (alpha, weights, sigma)):
        raise TransferError("TRANSFER_NONFINITE_INPUT")
    scale = float(np.max(np.abs(sigma)))
    if scale == 0:
        raise TransferError("TRANSFER_COVARIANCE_NOT_PD")
    normalized = sigma / scale
    symmetry_error = float(np.max(np.abs(normalized - normalized.T)))
    if symmetry_error > policy.symmetry_relative_tolerance:
        raise TransferError("TRANSFER_COVARIANCE_ASYMMETRIC")
    if not np.array_equal(sigma, sigma.T):
        raise TransferError("TRANSFER_COVARIANCE_NOT_EXACTLY_SYMMETRIC")
    try:
        factor = np.linalg.cholesky(normalized)
        condition = float(np.linalg.cond(normalized))
    except np.linalg.LinAlgError as error:
        raise TransferError("TRANSFER_COVARIANCE_NOT_PD") from error
    if not math.isfinite(condition):
        raise TransferError("TRANSFER_COVARIANCE_ILL_CONDITIONED")
    if condition > policy.max_condition_number:
        return AlignmentResult(
            "numerically_unreliable",
            "TRANSFER_COVARIANCE_ILL_CONDITIONED",
            None,
            None,
            None,
            None,
            None,
            condition,
            symmetry_error,
            n,
        )
    alpha_scale = float(np.max(np.abs(alpha)))
    weight_scale = float(np.max(np.abs(weights)))
    if alpha_scale == 0:
        raise TransferError("TRANSFER_ZERO_ALPHA_NORM")
    if weight_scale == 0:
        raise TransferError("TRANSFER_ZERO_PORTFOLIO_RISK")
    # Normalize before solving to preserve alignment under very large/small scales.
    a = np.linalg.solve(factor, alpha / alpha_scale)
    b = factor.T @ (weights / weight_scale)
    a_norm, b_norm = float(np.linalg.norm(a)), float(np.linalg.norm(b))
    value = float((a / a_norm) @ (b / b_norm))
    if not math.isfinite(value) or abs(value) > 1 + policy.bound_tolerance:
        raise TransferError("TRANSFER_NUMERICAL_FAILURE")
    value = max(-1.0, min(1.0, value))
    optimal = a_norm * (alpha_scale / math.sqrt(scale))
    risk = b_norm * (weight_scale * math.sqrt(scale))
    model = value * optimal
    numerator = model * risk
    if not all(math.isfinite(x) for x in (optimal, risk, model, numerator)):
        raise TransferError("TRANSFER_NUMERICAL_FAILURE")
    if optimal <= 0 or risk <= 0:
        raise TransferError("TRANSFER_NUMERICAL_FAILURE")
    alpha_mean = weight_mean = pearson = difference = None
    if policy.diagonal_diagnostic:
        if np.count_nonzero(sigma - np.diag(np.diag(sigma))):
            raise TransferError("TRANSFER_DIAGNOSTIC_REQUIRES_DIAGONAL")
        alpha_mean = float(np.mean(a)) * (alpha_scale / math.sqrt(scale))
        weight_mean = float(np.mean(b)) * (weight_scale * math.sqrt(scale))
        ac, bc = a - np.mean(a), b - np.mean(b)
        an, bn = float(np.linalg.norm(ac)), float(np.linalg.norm(bc))
        if an > 0 and bn > 0:
            pearson = max(-1.0, min(1.0, float((ac / an) @ (bc / bn))))
            difference = value - pearson
    return AlignmentResult(
        "computed",
        None,
        value,
        model,
        optimal,
        numerator,
        risk,
        condition,
        symmetry_error,
        n,
        alpha_mean,
        weight_mean,
        pearson,
        difference,
    )
