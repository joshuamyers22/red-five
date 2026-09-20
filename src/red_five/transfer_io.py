"""Bounded snapshot adapter and versioned transfer evidence using shared publication."""

from __future__ import annotations

import math
from dataclasses import asdict, fields
from typing import cast

import numpy as np

from .contracts import ContractError, identifier, timestamp
from .reporting import canonical
from .signal_io import MAX_BYTES, digest, json_object
from .transfer import (
    MAX_ASSETS,
    AlignmentInput,
    AlignmentPolicy,
    AlignmentResult,
    TransferError,
    calculate_alignment,
)

SCHEMA = "red-five-transfer-report/v1"
WARNINGS = [
    "Forecast-model conditional alignment; not the paper's true-alpha coefficient.",
    "Offline research only; no live allocation or promotion decision is authorized.",
    "Hash verification does not certify source truth or financial correctness.",
]


def _object(value: object, keys: set[str]) -> dict[str, object]:
    if not isinstance(value, dict) or set(cast(dict[str, object], value)) != keys:
        raise TransferError("TRANSFER_INVALID_SCHEMA")
    return cast(dict[str, object], value)


def _number(value: object) -> float:
    if type(value) not in (float, int):
        raise TransferError("TRANSFER_NONFINITE_INPUT")
    try:
        result = float(cast(float, value))
    except OverflowError as error:
        raise TransferError("TRANSFER_NONFINITE_INPUT") from error
    if not math.isfinite(result):
        raise TransferError("TRANSFER_NONFINITE_INPUT")
    return result


def _vector(value: object) -> tuple[float, ...]:
    if (
        not isinstance(value, list)
        or not 1 <= len(cast(list[object], value)) <= MAX_ASSETS
    ):
        raise TransferError("TRANSFER_INVALID_DIMENSIONS")
    return tuple(_number(x) for x in cast(list[object], value))


def _ids(value: object) -> tuple[str, ...]:
    if (
        not isinstance(value, list)
        or not 1 <= len(cast(list[object], value)) <= MAX_ASSETS
    ):
        raise TransferError("TRANSFER_INVALID_DIMENSIONS")
    return tuple(identifier(x, "asset_id") for x in cast(list[object], value))


def evaluate_alignment(
    forecast_bytes: bytes,
    covariance_bytes: bytes,
    config_bytes: bytes,
    plan_bytes: bytes,
    lock_bytes: bytes,
    *,
    code_identity: dict[str, str],
    software: dict[str, str],
) -> dict[str, object]:
    """One snapshot; all times, units and asset order are supplied explicitly."""
    try:
        return _evaluate(
            forecast_bytes,
            covariance_bytes,
            config_bytes,
            plan_bytes,
            lock_bytes,
            code_identity=code_identity,
            software=software,
        )
    except TransferError:
        raise
    except (ContractError, ValueError, TypeError, OverflowError) as error:
        raise TransferError("TRANSFER_INVALID_SCHEMA") from error


def _evaluate(
    forecast_bytes: bytes,
    covariance_bytes: bytes,
    config_bytes: bytes,
    plan_bytes: bytes,
    lock_bytes: bytes,
    *,
    code_identity: dict[str, str],
    software: dict[str, str],
) -> dict[str, object]:
    inputs = dict(
        zip(
            ("forecast", "covariance", "config", "analysis_plan", "lock"),
            (forecast_bytes, covariance_bytes, config_bytes, plan_bytes, lock_bytes),
            strict=True,
        )
    )
    if any(not x.strip() or len(x) > MAX_BYTES for x in inputs.values()):
        raise TransferError("TRANSFER_INPUT_SIZE")
    common = {"schema_version", "as_of", "horizon", "risk_model_id", "asset_ids"}
    forecast = _object(
        json_object(forecast_bytes),
        common
        | {
            "snapshot_id",
            "forecast_model_id",
            "universe_id",
            "return_unit",
            "weight_unit",
            "expected_excess_returns",
            "implemented_weights",
        },
    )
    covariance = _object(
        json_object(covariance_bytes),
        common
        | {
            "covariance_unit",
            "matrix",
        },
    )
    config = _object(
        json_object(config_bytes),
        {
            "schema_version",
            "analysis_id",
            "enabled",
            "evaluated_at_utc",
            "max_condition_number",
            "symmetry_relative_tolerance",
            "bound_tolerance",
            "diagonal_diagnostic",
        },
    )
    if (
        forecast["schema_version"] != "red-five-transfer-forecast/v1"
        or covariance["schema_version"] != "red-five-transfer-covariance/v1"
        or config["schema_version"] != "red-five-transfer-config/v1"
    ):
        raise TransferError("TRANSFER_INVALID_SCHEMA")
    if config["enabled"] is not True:
        raise TransferError("TRANSFER_DISABLED")
    evaluated = timestamp(config["evaluated_at_utc"], "evaluated_at_utc")
    forecast_time = timestamp(forecast["as_of"], "as_of")
    covariance_time = timestamp(covariance["as_of"], "as_of")
    if forecast_time != covariance_time or forecast_time > evaluated:
        raise TransferError("TRANSFER_AS_OF_MISMATCH")
    for key in ("horizon", "risk_model_id"):
        if identifier(forecast[key], key) != identifier(covariance[key], key):
            raise TransferError("TRANSFER_MODEL_OR_HORIZON_MISMATCH")
    if (
        forecast["return_unit"] != "simple_excess_return_fraction"
        or forecast["weight_unit"] != "fraction_of_nav"
        or covariance["covariance_unit"] != "simple_return_fraction_squared"
    ):
        raise TransferError("TRANSFER_UNIT_MISMATCH")
    metadata = {
        key: identifier(forecast[key], key)
        for key in (
            "snapshot_id",
            "forecast_model_id",
            "universe_id",
            "risk_model_id",
            "horizon",
        )
    }
    matrix = covariance["matrix"]
    if (
        not isinstance(matrix, list)
        or not 1 <= len(cast(list[object], matrix)) <= MAX_ASSETS
    ):
        raise TransferError("TRANSFER_INVALID_DIMENSIONS")
    snapshot = AlignmentInput(
        _ids(forecast["asset_ids"]),
        _ids(covariance["asset_ids"]),
        _vector(forecast["expected_excess_returns"]),
        _vector(forecast["implemented_weights"]),
        tuple(_vector(row) for row in cast(list[object], matrix)),
    )
    diagnostic = config["diagonal_diagnostic"]
    if type(diagnostic) is not bool:
        raise TransferError("TRANSFER_INVALID_CONFIG")
    policy = AlignmentPolicy(
        _number(config["max_condition_number"]),
        _number(config["symmetry_relative_tolerance"]),
        _number(config["bound_tolerance"]),
        diagnostic,
    )
    result = calculate_alignment(snapshot, policy)
    # NumPy build metadata is allowlisted: no private compiler/build paths.
    build = cast(dict[str, object], np.__config__.CONFIG.get("Build Dependencies", {}))
    blas = cast(dict[str, object], build.get("blas", {}))
    identity: dict[str, object] = {
        "analysis_id": identifier(config["analysis_id"], "analysis_id"),
        "input_sha256": {key: digest(value) for key, value in inputs.items()},
        "code": code_identity,
        "software": software,
        "blas": {key: str(blas.get(key, "unavailable")) for key in ("name", "version")},
        "evaluated_at_utc": evaluated.isoformat(),
        "config": config,
        "seed": None,
    }
    return {
        "schema_version": SCHEMA,
        "run_id": digest(canonical(identity)),
        "identity": identity,
        "status": "insufficient_evidence",
        "verdict": None,
        "live_eligible": False,
        "snapshot": {
            **metadata,
            "as_of": forecast_time.isoformat(),
            "asset_order": "exact_match_no_reordering",
            "matrix_sha256": digest(canonical(cast(list[object], matrix))),
        },
        "alignment": asdict(result),
        "paired_comparison": {
            "status": "unavailable",
            "reason_code": "NOT_IMPLEMENTED",
        },
        "interpretation": WARNINGS,
    }


def validate_transfer_report(report: dict[str, object]) -> None:
    """Validate schema and basic numerical identities, not original inputs/models."""
    try:
        _validate_report(report)
    except (ContractError, ValueError, TypeError, OverflowError) as error:
        raise TransferError("TRANSFER_INVALID_EVIDENCE") from error


def _validate_report(report: dict[str, object]) -> None:
    _object(
        report,
        {
            "schema_version",
            "run_id",
            "identity",
            "status",
            "verdict",
            "live_eligible",
            "snapshot",
            "alignment",
            "paired_comparison",
            "interpretation",
        },
    )
    if (
        report["schema_version"] != SCHEMA
        or report["status"] != "insufficient_evidence"
        or report["verdict"] is not None
        or report["live_eligible"] is not False
        or report["interpretation"] != WARNINGS
        or report["paired_comparison"]
        != {"status": "unavailable", "reason_code": "NOT_IMPLEMENTED"}
    ):
        raise TransferError("TRANSFER_INVALID_EVIDENCE")
    identity = _object(
        report["identity"],
        {
            "analysis_id",
            "input_sha256",
            "code",
            "software",
            "blas",
            "evaluated_at_utc",
            "config",
            "seed",
        },
    )
    hashes = _object(
        identity["input_sha256"],
        {
            "forecast",
            "covariance",
            "config",
            "analysis_plan",
            "lock",
        },
    )
    for value in hashes.values():
        if (
            not isinstance(value, str)
            or len(value) != 64
            or any(c not in "0123456789abcdef" for c in value)
        ):
            raise TransferError("TRANSFER_INVALID_EVIDENCE")
    evaluated = timestamp(identity["evaluated_at_utc"], "evaluated_at_utc")
    if identity["seed"] is not None:
        raise TransferError("TRANSFER_INVALID_EVIDENCE")
    config = _object(
        identity["config"],
        {
            "schema_version",
            "analysis_id",
            "enabled",
            "evaluated_at_utc",
            "max_condition_number",
            "symmetry_relative_tolerance",
            "bound_tolerance",
            "diagonal_diagnostic",
        },
    )
    if (
        config["schema_version"] != "red-five-transfer-config/v1"
        or config["enabled"] is not True
        or identity["analysis_id"] != identifier(config["analysis_id"], "analysis_id")
        or timestamp(config["evaluated_at_utc"], "evaluated_at_utc") != evaluated
        or type(config["diagonal_diagnostic"]) is not bool
    ):
        raise TransferError("TRANSFER_INVALID_EVIDENCE")
    policy = AlignmentPolicy(
        _number(config["max_condition_number"]),
        _number(config["symmetry_relative_tolerance"]),
        _number(config["bound_tolerance"]),
        config["diagonal_diagnostic"],
    )
    code = _object(identity["code"], {"package_version", "source_sha256"})
    identifier(code["package_version"], "package_version")
    revision = code["source_sha256"]
    if (
        not isinstance(revision, str)
        or len(revision) != 64
        or any(c not in "0123456789abcdef" for c in revision)
    ):
        raise TransferError("TRANSFER_INVALID_EVIDENCE")
    if not isinstance(identity["software"], dict):
        raise TransferError("TRANSFER_INVALID_EVIDENCE")
    for k, v in cast(dict[str, object], identity["software"]).items():
        identifier(k, "dependency")
        identifier(v, "version")
    for v in _object(identity["blas"], {"name", "version"}).values():
        identifier(v, "blas")
    snapshot = _object(
        report["snapshot"],
        {
            "snapshot_id",
            "forecast_model_id",
            "universe_id",
            "risk_model_id",
            "horizon",
            "as_of",
            "asset_order",
            "matrix_sha256",
        },
    )
    for k, v in snapshot.items():
        identifier(v, k)
    if (
        timestamp(snapshot["as_of"], "as_of") > evaluated
        or snapshot["asset_order"] != "exact_match_no_reordering"
    ):
        raise TransferError("TRANSFER_INVALID_EVIDENCE")
    matrix_hash = cast(str, snapshot["matrix_sha256"])
    if len(matrix_hash) != 64 or any(c not in "0123456789abcdef" for c in matrix_hash):
        raise TransferError("TRANSFER_INVALID_EVIDENCE")
    result = _object(report["alignment"], {f.name for f in fields(AlignmentResult)})
    n = result["asset_count"]
    if type(n) is not int or not 1 <= n <= MAX_ASSETS:
        raise TransferError("TRANSFER_INVALID_EVIDENCE")
    if _number(result["condition_number"]) < 1:
        raise TransferError("TRANSFER_INVALID_EVIDENCE")
    if _number(result["symmetry_relative_error"]) != 0:
        raise TransferError("TRANSFER_INVALID_EVIDENCE")
    numbers = (
        "ex_ante_transfer_alignment",
        "model_sharpe",
        "optimal_model_sharpe",
        "expected_return_dot_weight",
        "portfolio_risk",
    )
    diagnostics = (
        "risk_adjusted_alpha_mean",
        "risk_weight_mean",
        "pearson_diagnostic",
        "cosine_minus_pearson",
    )
    condition = _number(result["condition_number"])
    if result["status"] == "numerically_unreliable":
        if condition <= policy.max_condition_number:
            raise TransferError("TRANSFER_INVALID_EVIDENCE")
        if result["reason_code"] != "TRANSFER_COVARIANCE_ILL_CONDITIONED" or any(
            result[k] is not None for k in (*numbers, *diagnostics)
        ):
            raise TransferError("TRANSFER_INVALID_EVIDENCE")
    elif result["status"] == "computed" and result["reason_code"] is None:
        if condition > policy.max_condition_number:
            raise TransferError("TRANSFER_INVALID_EVIDENCE")
        value, model, optimal, numerator, risk = (_number(result[k]) for k in numbers)
        if not (-1 <= value <= 1 and optimal > 0 and risk > 0):
            raise TransferError("TRANSFER_INVALID_EVIDENCE")
        if not math.isclose(model, value * optimal, rel_tol=1e-12, abs_tol=1e-15):
            raise TransferError("TRANSFER_INVALID_EVIDENCE")
        if not math.isclose(numerator, model * risk, rel_tol=1e-12, abs_tol=1e-15):
            raise TransferError("TRANSFER_INVALID_EVIDENCE")
        for key in diagnostics:
            if result[key] is not None:
                _number(result[key])
        if policy.diagonal_diagnostic:
            _number(result["risk_adjusted_alpha_mean"])
            _number(result["risk_weight_mean"])
            pearson, difference = (
                result["pearson_diagnostic"],
                result["cosine_minus_pearson"],
            )
            if pearson is None:
                if difference is not None:
                    raise TransferError("TRANSFER_INVALID_EVIDENCE")
            elif not (
                -1 <= _number(pearson) <= 1
                and math.isclose(
                    _number(difference), value - _number(pearson), abs_tol=1e-12
                )
            ):
                raise TransferError("TRANSFER_INVALID_EVIDENCE")
        elif any(result[k] is not None for k in diagnostics):
            raise TransferError("TRANSFER_INVALID_EVIDENCE")
    else:
        raise TransferError("TRANSFER_INVALID_EVIDENCE")
