import tempfile
from pathlib import Path
from unittest import TestCase

from red_five.ingest import load_csv


class IngestTests(TestCase):
    def test_load_records_provenance(self) -> None:
        content = (
            "timestamp,instrument,value,unit\n2026-01-02T14:30:00Z,ES,5000.1,points\n"
        )
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "input.csv"
            path.write_text(content, encoding="utf-8")
            dataset = load_csv(path)
        self.assertEqual(len(dataset.observations), 1)
        self.assertEqual(len(dataset.source_sha256), 64)

    def test_schema_drift_is_rejected(self) -> None:
        with (
            tempfile.TemporaryDirectory() as temporary,
            self.assertRaisesRegex(ValueError, "columns"),
        ):
            path = Path(temporary) / "input.csv"
            path.write_text("time,ticker,price\nnow,ES,1\n", encoding="utf-8")
            load_csv(path)

    def test_polars_inference_cannot_coerce_decimal_source_text(self) -> None:
        content = (
            "timestamp,instrument,value,unit\n2026-01-02T14:30:00Z,ES,5000.10,points\n"
        )
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "input.csv"
            path.write_text(content, encoding="utf-8")
            dataset = load_csv(path)

        self.assertEqual(str(dataset.observations[0].value), "5000.10")

    def test_null_required_field_is_rejected(self) -> None:
        content = "timestamp,instrument,value,unit\n2026-01-02T14:30:00Z,ES,,points\n"
        with (
            tempfile.TemporaryDirectory() as temporary,
            self.assertRaisesRegex(ValueError, "cannot be null"),
        ):
            path = Path(temporary) / "input.csv"
            path.write_text(content, encoding="utf-8")
            load_csv(path)
