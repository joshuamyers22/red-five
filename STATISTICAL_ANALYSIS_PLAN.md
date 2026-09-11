# Red Five — initial descriptive analysis plan

Version: `red-five-descriptive/v1`. Status: development fixtures only.
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
preprocessing, missing-value imputation or data-driven sign choice. Tied ranks use
average rank. Constant scores/targets and too-small samples produce null metrics
with reason codes. Do not square rank correlation and call it R².

Apply feature availability at the decision and label availability at the report
cutoff. Do not use immature labels even if a later-vintage input contains them.
Model identity must be consistent with the declared mode. Predictive/causal claims,
standard errors, p-values, quantile/decay fits and aggregate significance are deferred
to an analysis plan defining temporal folds, label overlap and multiple testing.

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
