# Transfer coefficient development analysis plan

Version: `red-five-transfer-development/v1`, 2026-09-20.
Status: synthetic software verification only. Owner: Josh (existing project owner).
Based on `templates/STATISTICAL_ANALYSIS_PLAN.md` and the Dropbox transfer plan.
No consequential assessment or live approval has been granted.

## Decision and estimand

Verify the implementation of model-conditional ex-ante transfer alignment:
`alpha.T @ w / (sqrt(alpha.T @ solve(Sigma, alpha)) * sqrt(w.T @ Sigma @ w))`.
Alpha and risk inputs are supplied forecasts. The coefficient is a risk-space
cosine, not generally Pearson correlation and not the unobservable true-alpha
Transfer Coefficient. The reported model Sharpe has the declared snapshot horizon;
no observed or annualized Sharpe is inferred. Practical significance and promotion
thresholds are not selected for a software fixture.

## Data and sample

Synthetic two-asset JSON examples; source hashes identify exact bytes. Units are
simple excess return fractions, covariance in squared simple return fractions,
and supplied weights as fractions of NAV. Forecast/covariance share horizon,
risk-model identity, exact ordered asset IDs and an aware as-of timestamp no later
than the caller-declared evaluation timestamp. UTC normalization does not attest
historical availability. Missing, extra, duplicate or reordered identities fail;
no interpolation, imputation, covariance repair, model fitting or weight fitting.
No real sample window, licensed dataset, assessment split or final holdout is selected.

## Numerical specification

Float64 NumPy Cholesky of scale-normalized positive-definite covariance followed
by a solve; no explicit inverse. Normalize alpha/weights during calculation to
limit overflow. Exact symmetry required; diagnose material asymmetry relative to
matrix scale using `1e-12` in the example. Condition-number limit `1e10` in the
example (allowed [1, 1e12]); larger finite values yield numerically unreliable
null output. Bound clipping is limited to roundoff within `1e-12` in the example
(max allowed `1e-10`). Empty, nonfinite, indefinite/PSD, zero-alpha and zero-risk
inputs fail explicitly. Maximum 256 assets; 16 MiB per input/output artifact.
No Bayesian/regression model or stochastic inference applies. Seed is null because
alignment is deterministic. Optional diagonal Pearson diagnostics report both
risk-coordinate means and cosine-minus-Pearson; constant coordinates give null
Pearson. The cosine remains canonical.

## Diagnostics and verification

Analytic optimal/opposite/orthogonal and correlated fixtures; nonzero-mean Pearson
counterexample; deterministic random SPD cases (seed 190), permutation and scaling
invariance; adversarial numerical/identity/timing/units inputs; immutability,
source/config/plan drift, race/conflict/tamper and CLI/wheel checks. These are
software evidence, not statistical coverage or empirical strategy results.

## Paired comparison policy — not implemented

Future estimand: implemented Sharpe minus pristine Sharpe; report components,
paired correlation, sample coverage and dependence-aware uncertainty separately.
Exact period identity, identical return/cost basis, explicit risk-free convention
and annualization are required; no silent inner joins. Research/model-risk owners
must predeclare moving/stationary block method, block length, replicates, confidence,
seed, overlap policy, minimum sample, calibration DGPs, practical effect, trial
history/multiplicity and locked assessment boundaries. Existing IC bootstrap tests
do not establish Sharpe-difference calibration. No default is silently promoted
into an approved real-data policy. Jobson–Korkie remains blocked pending derivation
review. Gross/net decomposition and cash/financing semantics require data owners.

## Evidence, approval and retirement

Report binds source/config/analysis-plan/lock hashes, source revision digest,
package/dependency/BLAS versions and explicit evaluation time. Schema checks and
internal hashes detect accidental changes; they do not authenticate rewritten
sources/artifacts, certify models, or recompute missing original inputs.
Every output has `live_eligible=false`, null verdict and insufficient-evidence status.
Independent math and fixture reviewers remain unassigned. Real-data licensing,
access, retention, production workload/monitoring and rollback acceptance are open.
Disable evaluation on contract/identity failures or violated numerical assumptions;
preserve verification for previously published evidence. See TRANSFER_VERIFICATION.md.
