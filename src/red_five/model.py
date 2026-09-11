"""Validated domain records and deterministic calculations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation


@dataclass(frozen=True, slots=True)
class Observation:
    timestamp: datetime
    instrument: str
    value: Decimal
    unit: str

    @classmethod
    def parse(
        cls, timestamp: str, instrument: str, value: str, unit: str
    ) -> Observation:
        try:
            parsed_time = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            parsed_value = Decimal(value)
        except (ValueError, InvalidOperation) as error:
            raise ValueError("invalid timestamp or decimal value") from error
        if parsed_time.tzinfo is None or parsed_time.utcoffset() is None:
            raise ValueError("timestamp must include an offset")
        if not parsed_value.is_finite():
            raise ValueError("value must be finite")
        if not instrument.strip() or not unit.strip():
            raise ValueError("instrument and unit are required")
        return cls(
            parsed_time.astimezone(UTC),
            instrument.strip(),
            parsed_value,
            unit.strip(),
        )


def arithmetic_returns(values: list[Decimal]) -> list[Decimal]:
    """Calculate adjacent simple returns, rejecting a zero denominator."""
    results: list[Decimal] = []
    for previous, current in zip(values, values[1:], strict=False):
        if previous == 0:
            raise ZeroDivisionError("return denominator must not be zero")
        results.append(current / previous - 1)
    return results
