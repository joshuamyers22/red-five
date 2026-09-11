import hashlib
import json
import tempfile
from dataclasses import replace
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from unittest import TestCase

import polars as pl

from red_five.dataset import (
    DatasetContract,
    DatasetContractError,
    DatasetIntegrityError,
    assert_backward_compatible,
    market_observation_contract,
    publish_dataset,
    scan_verified_dataset,
    verify_dataset,
)


def market_frame() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "event_date": [date(2026, 1, 2), date(2026, 1, 1), date(2026, 1, 1)],
            "timestamp": [
                datetime(2026, 1, 2, 15, tzinfo=UTC),
                datetime(2026, 1, 1, 16, tzinfo=UTC),
                datetime(2026, 1, 1, 15, tzinfo=UTC),
            ],
            "instrument": ["ABC", "XYZ", "ABC"],
            "value": [
                Decimal("102.00000000"),
                Decimal("50.50000000"),
                Decimal("100.00000000"),
            ],
            "unit": ["USD", "USD", "USD"],
        },
        schema=market_observation_contract().schema,
    )


def publish(root: Path, frame: pl.DataFrame | None = None) -> Path:
    return publish_dataset(
        frame if frame is not None else market_frame(),
        root,
        contract=market_observation_contract(),
        dataset_version="2026-01-02.1",
        source_id="fixture/market-observations.csv",
        source_sha256="a" * 64,
        code_revision="0123456789abcdef",
        created_at_utc=datetime(2026, 1, 2, 18, tzinfo=UTC),
    )


class DatasetTests(TestCase):
    def test_publish_verify_and_lazy_scan(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            dataset = publish(Path(temporary))

            verified = verify_dataset(dataset, contract=market_observation_contract())
            collected = scan_verified_dataset(
                dataset, contract=market_observation_contract()
            ).collect()

            self.assertEqual(verified.files, 2)
            self.assertEqual(verified.rows, 3)
            self.assertEqual(collected.schema, market_observation_contract().schema)
            self.assertEqual(collected.height, 3)
            self.assertEqual(
                sorted(
                    path.relative_to(dataset).as_posix()
                    for path in dataset.rglob("*.parquet")
                ),
                [
                    "event_date=2026-01-01/part-00000.parquet",
                    "event_date=2026-01-02/part-00000.parquet",
                ],
            )

    def test_publication_is_deterministic_and_immutable(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = publish(root / "first")
            second = publish(root / "second")

            self.assertEqual(
                (first / "manifest.json").read_bytes(),
                (second / "manifest.json").read_bytes(),
            )
            with self.assertRaises(FileExistsError):
                publish(root / "first")

    def test_file_corruption_is_detected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            dataset = publish(Path(temporary))
            parquet = next(dataset.rglob("*.parquet"))
            content = parquet.read_bytes()
            parquet.write_bytes(bytes([content[0] ^ 1]) + content[1:])

            with self.assertRaisesRegex(DatasetIntegrityError, "digest"):
                verify_dataset(dataset, contract=market_observation_contract())

    def test_unmanifested_file_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            dataset = publish(Path(temporary))
            (dataset / "unexpected.txt").write_text("unexpected", encoding="utf-8")

            with self.assertRaisesRegex(DatasetIntegrityError, "unmanifested"):
                verify_dataset(dataset, contract=market_observation_contract())

    def test_schema_and_primary_key_drift_fail_closed(self) -> None:
        wrong_schema = market_frame().with_columns(pl.col("value").cast(pl.Float64))
        duplicate = pl.concat([market_frame(), market_frame().head(1)])
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with self.assertRaisesRegex(DatasetContractError, "schema mismatch"):
                publish(root / "schema", wrong_schema)
            with self.assertRaisesRegex(DatasetContractError, "duplicates"):
                publish(root / "duplicate", duplicate)

    def test_partition_must_match_utc_timestamp_date(self) -> None:
        frame = market_frame().with_columns(
            pl.lit(date(2026, 1, 3)).alias("event_date")
        )
        with (
            tempfile.TemporaryDirectory() as temporary,
            self.assertRaisesRegex(DatasetContractError, "UTC timestamp date"),
        ):
            publish(Path(temporary), frame)

    def test_only_appended_nullable_columns_are_backward_compatible(self) -> None:
        previous = market_observation_contract()
        compatible = DatasetContract(
            name=previous.name,
            schema_version=2,
            schema=pl.Schema([*previous.schema.items(), ("venue", pl.String)]),
            nullable_columns=frozenset({"venue"}),
            partition_columns=previous.partition_columns,
            primary_key=previous.primary_key,
            sort_columns=previous.sort_columns,
            invariant_set=previous.invariant_set,
        )
        incompatible = DatasetContract(
            name=previous.name,
            schema_version=2,
            schema=pl.Schema([*previous.schema.items(), ("venue", pl.String)]),
            nullable_columns=frozenset(),
            partition_columns=previous.partition_columns,
            primary_key=previous.primary_key,
            sort_columns=previous.sort_columns,
            invariant_set=previous.invariant_set,
        )

        assert_backward_compatible(previous, compatible)
        with self.assertRaisesRegex(DatasetContractError, "must be nullable"):
            assert_backward_compatible(previous, incompatible)

    def test_partition_and_key_columns_cannot_be_nullable(self) -> None:
        with self.assertRaisesRegex(DatasetContractError, "cannot be nullable"):
            replace(
                market_observation_contract(),
                nullable_columns=frozenset({"timestamp"}),
            )

    def test_manifest_path_traversal_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            dataset = publish(Path(temporary))
            manifest_path = dataset / "manifest.json"
            manifest = json.loads(manifest_path.read_bytes())
            manifest["files"][0]["path"] = "../outside.parquet"
            content = (
                json.dumps(manifest, allow_nan=False, indent=2, sort_keys=True) + "\n"
            ).encode()
            manifest_path.write_bytes(content)
            digest = hashlib.sha256(content).hexdigest()
            (dataset / "manifest.sha256").write_text(
                f"{digest}  manifest.json\n", encoding="ascii"
            )

            with self.assertRaisesRegex(DatasetIntegrityError, "unsafe"):
                verify_dataset(dataset, contract=market_observation_contract())
