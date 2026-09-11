# Parquet Dataset Contract

`red-five-dataset` publishes the reference market-observation CSV as an
immutable, date-partitioned Parquet dataset. The implementation uses Polars'
native stable single-file writer inside deterministic partition directories. It
does not use `PartitionBy` or inferred Hive schemas because those APIs are marked
unstable by Polars.

## Published layout

```text
<root>/<dataset-version>/
├── event_date=YYYY-MM-DD/part-00000.parquet
├── manifest.json
└── manifest.sha256
```

The contract requires exact ordered columns and dtypes: UTC microsecond
timestamps, an explicit event date, string instrument and unit, and
`Decimal(20, 8)` values. Partition, primary-key, sort, nullability, and
market-observation invariants are code, not prose. Publication sorts canonically,
writes Zstandard-compressed files with statistics, writes the manifest last, and
renames a same-filesystem staging directory into place. Existing versions are
never overwritten.

The manifest records its schema version, dataset and contract versions, portable
source identifier and hash, code revision, UTC creation time, writer versions,
storage settings, row count, and every file's relative path, partition, size,
row count, and SHA-256 hash. `manifest.sha256` protects the manifest itself.

## Verification and reads

Verification fails closed on malformed manifests, checksum or file-set drift,
unsafe or symbolic-link paths, unknown files, schema changes, duplicate primary
keys, null violations, partition/data disagreement, date/timestamp disagreement,
or noncanonical row order. Only after verification does
`scan_verified_dataset` return a lazy Polars scan. Hive inference is explicitly
disabled because partition columns remain inside every file.

```sh
uv run red-five-dataset publish data/example.csv data/processed \
  --dataset-version 2026-01-02.1 \
  --source-id fixture/example.csv \
  --revision "$(git rev-parse HEAD)" \
  --created-at-utc "$(date -u +%Y-%m-%dT%H:%M:%SZ)"

uv run red-five-dataset verify data/processed/2026-01-02.1
```

## Compatibility and trust boundaries

`assert_backward_compatible` permits only a higher schema version with existing
columns, order, dtypes, nullability, partitions, keys, sorting, and invariants
unchanged. New fields must be nullable and appended. This is a conservative
release check; consumers still need an explicit mixed-version read/migration
policy before schemas coexist.

SHA-256 detects accidental or uncoordinated change but does not authenticate a
publisher: an attacker able to replace the dataset can replace its checksums.
Use access controls, object retention/versioning, and signed provenance where the
threat model requires them. Directory rename gives atomic visibility on one local
filesystem, not crash durability, distributed object-store transactions, or
automatic cleanup after process termination. The verifier confirms declared
writer settings, but it does not inspect every Parquet page's physical encoding.

Dataset manifests may expose sensitive identifiers, values, and lineage. Apply
the project's classification, authorization, encryption, retention, deletion,
and backup policy. Never commit client, account, credential, or restricted market
data.

## Polars references

- [Parquet writer](https://docs.pola.rs/api/python/stable/reference/api/polars.DataFrame.write_parquet.html)
- [Lazy Parquet scan](https://docs.pola.rs/api/python/stable/reference/api/polars.scan_parquet.html)
- [Parquet schema reader](https://docs.pola.rs/api/python/stable/reference/api/polars.read_parquet_schema.html)
- [Hive partitioning](https://docs.pola.rs/user-guide/io/hive/)
