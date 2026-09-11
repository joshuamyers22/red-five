# Statistical Analysis Plan

Complete this before consequential inference, regression, forecasting, or model
selection. Link the approved version from the result, report, or model card.

## Decision and estimand

- Decision this analysis informs:
- Population and estimand:
- Primary hypothesis or prediction target:
- Prediction time, action, horizon, target availability, and decision owner:
- Model objective, decision utility, guardrail metrics, and known proxy gaps:
- Economic/practical significance threshold:
- Pre-specified versus exploratory analyses:
- Statistical-learning point-of-view preferences followed or departed from, with rationale:

## Data and sample

- Dataset owners, versions, licenses, hashes, and as-of time:
- Dataset manifest, schema contract, partitions, and compatibility decision:
- Inclusion/exclusion rules and point-in-time universe:
- Observation unit, time range, frequency, and expected sample size:
- Outcome, predictors, controls, units, and transformations:
- Missing-data, outlier, censoring, and imputation policy:
- Look-ahead, survivorship, selection, and leakage controls:
- Prediction, feature-availability, and target-availability timestamp semantics:

## Model specification

- Statsmodels class and locked version:
- Polars feature pipeline and exact Polars-to-model boundary:
- Formula or ordered design-matrix columns:
- Intercept, weights, offsets/exposure, fixed effects, and interactions:
- Distribution/link, lag structure, seasonality, and stationarity assumptions:
- Covariance/standard-error estimator, clustering groups, and rationale:
- Multiple-testing or model-selection correction:
- Domain heuristic, naive baseline, and interpretable statistical baseline:
- Candidate model, feature, transformation, and hyperparameter search space:
- Fold-local learned steps, including cleaning, selection, tuning, and calibration:
- Random seeds and numerical tolerances:

## Bayesian regression implementation, when applicable

Use `docs/BAYESIAN_REGRESSION_IMPLEMENTATION.md` for implementation details in
the template repository or a generated quant project. Mark this section not
applicable for a non-Bayesian analysis. These fields specify statistical
implementation; they do not select financial applications.

- Inference engine and locked version; exact model code and parameterization:
- Likelihood, response support, link, offsets/exposures, and error covariance:
- Priors and hyperpriors, constraints, units, scaling, and posterior propriety:
- Design-matrix identity/order, categorical coding, rank, and conditioning:
- Group definitions, exchangeability assumptions, varying coefficients, and covariance:
- Parameter draws, conditional-mean predictions, or new-observation predictions:
- Prediction for existing versus new groups and treatment of new group effects:
- Exact inference, posterior mode, approximation, or posterior simulation:
- Factorizations/solves, numerical tolerances, and degenerate-input behavior:
- Random generator, seed/state, parallel streams, chains, warmup, and retained draws:
- R-hat, bulk/tail ESS, Monte Carlo error, and sampler-specific warning assessment:
- Prior predictive checks, posterior predictive checks, and prior sensitivity:
- Held-out predictive assessment and fitted preprocessing boundaries:
- Missingness assumptions and propagation of imputation uncertainty:
- Analytic/simulated reference cases, implementation tests, and evidence schema:

## Diagnostics and validation

- Identification and rank/collinearity checks:
- Residual, influence, heteroskedasticity, dependence, and stability diagnostics:
- Time-aware train/validation/test or rolling evaluation design:
- Development, selection, and locked final-assessment evidence boundaries:
- Initial test boundary, window/step sizes, embargo or label-availability purge:
- Baselines and ablations:
- Selection uncertainty and candidate-search/history retention:
- Sensitivity analyses and alternative specifications:
- Time, regime, instrument, liquidity, venue, and data-vintage stability slices:
- Calibration, uncertainty coverage, and failure thresholds:
- Transaction costs, capacity, latency, and operational constraints if applicable:
- Research/batch/replay/live parity and training-serving skew evidence:

## Evidence and approval

- Commands, commit, environment lock, input/output hashes, and artifact location:
- Evidence schema version and independent artifact reviewer:
- Results with uncertainty—not coefficient or p-value alone:
- Known limitations and conditions that invalidate use:
- Monitoring, drift, refit, rollback, and retirement policy:
- Falsification criteria and conditions that trigger fallback or retirement:
- Author, independent reviewer, model-risk/compliance approver, and date:
