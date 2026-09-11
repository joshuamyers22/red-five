# Quantile slice verification

Scope: descriptive fixed-training-reference bins, per-contract time-series models
and per-date cross-sectional views, explicit counts/means/spreads/monotonicity,
notebook composition and partial export. No learned weights or inference policy.

Blocking invariants: evaluation scores/labels cannot move training boundaries;
training returns are not used to fit bins; models/contracts remain separate;
ties, sparse/empty bins, unavailable/immature labels and numerical failures are
explicit; notebook/exports use exactly the stored results. Verify adversarial and
hand-worked fixtures, compatibility, strict quality gates, actual kernel execution
and an installed-wheel smoke test. Three evidence-changing passes / two hours;
synthetic data only, no deployment or consequential financial approval.

## Executed evidence — 2026-09-11

- `make check`: Ruff lint/format and strict Pyright passed; 163 tests passed,
  92.37% package coverage (unchanged 85% floor). The quantile module has 96%
  statement coverage. No typing or coverage policy was relaxed.
- Hand-worked training cuts `[1, 3, 5]` produce bin means `[.01, .02, .03, .04]`
  and spread `.03`. Thirty-two quantile tests cover future-score/all-label
  perturbation invariance, input-order invariance, cutoff equality, independent
  model scales, cross-sectional grouping, ties and tail extrapolation, constant
  or short training, one effective bin, sparse/missing/immature labels, no-test
  samples, finite extreme returns, monotonicity, and invalid policies.
- Section integration checks cover calculation isolation, immutable metadata,
  schema compatibility/rejection, unavailable plots without zero imputation,
  exact bar-height/table parity, partial export verification, and rejection of
  unsupported quantile extraction from a full v1 report.
- All three notebooks executed in real local Jupyter kernels. Tracked notebooks
  have no outputs; executed copies and synthetic bundles stay in ignored `build/`.
  Inspected the quantile mean-return PNG: bin identities, target units, selection
  count, partial scope and no-verdict caption remain visible.
- `make audit build`: no known vulnerabilities/adverse statuses in 111 non-dev
  packages; license policy passed; wheel and source distribution built. No new
  dependency or lockfile change. The audit required approved network access
  after sandbox DNS failure.
- Installed the built wheel into `build/report-wheel-smoke` and ran
  `tools/smoke_sections.py` from `/private/tmp`, outside the checkout. Independent
  standalone/quantile evaluation, model selection, mean/count plots and partial
  bundle verification passed. CI uses this extended smoke and `make notebook-check`.

The three verification perspectives were hand-worked/adversarial calculations,
composition and schema boundaries, then quality/build/kernel/installed-package
execution. Review found that bin-number matches alone were insufficient for safe
overlays: quantile overlays now require matching bounds. The initial overlay test
cutoff happened to preserve the empirical cuts; the corrected fixture explicitly
asserts changed cuts before asserting rejection. Partial manifests now reject
metrics incompatible with the plotted kind and missing companion-table metrics.
Type checks caught a test constant reassignment and a mis-typed test identity;
the regression suite caught a stale assertion after clarifying the full-report
unavailable message. These were corrected before the final gate passed.

## Remaining limits

Fixed reference bins are not per-date equal-count quantiles or purged walk-forward
validation. Within-model cross-sectional score comparability is an upstream
precondition; training panel observations, not dates, have equal influence on
cuts. No roll stitching, inferred effective breadth, confidence intervals,
trial ledger, multiplicity choice or consequential approval is implemented.
Spreads repeat by bin in tidy output and are not portfolio returns. The notebook
demonstrates displaying group summaries once, without summing them. Existing
200-row/20-row-page rendering limits and trusted-local-kernel restrictions remain.

Jupyter warns that loopback kernel TCP is unencrypted; no public/shared server was
started. These checks are synthetic software evidence, not a financial validation.
The prior pushed baseline `c56a955` passed [GitHub CI](https://github.com/joshuamyers22/red-five/actions/runs/34657506087).
The quantile changes are local and have not yet run remotely or been deployed.
