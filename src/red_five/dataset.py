"""Versioned, integrity-checked Parquet dataset publication."""

from __future__ import annotations

import hashlib
import json
import platform
import re
import shutil
import tempfile
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from importlib.metadata import version
from pathlib import Path, PurePosixPath
from typing import Any, cast

import polars as pl

from .evidence import validate_sha256

MANIFEST_SCHEMA_VERSION = "quant-parquet-dataset-manifest/v1"
VERSION_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
PARTITION_VALUE_PATTERN = re.compile(r"^[A-Za-z0-9._-]+$")


class DatasetContractError(ValueError):
    """The frame or schema is incompatible with the declared contract."""


class DatasetIntegrityError(ValueError):
    """Published bytes do not match the dataset manifest."""


@dataclass(frozen=True, slots=True)
class DatasetContract:
    name: str
    schema_version: int
    schema: pl.Schema
    nullable_columns: frozenset[str]
    partition_columns: tuple[str, ...]
    primary_key: tuple[str, ...]
    sort_columns: tuple[str, ...]
    invariant_set: str

    def __post_init__(self) -> None:
        columns = set(self.schema.names())
        if not self.name.strip() or self.schema_version < 1 or not columns:
            raise DatasetContractError("dataset name, version, and schema are required")
        if len(self.partition_columns) != 1:
            raise DatasetContractError("the reference publisher requires one partition")
        referenced = (
            set(self.nullable_columns)
            | set(self.partition_columns)
            | set(self.primary_key)
            | set(self.sort_columns)
        )
        if missing := referenced - columns:
            raise DatasetContractError(
                f"contract references unknown columns: {missing}"
            )
        if not self.primary_key or not self.sort_columns:
            raise DatasetContractError("primary key and sort columns are required")
        if self.nullable_columns & (
            set(self.partition_columns) | set(self.primary_key)
        ):
            raise DatasetContractError(
                "partition and primary-key columns cannot be nullable"
            )
        if not self.invariant_set.strip():
            raise DatasetContractError("an invariant set is required")


@dataclass(frozen=True, slots=True)
class DatasetVerification:
    manifest_sha256: str
    files: int
    rows: int


def market_observation_contract() -> DatasetContract:
    return DatasetContract(
        name="market-observations",
        schema_version=1,
        schema=pl.Schema(
            {
                "event_date": pl.Date,
                "timestamp": pl.Datetime("us", "UTC"),
                "instrument": pl.String,
                "value": pl.Decimal(20, 8),
                "unit": pl.String,
            }
        ),
        nullable_columns=frozenset(),
        partition_columns=("event_date",),
        primary_key=("timestamp", "instrument"),
        sort_columns=("event_date", "timestamp", "instrument"),
        invariant_set="market-observation/v1",
    )


def assert_backward_compatible(
    previous: DatasetContract, current: DatasetContract
) -> None:
    """Allow only appended nullable columns under a new schema version."""
    if previous.name != current.name:
        raise DatasetContractError("dataset name cannot change")
    if current.schema_version <= previous.schema_version:
        raise DatasetContractError("schema version must increase")
    fixed = (
        ("partition columns", previous.partition_columns, current.partition_columns),
        ("primary key", previous.primary_key, current.primary_key),
        ("sort columns", previous.sort_columns, current.sort_columns),
        ("invariant set", (previous.invariant_set,), (current.invariant_set,)),
    )
    for label, old, new in fixed:
        if old != new:
            raise DatasetContractError(f"{label} cannot change compatibly")

    old_items = list(previous.schema.items())
    new_items = list(current.schema.items())
    if new_items[: len(old_items)] != old_items:
        raise DatasetContractError("existing columns, order, and dtypes cannot change")
    for name, _dtype in old_items:
        if (name in previous.nullable_columns) != (name in current.nullable_columns):
            raise DatasetContractError("existing column nullability cannot change")
    added = [name for name, _dtype in new_items[len(old_items) :]]
    if any(name not in current.nullable_columns for name in added):
        raise DatasetContractError("new compatible columns must be nullable")


def _contract_dict(contract: DatasetContract) -> dict[str, object]:
    return {
        "name": contract.name,
        "schema_version": contract.schema_version,
        "columns": [
            {
                "name": name,
                "dtype": str(dtype),
                "nullable": name in contract.nullable_columns,
            }
            for name, dtype in contract.schema.items()
        ],
        "partition_columns": list(contract.partition_columns),
        "primary_key": list(contract.primary_key),
        "sort_columns": list(contract.sort_columns),
        "invariant_set": contract.invariant_set,
    }


def _validate_frame(frame: pl.DataFrame, contract: DatasetContract) -> None:
    if frame.schema != contract.schema:
        raise DatasetContractError(
            f"schema mismatch: expected {contract.schema}, received {frame.schema}"
        )
    required = [
        name
        for name in contract.schema.names()
        if name not in contract.nullable_columns
    ]
    if any(value != 0 for value in frame.select(required).null_count().row(0)):
        raise DatasetContractError("non-nullable columns contain nulls")
    if frame.select(contract.primary_key).n_unique() != frame.height:
        raise DatasetContractError("primary key contains duplicates")
    if frame.height < 1:
        raise DatasetContractError("dataset cannot be empty")
    if contract.invariant_set == "market-observation/v1":
        inconsistent_dates = frame.filter(
            pl.col("event_date") != pl.col("timestamp").dt.date()
        ).height
        blank_text = frame.filter(
            (pl.col("instrument").str.strip_chars() == "")
            | (pl.col("unit").str.strip_chars() == "")
            | (pl.col("instrument") != pl.col("instrument").str.strip_chars())
            | (pl.col("unit") != pl.col("unit").str.strip_chars())
        ).height
        if inconsistent_dates:
            raise DatasetContractError("event_date must match the UTC timestamp date")
        if blank_text:
            raise DatasetContractError(
                "instrument and unit must be nonblank and trimmed"
            )


def _partition_text(value: object) -> str:
    text = value.isoformat() if isinstance(value, date) else str(value)
    if not PARTITION_VALUE_PATTERN.fullmatch(text):
        raise DatasetContractError(f"unsafe partition value: {text!r}")
    return text


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def publish_dataset(
    frame: pl.DataFrame,
    root: Path,
    *,
    contract: DatasetContract,
    dataset_version: str,
    source_id: str,
    source_sha256: str,
    code_revision: str,
    created_at_utc: datetime,
) -> Path:
    """Publish an immutable dataset directory with atomic visibility."""
    _validate_frame(frame, contract)
    validate_sha256("source_sha256", source_sha256)
    if not VERSION_PATTERN.fullmatch(dataset_version):
        raise DatasetContractError("dataset version contains unsafe characters")
    if not source_id.strip() or not code_revision.strip():
        raise DatasetContractError("source identifier and code revision are required")
    if created_at_utc.utcoffset() != timedelta(0):
        raise DatasetContractError("created_at_utc must use UTC")

    root.mkdir(parents=True, exist_ok=True)
    target = root / dataset_version
    if target.exists():
        raise FileExistsError(f"dataset version already exists: {target}")
    stage = Path(tempfile.mkdtemp(dir=root, prefix=".staging-"))
    try:
        ordered = frame.sort(contract.sort_columns)
        partition_column = contract.partition_columns[0]
        partition_values = (
            ordered.get_column(partition_column).unique().sort().to_list()
        )
        files: list[dict[str, object]] = []
        for value in partition_values:
            partition_text = _partition_text(value)
            relative = (
                Path(f"{partition_column}={partition_text}") / "part-00000.parquet"
            )
            destination = stage / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            partition = ordered.filter(pl.col(partition_column) == pl.lit(value))
            partition.write_parquet(
                destination,
                compression="zstd",
                statistics=True,
                row_group_size=100_000,
            )
            files.append(
                {
                    "path": relative.as_posix(),
                    "sha256": _sha256(destination),
                    "bytes": destination.stat().st_size,
                    "rows": partition.height,
                    "partition": {partition_column: partition_text},
                }
            )
        manifest = {
            "schema_version": MANIFEST_SCHEMA_VERSION,
            "dataset": {
                "name": contract.name,
                "version": dataset_version,
                "created_at_utc": created_at_utc.astimezone(UTC)
                .isoformat()
                .replace("+00:00", "Z"),
                "code_revision": code_revision,
                "source_id": source_id,
                "source_sha256": source_sha256,
                "rows": ordered.height,
            },
            "contract": _contract_dict(contract),
            "storage": {
                "format": "parquet",
                "writer": "polars-native",
                "compression": "zstd",
                "statistics": True,
                "row_group_size": 100_000,
                "partition_columns_in_files": True,
                "hive_partition_inference": False,
            },
            "software": {
                "python": platform.python_version(),
                "polars": version("polars"),
            },
            "files": files,
        }
        manifest_bytes = (
            json.dumps(manifest, allow_nan=False, indent=2, sort_keys=True) + "\n"
        ).encode()
        (stage / "manifest.json").write_bytes(manifest_bytes)
        manifest_digest = hashlib.sha256(manifest_bytes).hexdigest()
        (stage / "manifest.sha256").write_text(
            f"{manifest_digest}  manifest.json\n", encoding="ascii"
        )
        stage.replace(target)
        return target
    finally:
        if stage.exists():
            shutil.rmtree(stage)


def _load_manifest(dataset: Path) -> tuple[dict[str, Any], str]:
    try:
        manifest_bytes = (dataset / "manifest.json").read_bytes()
        expected_line = (dataset / "manifest.sha256").read_text(encoding="ascii")
        expected_digest, filename = expected_line.rstrip("\n").split("  ", 1)
        actual_digest = hashlib.sha256(manifest_bytes).hexdigest()
        validate_sha256("manifest SHA-256", expected_digest)
        if filename != "manifest.json" or expected_digest != actual_digest:
            raise DatasetIntegrityError("manifest digest does not match")
        parsed: object = json.loads(manifest_bytes)
        if not isinstance(parsed, dict):
            raise DatasetIntegrityError("manifest root must be an object")
        return cast(dict[str, Any], parsed), actual_digest
    except DatasetIntegrityError:
        raise
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as error:
        raise DatasetIntegrityError("manifest is missing or malformed") from error


def _safe_manifest_path(dataset: Path, relative_text: str) -> Path:
    relative = PurePosixPath(relative_text)
    if (
        relative.is_absolute()
        or ".." in relative.parts
        or relative.suffix != ".parquet"
    ):
        raise DatasetIntegrityError("manifest contains an unsafe Parquet path")
    path = dataset
    if path.is_symlink():
        raise DatasetIntegrityError("dataset paths cannot contain symbolic links")
    for part in relative.parts:
        path /= part
        if path.is_symlink():
            raise DatasetIntegrityError("dataset paths cannot contain symbolic links")
    return path


def verify_dataset(dataset: Path, *, contract: DatasetContract) -> DatasetVerification:
    """Verify the manifest, file set, hashes, schema, partitions, and invariants."""
    manifest, manifest_digest = _load_manifest(dataset)
    try:
        if manifest["schema_version"] != MANIFEST_SCHEMA_VERSION:
            raise DatasetIntegrityError("unsupported manifest schema")
        if manifest["contract"] != _contract_dict(contract):
            raise DatasetIntegrityError("manifest contract does not match")
        dataset_record = manifest["dataset"]
        if dataset_record["name"] != contract.name:
            raise DatasetIntegrityError("dataset name does not match")
        if dataset_record["version"] != dataset.name:
            raise DatasetIntegrityError("dataset version does not match its directory")
        validate_sha256("source_sha256", dataset_record["source_sha256"])
        created_at = datetime.fromisoformat(
            dataset_record["created_at_utc"].replace("Z", "+00:00")
        )
        if created_at.utcoffset() != timedelta(0):
            raise DatasetIntegrityError("dataset creation time must use UTC")
        if (
            not isinstance(dataset_record["code_revision"], str)
            or not dataset_record["code_revision"].strip()
        ):
            raise DatasetIntegrityError("dataset code revision is missing")
        if (
            not isinstance(dataset_record["source_id"], str)
            or not dataset_record["source_id"].strip()
        ):
            raise DatasetIntegrityError("dataset source identifier is missing")
        expected_storage = {
            "format": "parquet",
            "writer": "polars-native",
            "compression": "zstd",
            "statistics": True,
            "row_group_size": 100_000,
            "partition_columns_in_files": True,
            "hive_partition_inference": False,
        }
        if manifest["storage"] != expected_storage:
            raise DatasetIntegrityError("storage contract does not match")
        if (
            not isinstance(manifest["software"]["python"], str)
            or not manifest["software"]["python"]
            or not isinstance(manifest["software"]["polars"], str)
            or not manifest["software"]["polars"]
        ):
            raise DatasetIntegrityError("writer software identity is missing")
        raw_file_records: object = manifest["files"]
        if not isinstance(raw_file_records, list) or not raw_file_records:
            raise DatasetIntegrityError("manifest must contain files")
        unknown_records = cast(list[object], raw_file_records)
        if any(not isinstance(record, dict) for record in unknown_records):
            raise DatasetIntegrityError("manifest must contain files")
        file_records = cast(list[dict[str, Any]], raw_file_records)
        record_paths: list[str] = []
        for record in file_records:
            relative_text = record.get("path")
            if not isinstance(relative_text, str):
                raise DatasetIntegrityError("manifest file path must be text")
            record_paths.append(relative_text)
        if record_paths != sorted(record_paths):
            raise DatasetIntegrityError("manifest file records must be sorted")

        expected_files: set[Path] = set()
        frames: list[pl.DataFrame] = []
        partition_column = contract.partition_columns[0]
        total_rows = 0
        for record in file_records:
            relative_text = cast(str, record["path"])
            digest = record.get("sha256")
            byte_count = record.get("bytes")
            row_count = record.get("rows")
            partition_record = record.get("partition")
            if not isinstance(digest, str):
                raise DatasetIntegrityError("manifest file digest must be text")
            if (
                isinstance(byte_count, bool)
                or not isinstance(byte_count, int)
                or byte_count < 1
                or isinstance(row_count, bool)
                or not isinstance(row_count, int)
                or row_count < 1
                or not isinstance(partition_record, dict)
            ):
                raise DatasetIntegrityError("manifest file metadata is malformed")
            partition_record = cast(dict[str, Any], partition_record)
            partition_value = partition_record.get(partition_column)
            if not isinstance(partition_value, str):
                raise DatasetIntegrityError("manifest partition value must be text")
            validate_sha256("file SHA-256", digest)
            path = _safe_manifest_path(dataset, relative_text)
            if path in expected_files:
                raise DatasetIntegrityError("manifest contains duplicate file paths")
            expected_files.add(path)
            if not path.is_file() or path.stat().st_size != byte_count:
                raise DatasetIntegrityError(f"file size does not match: {path.name}")
            if _sha256(path) != digest:
                raise DatasetIntegrityError(f"file digest does not match: {path.name}")
            if pl.read_parquet_schema(path) != contract.schema:
                raise DatasetIntegrityError(f"file schema does not match: {path.name}")
            frame = pl.read_parquet(path)
            if frame.height != row_count:
                raise DatasetIntegrityError(
                    f"file row count does not match: {path.name}"
                )
            expected_relative = (
                Path(f"{partition_column}={partition_value}") / "part-00000.parquet"
            ).as_posix()
            if relative_text != expected_relative:
                raise DatasetIntegrityError("file path does not match its partition")
            actual_values = {
                _partition_text(value)
                for value in frame.get_column(partition_column).unique().to_list()
            }
            if actual_values != {partition_value}:
                raise DatasetIntegrityError(
                    f"partition data does not match: {path.name}"
                )
            if not frame.equals(frame.sort(contract.sort_columns)):
                raise DatasetIntegrityError(f"file rows are not sorted: {path.name}")
            frames.append(frame)
            total_rows += frame.height

        actual_files = set(dataset.rglob("*.parquet"))
        if actual_files != expected_files:
            raise DatasetIntegrityError("published Parquet file set does not match")
        allowed_files = expected_files | {
            dataset / "manifest.json",
            dataset / "manifest.sha256",
        }
        actual_regular_files = {path for path in dataset.rglob("*") if path.is_file()}
        if actual_regular_files != allowed_files:
            raise DatasetIntegrityError("dataset contains unmanifested files")
        combined = pl.concat(frames).sort(contract.sort_columns)
        _validate_frame(combined, contract)
        if total_rows != dataset_record["rows"]:
            raise DatasetIntegrityError("dataset row count does not match")
    except DatasetIntegrityError:
        raise
    except (KeyError, TypeError, ValueError, pl.exceptions.PolarsError) as error:
        raise DatasetIntegrityError(
            "manifest or dataset content is malformed"
        ) from error
    return DatasetVerification(
        manifest_sha256=manifest_digest,
        files=len(file_records),
        rows=total_rows,
    )


def scan_verified_dataset(dataset: Path, *, contract: DatasetContract) -> pl.LazyFrame:
    """Verify a dataset before returning an explicitly configured lazy scan."""
    verify_dataset(dataset, contract=contract)
    files = sorted(dataset.rglob("*.parquet"))
    return pl.scan_parquet(files, hive_partitioning=False, use_statistics=True)
