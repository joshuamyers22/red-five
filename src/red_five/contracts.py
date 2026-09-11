"""Owned input contracts; upstream models and weights are never fitted here."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Literal, cast

Mode = Literal["time_series", "cross_sectional"]


class ContractError(ValueError):
    """Input cannot be interpreted under the declared evaluation contract."""


def identifier(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > 256:
        raise ContractError(f"{field} must be a nonblank string of at most 256 chars")
    if value != value.strip() or any(ord(char) < 32 for char in value):
        raise ContractError(f"{field} contains whitespace or control characters")
    return value


def timestamp(value: object, field: str) -> datetime:
    text = identifier(value, field)
    try:
        result = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as error:
        raise ContractError(f"{field} must be an ISO timestamp") from error
    if result.utcoffset() is None:
        raise ContractError(f"{field} must include a timezone offset")
    return result.astimezone(UTC)


def finite_float(value: object, field: str) -> float:
    try:
        result = float(identifier(value, field))
    except ValueError as error:
        raise ContractError(f"{field} must be finite numeric text") from error
    if not math.isfinite(result):
        raise ContractError(f"{field} must be finite numeric text")
    return result


def decimal(value: object, field: str) -> Decimal:
    try:
        result = Decimal(identifier(value, field))
    except InvalidOperation as error:
        raise ContractError(f"{field} must be decimal text") from error
    if not result.is_finite() or abs(result) > Decimal("1e12"):
        raise ContractError(f"{field} must be finite and within +/-1e12")
    if cast(int, result.as_tuple().exponent) < -18:
        raise ContractError(f"{field} supports at most 18 decimal places")
    return result


@dataclass(frozen=True, slots=True)
class EvaluationConfig:
    study_id: str
    mode: Mode
    as_of: datetime
    signal_version: str
    return_kind: str
    return_model_id: str
    horizon: str
    calendar: str
    minimum_observations: int
    weighting_policy_id: str | None

    @classmethod
    def parse(cls, data: dict[str, object]) -> EvaluationConfig:
        fields = {
            "schema_version",
            "study_id",
            "mode",
            "as_of",
            "signal_version",
            "return_kind",
            "return_model_id",
            "horizon",
            "calendar",
            "minimum_observations",
            "weighting_policy_id",
        }
        if set(data) != fields or data["schema_version"] != "red-five-config/v1":
            raise ContractError("config schema or fields do not match v1")
        mode = data["mode"]
        if mode not in ("time_series", "cross_sectional"):
            raise ContractError("mode must be time_series or cross_sectional")
        kind = data["return_kind"]
        if kind not in ("residual", "total"):
            raise ContractError("return_kind must be residual or total")
        minimum = data["minimum_observations"]
        if type(minimum) is not int or not 3 <= minimum <= 100_000:
            raise ContractError(
                "minimum_observations must be an integer in [3, 100000]"
            )
        policy = data["weighting_policy_id"]
        return cls(
            study_id=identifier(data["study_id"], "study_id"),
            mode=mode,
            as_of=timestamp(data["as_of"], "as_of"),
            signal_version=identifier(data["signal_version"], "signal_version"),
            return_kind=cast(str, kind),
            return_model_id=identifier(data["return_model_id"], "return_model_id"),
            horizon=identifier(data["horizon"], "horizon"),
            calendar=identifier(data["calendar"], "calendar"),
            minimum_observations=minimum,
            weighting_policy_id=None
            if policy is None
            else identifier(policy, "policy"),
        )


@dataclass(frozen=True, slots=True)
class Prediction:
    model_id: str
    instrument_id: str
    contract_id: str
    decision_time: datetime
    signal_available_at: datetime
    label_start: datetime
    label_end: datetime
    label_available_at: datetime
    signal: float
    forward_return: float | None

    @classmethod
    def parse(cls, row: dict[str, object], config: EvaluationConfig) -> Prediction:
        times = [
            timestamp(row[key], key)
            for key in (
                "decision_time",
                "signal_available_at",
                "label_start",
                "label_end",
                "label_available_at",
            )
        ]
        decision, available, start, end, label_available = times
        if available > decision:
            raise ContractError("signal is unavailable at decision_time")
        if not decision <= start < end <= label_available:
            raise ContractError(
                "label timing must satisfy decision <= start < end <= availability"
            )
        if decision > config.as_of:
            raise ContractError("decision_time exceeds evaluation cutoff")
        raw_return = row["forward_return"]
        return cls(
            identifier(row["model_id"], "model_id"),
            identifier(row["instrument_id"], "instrument_id"),
            identifier(row["contract_id"], "contract_id"),
            decision,
            available,
            start,
            end,
            label_available,
            finite_float(row["signal"], "signal"),
            None if raw_return is None else finite_float(raw_return, "forward_return"),
        )


@dataclass(frozen=True, slots=True)
class WeightObservation:
    portfolio_id: str
    instrument_id: str
    contract_id: str
    decision_time: datetime
    weights_available_at: datetime
    label_start: datetime
    label_end: datetime
    label_available_at: datetime
    pre_trade_weight: Decimal
    target_weight: Decimal
    asset_total_return: Decimal
    trade_cost_bps: Decimal
    holding_cost_nav_bps: Decimal

    @classmethod
    def parse(
        cls, row: dict[str, object], config: EvaluationConfig
    ) -> WeightObservation:
        if config.weighting_policy_id is None:
            raise ContractError("supplied weights require weighting_policy_id")
        times = [
            timestamp(row[key], key)
            for key in (
                "decision_time",
                "weights_available_at",
                "label_start",
                "label_end",
                "label_available_at",
            )
        ]
        decision, available, start, end, label_available = times
        if available > decision or not decision <= start < end <= label_available:
            raise ContractError("weights or return interval have invalid availability")
        if label_available > config.as_of:
            raise ContractError("weight ledger contains immature returns")
        numbers = [
            decimal(row[key], key)
            for key in (
                "pre_trade_weight",
                "target_weight",
                "asset_total_return",
                "trade_cost_bps",
                "holding_cost_nav_bps",
            )
        ]
        if numbers[3] < 0 or numbers[4] < 0:
            raise ContractError("costs must be nonnegative")
        return cls(
            identifier(row["portfolio_id"], "portfolio_id"),
            identifier(row["instrument_id"], "instrument_id"),
            identifier(row["contract_id"], "contract_id"),
            decision,
            available,
            start,
            end,
            label_available,
            numbers[0],
            numbers[1],
            numbers[2],
            numbers[3],
            numbers[4],
        )
