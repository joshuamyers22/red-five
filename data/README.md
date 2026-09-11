# Data boundaries

Do not commit raw, private, client, account, credential, licensed, or restricted
market data. Store only small synthetic fixtures under `tests/fixtures`.

Each dataset needs an owner, source, license, schema version, as-of semantics,
timezone/calendar, units, adjustment policy, retention, and source hash.

`example.csv` is also the synthetic input for the Parquet publication example.
Published versions belong under ignored `data/processed/`, not in Git. Each
version must retain its manifest and checksum with the Parquet files.
