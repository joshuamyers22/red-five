# ADR 0005 — Supplied-signal fold audits and a local trial journal

Date: 2026-09-11. Status: implemented development slice, not production approval.

The inherited walk-forward utility fits OLS and therefore cannot serve as the
evaluation workflow for externally supplied models. Add explicit timestamp
folds that account for every row, conservatively purge unavailable/missing
training labels, and reuse standalone/coverage/quantile calculations on test
windows. Do not fit upstream models or infer out-of-sample provenance.

Keep notebook composition through immutable sections. Store fold policy, audit,
membership digest and retained test keys with section evidence; display fold
windows and unverified upstream provenance. The original fixed score-only
quantile API remains available; the fold path explicitly uses stricter training
eligibility. Neither path chooses uncertainty or a decision rule.

Use standard-library SQLite for a bounded local trial journal, distinct from
the future Postgres production registry. Register before computation and append
computed/unavailable/failed outcomes transactionally; preserve unfinished attempts
and reject reused IDs. Digest chains and request/result reconciliation provide
local integrity checks, not completeness, signed provenance or protected history.
No database server, dependency, remote infrastructure or new release policy.

Consequences: synthetic research can be inspected and reproduced in individual
notebook cells now. Final assessment locking, upstream training attestations,
dependence-aware inference, historical trial reconstruction, access controls and
production backup/restore remain future gates. See [contracts](../TEMPORAL_TRIALS.md)
and [verification](../TEMPORAL_VERIFICATION.md).
