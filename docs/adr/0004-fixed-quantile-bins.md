# ADR 0004 — Explicit fixed training-reference quantiles

Date: 2026-09-11. Status: implemented descriptive development policy; not a
production decision rule or owner-approved inferential study specification.

Use an explicit training cutoff and empirical inverse-CDF boundaries. Fit only
known pre-cutoff scores, never returns. Keep time-series instrument/contract
models separate. Cross-sectional mode fits historical panel scores per model and
reports evaluation dates separately; comparable within-model scores are an
upstream precondition. This bounded first slice deliberately implements frozen
reference bins, not per-date ranks or automated walk-forward folds.

Deduplicate boundaries, send equality to the lower bin, count tail extrapolation,
and make sparse/missing results explicit. Store fitting evidence and the declared
policy in a versioned immutable independent section. Reuse notebook composition,
plots and partial exports. Preserve v1 full reports without fabricating quantiles.

Consequences: changes in evaluation values cannot move fitted boundaries; a
single-instrument history works without a cross-section; contract rolls remain
separate histories. Unequal date coverage affects cross-sectional training-score
frequencies. Empty bins and reduced effective bin counts are expected. Spreads
are descriptive return differences, not externally weighted portfolio economics.
Inference, purging, trial ledgers and upstream leakage attestations remain open.
See [algorithm and limits](../QUANTILES.md) and [tests](../../tests/test_quantiles.py).
