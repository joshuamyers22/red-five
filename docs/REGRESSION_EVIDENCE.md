# Regression Evidence Contract

`red-five-regression` is a narrow reference path for an intercept plus one
predictor using `statsmodels.api.OLS`. It exists to demonstrate the minimum
provenance and uncertainty expected from an inference artifact, not to prescribe
simple OLS for every quantitative problem.

## Contract

The versioned JSON records:

- the analysis identifier, exact UTC evaluation time, code revision, and hashed
  statistical-analysis plan;
- the input path and SHA-256 hash plus the declared sample filters;
- response, ordered design matrix, explicit intercept, fail-closed missing-data
  policy, and covariance estimator;
- coefficient estimates, robust standard errors, 95% confidence intervals,
  p-values, R-squared, adjusted R-squared, and observation count;
- residual root mean square, Durbin-Watson, design condition number, and maximum
  Cook's distance;
- Python, NumPy, Polars, and Statsmodels versions; and
- explicit validation-design and leakage-control declarations.

Serialization sorts keys, prohibits non-finite JSON values, ends with one newline,
and is covered by deterministic and numerical drift tests. Output is replaced
atomically and its SHA-256 digest is printed after the write.

## Review boundaries

No diagnostic is a universal pass/fail rule. The analysis plan must define the
estimand, identification assumptions, dependence structure, covariance choice,
multiple-testing treatment, economic threshold, and validation criteria before
the result is known. For temporal predictions, use point-in-time features and an
ordered holdout or rolling evaluation; a declaration of “in-sample only” is an
explicit limitation, not validation.

Extend or replace this schema for multiple predictors, fixed effects, clustered
or HAC covariance, GLMs, time-series models, cross-validation, forecasts, or live
model monitoring. Increment `schema_version` when a consumer-facing field or
meaning changes.

## Time-aware validation contract

`red-five-validate` emits `quant-time-validation-evidence/v1` for a
non-overlapping expanding-window evaluation. Input rows must already be in unique,
strict prediction-time order. Each row names when its feature and target became
available. The command rejects a feature timestamp after prediction and a target
timestamp at or before prediction.

Before each test window, training candidates whose targets were not available
strictly before the test start are purged. The strict inequality is intentional:
when availability and prediction timestamps tie, event order is unknown. Each
fold records its training, purged, and test counts, fitted coefficients, individual
out-of-sample predictions, and model-versus-training-mean error metrics. Aggregate
relative mean-square skill is `1 - model SSE / baseline SSE`; it is JSON `null`
when the baseline SSE is zero.

The executable checks prevent several common forms of mechanical look-ahead, but
they cannot prove upstream availability metadata, universe membership, revisions,
adjustments, or feature lineage. Evidence files include realized targets and may
be sensitive; classify and retain them under the project's data policy rather
than committing client or restricted data.
