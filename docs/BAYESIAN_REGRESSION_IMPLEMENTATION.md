# Bayesian Regression Implementation

This guide emphasizes the regression material in Gelman, Carlin, Stern, Dunson,
Vehtari, and Rubin's *Bayesian Data Analysis*, third edition (BDA). It records
statistical specification and implementation practices. It draws no conclusions
about applications of statistical methods to finance and selects no model for a
particular domain.

The reading order is Chapters 14–16, followed by Chapter 17's robust regression
and Chapter 18's missing-data treatment. Chapters 6–7 support checking and
evaluation; Chapters 20–21 extend regression through basis functions and Gaussian
processes. Page references below are **PDF page markers in the supplied copy**;
printed book pages are 15 lower in these chapters.

## Specify the regression before implementing it

State whether the goal is conditional description, prediction, or causal
inference. A fitted conditional association does not by itself identify a causal
effect; the latter needs an explicit identification argument and data-collection
assumptions. BDA §§14.1, 14.3–14.4, PDF pp. 368–369 and 373–380.

Record the observation unit, response support, likelihood, link, parameterization,
and error structure. For the elementary normal linear model, document the
conditional mean `X beta` and the assumption of independent, equal-variance normal
errors. If a different covariance model is specified, implement that model
explicitly. Changing a reported standard-error estimator does not implement a
different Bayesian likelihood. BDA §§14.2, 14.7, PDF pp. 369–372 and 384–391.

Make the design matrix reproducible: row identity and order, column names and
order, intercept, categorical reference levels, transformations, interactions,
offsets, weights, and units. Fit estimated transformations using the declared
training sample and retain their parameters for prediction. Check rank and
conditioning; a prior that regularizes coefficients does not create information
in the likelihood. BDA §§14.5–14.6, PDF pp. 380–384; evaluation boundaries are also
covered by the existing statistical analysis plan.

## Linear regression and numerical computation

For the classical normal model, BDA §14.2 gives conditional coefficient draws,
residual-variance draws, and posterior predictive simulation. Its improper-prior
derivation is a specific mathematical case, not a default for arbitrary models.
Check posterior propriety and degenerate inputs, including rank deficiency,
insufficient residual degrees of freedom, and zero residual variation. Never
silently turn an improper or degenerate posterior into finite output.

Use matrix factorizations and linear solves. BDA §14.2 explicitly gives QR-based
computation (PDF p. 371); §14.7 uses Cholesky-based computation and notes that
explicit inverses are unnecessary (PDF p. 386). Preserve symmetry and check the
required positive-definiteness assumptions for covariance matrices. Report
failed factorizations and ill-conditioning; any regularization or jitter changes
the numerical or statistical specification and must be recorded.

Distinguish coefficient draws, conditional-mean draws, and new-observation draws.
To simulate a new observation in the normal model, draw the parameters jointly
from the posterior, then draw the observation conditional on those parameters.
Using only `X_new beta` omits observation noise and does not produce the full
posterior predictive distribution. BDA §14.2, PDF p. 372.

## Priors, scaling, and hierarchical regression

Specify priors for coefficients, intercepts, residual scales, group scales, and
correlations as applicable, including units and parameter constraints. Predictor
rescaling changes the meaning of a fixed coefficient prior; retain the scale
transformations and interpret summaries on the intended scale. Document prior
information separately from observations, even when normal priors are implemented
as augmented linear systems. BDA §§14.6, 14.8, PDF pp. 383–384 and 391–393.

For hierarchical linear models, define the grouping structure and which
coefficients are exchangeable within each batch. Specify varying intercepts,
varying slopes, their joint covariance, and hyperpriors. Partial pooling is a
consequence of this specified model. It is not a replacement for explaining the
grouping and exchangeability assumptions. BDA §§15.1–15.4, PDF pp. 397–406.

Distinguish prediction for an observed group from prediction for a new group.
For the latter, integrate over a new group effect conditional on the population
parameters, as well as uncertainty in those parameters. Reusing an existing
group's fitted effect changes the prediction target. Check group-index mappings
and preserve the parameterization used during fitting and prediction.

Simulate from the prior predictive distribution to inspect the consequences of
priors on the outcome scale. Repeat the analysis under declared plausible prior
alternatives to measure sensitivity. Predictive simulation and hierarchical
replication details are documented in the official
[Stan predictive-check guide](https://mc-stan.org/docs/2_38/stan-users-guide/posterior-predictive-checks.html).

## Generalized linear and robust regression

Match the likelihood and link to the declared response: record binomial trial
counts, count-model exposures or offsets, and dispersion parameters where used.
Calculate likelihoods with numerically stable library primitives and validate
support at input boundaries. A link transformation alone does not define the
likelihood. BDA §§16.1–16.2, PDF pp. 421–427.

Detect separation as well as collinearity in logistic regression. BDA §16.3
explains how weakly informative coefficient priors can regularize separation,
but its numerical prior scales depend on its predictor-scaling conventions.
Specify and check the actual prior rather than transplanting a textbook constant.
Distinguish a posterior mode, a normal approximation, variational approximation,
and posterior simulation in both APIs and result artifacts. BDA §16.3, PDF
pp. 427–435.

For Student-t regression, specify residual scale and degrees of freedom, including
whether degrees of freedom are fixed or inferred. A t scale is not generally its
standard deviation. Do not confuse t-distributed observation errors with the
t-shaped marginal coefficient posterior arising from normal regression.
Changing the residual likelihood changes the model; a robust covariance estimate
on an OLS fit does not implement t-error regression. BDA §17.5, PDF pp. 459–460.

State the missingness mechanism and assumptions that justify ignoring or modeling
it. Retain uncertainty from modeled missing values or multiple imputations;
single-value filling does not reproduce that uncertainty. BDA §§18.1–18.3,
PDF pp. 464–470.

## Verification and retained evidence

Use analytically tractable cases to check numerical implementations and simulated
data to check parameter recovery and predictive behavior. Test shape and column
alignment, group-index permutations, invalid scales, rank-deficient designs,
separation, prediction for unseen groups, and reproducibility where applicable.
Choose tolerances that account for floating-point and Monte Carlo error.

Retain model and prior specifications, data/design identity, transformations,
implementation and environment versions, random-stream configuration, inference
settings, diagnostics, and the prediction target. A seed alone does not establish
reproducibility across different algorithms or environments.

For MCMC, examine multiple chains, rank-normalized R-hat, bulk and tail effective
sample sizes, and Monte Carlo error for reported quantities. Investigate
sampler-specific warnings. For HMC, include divergences, energy diagnostics, and
tree-depth behavior. Use the supported sampler's current diagnostic guidance;
do not turn BDA examples using R-hat below 1.1 into a production acceptance rule.
[Stan's diagnostic guide](https://mc-stan.org/learn-stan/diagnostics-warnings.html)
documents these distinctions. Convergence diagnostics assess computation, not
model adequacy.

Use posterior predictive checks to compare specified features of replicated and
observed data, including residual variation and dependence. These checks reuse
the observed data and are distinct from held-out predictive assessment. Retain
the evaluation split and all fitted preprocessing, and evaluate predictions
against the declared target. BDA Chapters 6–7, with regression examples in
Chapters 14–16.

## Template integration

Complete the applicable fields in `templates/STATISTICAL_ANALYSIS_PLAN.md`.
The generated quant starter currently implements Statsmodels OLS evidence and
time validation. This guide does not add a Bayesian estimator or make those
artifacts represent posterior inference. Any Bayesian implementation needs an
explicit engine choice, result schema, and verification appropriate to the model.

The template repository's `docs/NUMERICAL_SOURCE_REVIEW.md` records source hashes,
reading maps, extraction limitations, and the separate Hull reference inventory.
