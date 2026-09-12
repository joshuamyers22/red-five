# ADR 0006 — Explicit conditional moving-block intervals

Date: 2026-09-11. Status: implemented development slice; not a consequential
inference/selection policy or production approval.

Use an explicitly configured moving-block percentile estimator for paired
time-series Pearson/Spearman correlations and equal-date mean cross-sectional
IC. Require a regular elapsed-time grid, complete usable time points, bounded
work, mechanical history/block floors and finite nondegenerate replicates.
Do not infer block length, impute missing time points, select a sign, or drop
undefined replicates. Preserve existing correlation semantics inside resamples.

Publish schema-v3 immutable uncertainty sections through existing notebook,
fold and trial APIs. Bind policy to evidence, label intervals conditional/not
selection-adjusted, and keep charts' point estimates and bounds together. No new
dependency; NumPy resamples existing production statistics. Keep the template
regression fitter outside supplied-signal evaluation.

Consequences: per-contract uncertainty and per-date CS mean uncertainty become
independently inspectable now. Regular-grid restrictions intentionally exclude
unsupported calendar/missingness cases. Noncircular edge weighting, finite-sample
coverage, dependence beyond blocks and upstream leakage remain limitations.
Do not generalize the small null simulation test to real-data calibration.

Actual holdout/family/access decisions remain open in FINAL_ASSESSMENT.md; no
enforced final-assessment lock or multiple-testing correction is claimed. See
[method/primary references](../UNCERTAINTY.md) and [verification](../UNCERTAINTY_VERIFICATION.md).
