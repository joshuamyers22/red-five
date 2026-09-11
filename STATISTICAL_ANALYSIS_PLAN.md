# Red Five — initial descriptive analysis plan

Version: `red-five-descriptive/v3`. Status: development fixtures only.
Decision owner: Josh; no consequential model approval has been granted.

## Estimand and sample

Given externally supplied scores and one declared forward-return target/horizon,
compute Pearson and Spearman correlation over eligible observations. In
`time_series` mode group by model, instrument and contract; in `cross_sectional`
mode group by model and decision time, retaining per-date results. Each group
reports coverage, immature/missing labels, sample size and unavailable reasons.

The evaluated inputs are not claimed to be out-of-sample merely because they have
timestamps. The example is synthetic software-verification evidence, not a signal
discovery study. Upstream availability metadata must be independently trustworthy.

## Implementation

No regression, model selection, residualization or allocation fitting. No learned
preprocessing except the declared training-only score boundaries below; no
missing-value imputation or data-driven sign choice. Tied ranks use
average rank. Constant scores/targets and too-small samples produce null metrics
with reason codes. Do not square rank correlation and call it R².

Apply feature availability at the decision and label availability at the report
cutoff. Do not use immature labels even if a later-vintage input contains them.
Model identity must be consistent with the declared mode. Predictive/causal claims,
standard errors, p-values, decay fits and aggregate significance are deferred
to an analysis plan defining temporal folds, label overlap and multiple testing.

## Descriptive quantile extension

Independently requested quantile sections require an explicit training cutoff,
bin count, minimum training count and minimum eligible labels per bin. Fit only
pre-cutoff scores, never training returns; freeze empirical inverse-CDF cuts for
later evaluation. Time-series models remain separate by instrument/contract.
Cross-sectional mode fits historical scores per model and reports each later date
separately, not per-date equal-count ranks. Collapse ties; count out-of-range
scores; preserve sparse and missing outcomes as null with reasons. Report bin
means, high-minus-low descriptive spread and complete-bin monotonicity only.
The exact policy, grouping, fit metadata and exclusions accompany section v2.
See [the full calculation contract](docs/QUANTILES.md).

This extension does not establish independent observations or upstream out-of-sample
predictions and is not portfolio weighting. No confidence intervals or significance
claim. Bin/cutoff choices must be registered before a future confirmatory study;
post-outcome tuning must be recorded as another trial, not treated as presentation.

## Declared fold and local trial extension

Explicit half-open test windows are ordered and nonoverlapping within an audit.
Training decisions precede test start minus a declared elapsed-time gap; training
labels must be nonmissing and available strictly before that boundary. This
conservative population filter also applies to fold-local score binning, unlike
the original score-only fixed-cutoff API. Numeric training returns never determine
bin boundaries. Test metrics use report-time label maturity and retain exclusions.
Every original row is accounted for in fold membership; sections retain fold
policy, test identities and hashes, without certifying upstream model training.

The local journal registers each wrapper request before computation and retains
computed, unavailable, failed and unfinished attempts. It binds specification and
input hashes to exact section evidence. Historical search completeness remains
unknown, including searches outside the wrapper. Family IDs do not select or
validate a multiplicity policy. Nonoverlapping decision windows do not imply
independent labels; no combined significance or locked final assessment is added.
See [the temporal/trial contract](docs/TEMPORAL_TRIALS.md).

## Supplied portfolio accounting

Optional weights input carries pre-trade and target weights, interval asset total
returns, per-traded-notional side costs and per-NAV holding/financing costs.
Compute target-weight gross contribution minus absolute weight change times side
cost minus holding cost. Aggregate only within identical portfolio intervals.
This is conditional reconciliation, not execution simulation, portfolio
optimization, future capacity forecasting or a Sharpe estimate.

## Validation and later decisions

Tests use hand-computed correlation and trade-side examples, independent groups,
missing/immature labels, duplicates, future timestamps, artifact conflicts and
repeatability. Accounting uses Decimal and exact fixture results.

Open: study families/trial history, valid dependence-aware p-values, selected
Bonferroni/Holm/other policy, fold-local upstream selection evidence, locked final
assessment, practical effect threshold, calibrated costs and paired baseline
utility. Until resolved, outputs record `verdict: null` and an explicit
`decision-policy-not-configured` reason. Code, config, inputs, analysis plan,
lock and software versions accompany each report.
