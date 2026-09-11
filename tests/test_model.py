from datetime import UTC
from decimal import Decimal
from unittest import TestCase

from red_five.model import Observation, arithmetic_returns


class ModelTests(TestCase):
    def test_observation_normalizes_to_utc_without_float_loss(self) -> None:
        item = Observation.parse("2026-01-02T09:30:00-05:00", "ES", "5000.10", "points")
        self.assertEqual(item.timestamp.tzinfo, UTC)
        self.assertEqual(item.value, Decimal("5000.10"))

    def test_naive_timestamp_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "offset"):
            Observation.parse("2026-01-02T09:30:00", "ES", "5000", "points")

    def test_return_uses_decimal_arithmetic(self) -> None:
        self.assertEqual(
            arithmetic_returns([Decimal("100"), Decimal("101")]),
            [Decimal("0.01")],
        )
