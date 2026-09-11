# Reproducibility

## Red Five initial slice

The `red-five eval` report binds exact signal, weight, configuration, analysis-plan
and lockfile bytes with SHA-256, plus package version, package-source digest and
observed Python/NumPy/Polars/Statsmodels versions. `as_of` is the explicit UTC
evaluation cutoff, not the wall-clock execution time. Machine paths are excluded.
The source digest works for installed wheels without a Git checkout. Preserve the
Git revision and executed command alongside an assessment when promoting it beyond
the synthetic development slice; the initial report does not capture that revision.
The supplied lockfile is hashed, not an attestation that the entire environment
matches it: install with `uv sync --frozen` and preserve that install evidence.

See [the input contract](docs/INPUT_CONTRACTS.md), [analysis plan](STATISTICAL_ANALYSIS_PLAN.md)
and [verification record](docs/INITIAL_VERIFICATION.md). The general production
requirements below remain gates, not claims that the initial slice satisfies them.

## Production requirements and retained template utilities

Every result must record the Git commit, locked environment, command and
parameters, input identifiers and SHA-256 hashes, UTC evaluation time, timezone
and calendar, units and precision, transformation version, and output hash.

Raw inputs are immutable. Corrections create a new version. Derived data must be
rebuildable from authorized inputs and committed code. Random procedures require
an explicit seed and documented generator. Benchmarks record hardware and data
shape. Reconciliation tests define tolerances and explain why they are safe.

Polars is the default tabular engine. Record its locked version and relevant
streaming/lazy execution settings with evidence. Do not cross a pandas boundary
implicitly; document required interoperability, conversion ownership, null and
dtype semantics, and memory cost in an ADR.

Statsmodels is the default statistical/regression engine. Record the exact model
class, formula or design matrix, intercept handling, missing-data policy,
covariance estimator, weights/clusters, random seed where applicable, diagnostics,
sample filters, and locked Statsmodels/NumPy versions with each result.

For simple OLS, use the generated regression-evidence command to record these
fields in a versioned, deterministic JSON contract. Pass the revision, UTC
evaluation time, sample-filter declaration, validation design, and leakage
controls explicitly. Retain the printed artifact hash beside the review or run
manifest. Do not use the command's diagnostics as automatic approval thresholds;
pre-specify fit-for-purpose thresholds and time-aware validation in the analysis
plan.

For temporal prediction, prefer the generated expanding-window command over a
random split. Preserve source order, record feature and target availability, use
only labels available strictly before each test window, and retain per-observation
out-of-sample predictions. Compare against a fold-local baseline. Treat upstream
availability metadata and point-in-time universe construction as separately
audited inputs; this template cannot prove their truth.

Publish reviewed tabular outputs through the versioned Parquet contract. Preserve
a portable source identifier and hash, code revision, UTC creation time, exact
schema and invariants, partition/sort/key definitions, writer versions, and file
hashes in the manifest. Verify before lazy scanning and never mutate a published
version. Checksums detect change; they do not authenticate the publisher.

Notebooks explore and communicate; production calculations live in typed modules
with regression tests. A notebook result is not release evidence by itself.
