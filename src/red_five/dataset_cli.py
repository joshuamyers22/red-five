"""Command-line publication and verification for the reference dataset."""

from __future__ import annotations

import argparse
import hashlib
import io
from datetime import datetime
from pathlib import Path

import polars as pl

from .dataset import market_observation_contract, publish_dataset, verify_dataset


def _load_market_csv(path: Path) -> tuple[pl.DataFrame, str]:
    content = path.read_bytes()
    try:
        raw = pl.read_csv(
            io.BytesIO(content),
            infer_schema=False,
            try_parse_dates=False,
            ignore_errors=False,
        )
        required = {"timestamp", "instrument", "value", "unit"}
        if set(raw.columns) != required or len(raw.columns) != len(required):
            raise ValueError(f"columns must be exactly {sorted(required)}")
        frame = (
            raw.with_columns(
                pl.col("timestamp")
                .str.to_datetime(strict=True, time_zone="UTC")
                .cast(pl.Datetime("us", "UTC")),
                pl.col("value").cast(pl.Decimal(20, 8), strict=True),
            )
            .with_columns(pl.col("timestamp").dt.date().alias("event_date"))
            .select("event_date", "timestamp", "instrument", "value", "unit")
        )
    except pl.exceptions.PolarsError as error:
        raise ValueError("invalid market-observation CSV") from error
    return frame, hashlib.sha256(content).hexdigest()


def _created_at(value: str, parser: argparse.ArgumentParser) -> datetime:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        parser.error(f"invalid --created-at-utc: {error}")


def main() -> int:
    parser = argparse.ArgumentParser(prog="red-five-dataset")
    subparsers = parser.add_subparsers(dest="command", required=True)
    publish = subparsers.add_parser("publish")
    publish.add_argument("input", type=Path)
    publish.add_argument("root", type=Path)
    publish.add_argument("--dataset-version", required=True)
    publish.add_argument("--source-id", required=True)
    publish.add_argument("--revision", required=True)
    publish.add_argument("--created-at-utc", required=True)
    verify = subparsers.add_parser("verify")
    verify.add_argument("dataset", type=Path)
    args = parser.parse_args()
    contract = market_observation_contract()

    if args.command == "publish":
        frame, source_digest = _load_market_csv(args.input)
        destination = publish_dataset(
            frame,
            args.root,
            contract=contract,
            dataset_version=args.dataset_version,
            source_id=args.source_id,
            source_sha256=source_digest,
            code_revision=args.revision,
            created_at_utc=_created_at(args.created_at_utc, parser),
        )
        verified = verify_dataset(destination, contract=contract)
        print(
            f"dataset={destination} rows={verified.rows} files={verified.files} "
            f"manifest_sha256={verified.manifest_sha256}"
        )
        return 0

    verified = verify_dataset(args.dataset, contract=contract)
    print(
        f"dataset={args.dataset} rows={verified.rows} files={verified.files} "
        f"manifest_sha256={verified.manifest_sha256}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
