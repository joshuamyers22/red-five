# Red Five — Transfer Coefficient Project Plan

Status: **adapted implementation plan; local alignment slice only; no production approval**  
Prepared: 2026-09-20  
Source: Dropbox `echo-five-transfer-coefficient-project-plan.md`; its linked
transfer-coefficient note was not supplied in the local Dropbox copy.  
Template basis: local `production-project-template` at commit
`8879be48f3b760e65f6bed32f8740314fe92910d`

Repository reconciliation: the user corrected the target to `red-five`. Baseline
`c6bae32d40805f185fed1e8b5864dcb183fdbfc5` was inspected on 2026-09-20.
See [integration decisions](TRANSFER_INTEGRATION.md),
[development analysis plan](TRANSFER_COEFFICIENT_ANALYSIS_PLAN.md), and
[verification record](TRANSFER_VERIFICATION.md). Later-phase paths and command
examples below remain design proposals, not installed functionality.

Original Dropbox source SHA-256: `684d4de3a1c22d3b577131608953c6049fbbb9b3d137fb8fecb35bc16977758e`.
The original source is preserved in Dropbox. This repository adaptation governs
Red Five integration; the mathematical and later evidence gates below are retained.

## 1. Outcome

Add a transfer-coefficient evaluation capability to Red Five that answers two
different questions without conflating them:

1. **Ex ante alignment:** Given a declared expected-return vector, risk model, and
   implemented portfolio, how closely does the portfolio align with the
   model-implied maximum-Sharpe direction?
2. **Observed implementation drag:** Given paired pristine and implemented strategy
   returns, what is the observed difference in Sharpe, with uncertainty that
   preserves cross-strategy pairing and temporal dependence?

The feature should help a quant researcher identify where constraints, sizing,
costs, or execution may be degrading a strategy while making the forecast-model
dependency explicit. It must not present forecast-based alignment as the exact
Transfer Coefficient from the paper, because that identity uses unobservable true
expected returns.

### Measurable success criteria

- A pure calculation reproduces hand-worked diagonal-covariance examples and the
  equivalent full-covariance risk-space formula within declared numerical tolerance.
- Outputs distinguish `ex_ante_transfer_alignment` from observed Sharpe differences;
  neither is silently relabeled as the other.
- A paired block bootstrap produces deterministic results for a fixed seed, retains
  pair identity, and is calibration-tested on synthetic iid, autocorrelated,
  heavy-tailed, null, and known-difference cases.
- Invalid covariance, zero-risk portfolios, unaligned dates, mixed return units,
  insufficient samples, and non-finite values fail closed or return an explicit
  `unavailable` status with stable reason codes.
- Every result binds input hashes, configuration, analysis-plan hash, code revision,
  dependency versions, seed, and evaluation time into an immutable evidence artifact.
- The repository's existing quality gate passes, followed by the production-template
  checks that apply to Red Five's language and deployment model.
- A domain reviewer approves the mathematical contract and a separate reviewer
  verifies the end-to-end fixture before any production-facing claim.

### Explicit non-goals

- Estimating true alpha, declaring that forecast alpha is true alpha, or validating
  an alpha model.
- Selecting or fitting a covariance model.
- Building a general portfolio optimizer or changing live portfolio weights.
- Claiming that constraints necessarily reduce out-of-sample Sharpe.
- Using a TC threshold as a promotion, allocation, or trading rule.
- Treating the Jobson–Korkie approximation as the primary inferential method.
- Supporting live execution in the first release.

## 2. Concept and required terminology

### 2.1 Canonical risk-space coefficient

For expected excess returns \(\alpha\), covariance matrix \(\Sigma\), and portfolio
weights \(w\), define

$$
\operatorname{SR}_{\text{model}}(w)
=
\frac{\alpha^\top w}{\sqrt{w^\top\Sigma w}}.
$$

If \(\Sigma\) is positive definite, the unconstrained maximum-Sharpe direction is
proportional to \(\Sigma^{-1}\alpha\), and its model-implied Sharpe bound is

$$
\operatorname{SR}_{\mathrm{opt}}
=
\sqrt{\alpha^\top\Sigma^{-1}\alpha}.
$$

The exact risk-space alignment is

$$
\operatorname{TA}(\alpha,\Sigma,w)
=
\frac{\alpha^\top w}
{\sqrt{\alpha^\top\Sigma^{-1}\alpha}
 \sqrt{w^\top\Sigma w}}.
$$

It is a cosine in risk space and satisfies

$$
\operatorname{SR}_{\text{model}}(w)
=
\operatorname{TA}(\alpha,\Sigma,w)
\operatorname{SR}_{\mathrm{opt}},
\qquad -1\leq\operatorname{TA}\leq1.
$$

The public result name should be `ex_ante_transfer_alignment`, abbreviated `TA` in
the implementation, because \(\alpha\) and \(\Sigma\) are forecasts. Documentation
may explain that this is the computable, model-conditional analogue of the paper's
Transfer Coefficient; it must not imply that it uses true expected returns.

For diagonal \(\Sigma=\operatorname{diag}(\sigma_1^2,\ldots,\sigma_N^2)\), this
reduces to the uncentered cosine between \(\alpha_i/\sigma_i\) and
\(w_i\sigma_i\). It equals the paper's Pearson-correlation expression only when
both cross-sectional means are zero. Therefore:

- the cosine is canonical;
- Pearson correlation is an optional, clearly labeled diagnostic;
- the result records both cross-sectional means and the difference between cosine
  and Pearson correlation when the diagonal diagnostic is requested; and
- no implementation may use a generic correlation function as a substitute for the
  canonical coefficient.

### 2.2 Observed paired comparison

For aligned pristine and implemented excess returns, report separately:

$$
\widehat{\Delta\operatorname{SR}}
=
\widehat{\operatorname{SR}}_{\mathrm{implemented}}
-
\widehat{\operatorname{SR}}_{\mathrm{pristine}}.
$$

Use this sign convention everywhere: negative values mean the implementation
underperformed the pristine strategy on observed risk-adjusted returns. Report both
component Sharpes, their difference, paired return correlation, sample size, periods
per year, and a confidence interval.

Do **not** call the observed Sharpe ratio, Sharpe difference, or Sharpe ratio ratio a
Transfer Coefficient. A ratio becomes undefined or unstable when the pristine Sharpe
is zero or near zero and can obscure economically material level differences.

### 2.3 Inference policy

The default is a paired moving-block or stationary bootstrap over time. Every
resample uses identical time indices for the pristine and implemented series.
Configuration must declare:

- resampling method;
- block-length selection rule or fixed length;
- number of replicates \(B\);
- confidence level;
- random seed;
- return frequency and annualization factor; and
- whether returns overlap.

The iid paired bootstrap described in the source note is available only as an
explicit diagnostic. Jobson–Korkie is optional and may be emitted only when the user
requests it and the artifact states its iid, joint-normal, and large-sample
assumptions. Its implementation is blocked until the factor-of-two inconsistency
between Equation (30) and the note's earlier marginal Sharpe variance is reconciled
against the original estimator and any accepted correction. Neither method turns a
selected backtest into untouched evidence.

## 3. Product behavior

### 3.1 Supported workflows

**Workflow A — one-snapshot ex-ante diagnostic**

1. Read an expected-return vector, implemented weights, and covariance snapshot.
2. Validate asset identity, units, as-of times, symmetry, finiteness, and dimensions.
3. Solve the risk system without explicitly forming a matrix inverse.
4. Emit model Sharpe, optimal model Sharpe, transfer alignment, portfolio risk,
   numerator, numerical diagnostics, and provenance.

**Workflow B — many-snapshot ex-ante replay**

1. Evaluate Workflow A independently at each rebalance snapshot using only the
   forecast and risk model declared available at that time.
2. Retain every snapshot result, including invalid and unavailable snapshots.
3. Summarize distribution, time stability, constraint regimes, and coverage. Do not
   average silently across incompatible model, universe, or unit identities.

**Workflow C — paired realized-return comparison**

1. Align pristine and implemented returns by exact period identity.
2. Apply the same declared risk-free return and annualization convention.
3. Reject silent inner joins; enumerate missing-left, missing-right, duplicate, and
   excluded pairs.
4. Compute both Sharpes, \(\Delta\operatorname{SR}\), paired correlation, and the
   dependence-aware bootstrap interval.
5. Keep gross-vs-gross and net-vs-net comparisons distinct. If both are supplied,
   report construction drag and cost drag as separate comparisons.

### 3.2 Proposed command surface

The exact CLI must follow Red Five's established command structure. A provisional
shape is:

```sh
red-five transfer alignment \
  --forecast forecast.parquet \
  --covariance covariance.parquet \
  --config transfer-config.json \
  --output build/transfer-alignment.json

red-five transfer compare \
  --returns paired-returns.parquet \
  --analysis-plan docs/TRANSFER_COEFFICIENT_ANALYSIS_PLAN.md \
  --config transfer-config.json \
  --output build/transfer-comparison.json

red-five transfer verify build/transfer-comparison.json
```

Library users should receive immutable typed result objects. The CLI serializes the
same objects; it must not maintain a second calculation path.

## 4. Data and schema contracts

### 4.1 Forecast snapshot

Minimum logical fields:

| Field | Contract |
|---|---|
| `snapshot_id` | Stable caller-owned identity |
| `as_of` | UTC-aware information timestamp |
| `asset_id` | Unique within snapshot; exact match across alpha, weights, covariance |
| `expected_excess_return` | Finite value with declared horizon and unit |
| `implemented_weight` | Finite signed exposure with declared weight/notional unit |
| `risk_model_id` | Immutable risk-model snapshot identity |
| `forecast_model_id` | Immutable alpha-model snapshot identity |
| `universe_id` | Point-in-time universe identity |

The covariance artifact must declare asset order, return horizon, unit, as-of time,
matrix hash, and risk-model identity. Reordering is explicit and recorded; missing or
extra assets fail. Symmetry is checked within a predeclared tolerance and is never
silently repaired in the calculation core.

### 4.2 Paired returns

Minimum logical fields:

| Field | Contract |
|---|---|
| `period_start`, `period_end` | UTC-aware and strictly ordered |
| `pristine_return` | Finite realized return in the declared basis |
| `implemented_return` | Same horizon and basis as pristine |
| `risk_free_return` | Same horizon, or an explicit zero policy |
| `return_basis` | `gross` or `net`; values in a comparison must match |
| `strategy_snapshot_id` | Identity of the strategy definitions being compared |
| `source_id` | Versioned input provenance |

Simple returns and log returns may not be mixed. Sharpe is computed from simple
excess returns unless an approved Red Five convention says otherwise. Overlapping
horizons must be declared and must influence the bootstrap design.

### 4.3 Numerical contract

- Use `float64` for linear algebra and record the library/BLAS versions in evidence.
- Never compute `inv(Sigma) @ alpha`; use a symmetric factorization and solve.
- Positive definiteness is the default requirement. A positive-semidefinite mode
  requires a separate ADR covering eigenspace projection, tolerance, null-space alpha,
  pseudo-inverse behavior, and interpretation.
- Reject materially asymmetric, indefinite, non-finite, empty, and zero-risk input.
- Record condition number or a stable condition estimate and classify results above a
  configured threshold as `numerically_unreliable`, not successful.
- Clip only roundoff excursions immediately outside \([-1,1]\), under a documented
  tolerance. Larger excursions are errors.
- Positive rescaling of weights leaves alignment unchanged; negative rescaling flips
  its sign. Tests must lock both behaviors.

## 5. Provisional implementation structure

After Phase 0 maps the real repository, prefer the smallest equivalent of:

```text
src/red_five/transfer/
├── domain.py          # typed validated inputs and results
├── alignment.py       # pure risk-space calculations
├── paired_sharpe.py   # Sharpes, paired differences, optional JK diagnostic
├── bootstrap.py       # paired block resampling
├── evidence.py        # stable schema, hashing, publication, verification
└── cli.py             # adapters only

tests/transfer/
├── test_alignment.py
├── test_paired_sharpe.py
├── test_bootstrap.py
├── test_contracts.py
├── test_evidence.py
└── test_cli.py
```

The core accepts arrays and validated domain objects, performs no I/O, has no global
random state, and returns values plus diagnostics. File parsing, tabular transforms,
and publication remain adapters. Reuse Red Five's existing schema, error, evidence,
CLI, and immutable-output mechanisms rather than creating parallel infrastructure.

Proposed stable reason codes include:

```text
TRANSFER_ASSET_SET_MISMATCH
TRANSFER_COVARIANCE_ASYMMETRIC
TRANSFER_COVARIANCE_NOT_PD
TRANSFER_COVARIANCE_ILL_CONDITIONED
TRANSFER_ZERO_ALPHA_NORM
TRANSFER_ZERO_PORTFOLIO_RISK
TRANSFER_UNALIGNED_RETURN_PERIODS
TRANSFER_MIXED_RETURN_BASIS
TRANSFER_INSUFFICIENT_OBSERVATIONS
TRANSFER_NONFINITE_INPUT
```

## 6. Evidence artifact

Use one versioned envelope with separate sections:

```text
identity
  schema_version, analysis_id, result_hash
  source hashes, config hash, analysis-plan hash
  code revision, dependency versions, evaluated_at_utc

alignment
  status, value, model_sharpe, optimal_model_sharpe
  expected_return_dot_weight, portfolio_risk
  covariance diagnostics, asset count, centering diagnostics

paired_comparison
  status, pristine_sharpe, implemented_sharpe, delta_sharpe
  paired_correlation, observations, annualization
  bootstrap method, block rule/length, B, seed, confidence interval
  excluded-pair counts and reason codes

interpretation
  mandatory model-dependency warning
  mandatory no-live-decision warning until separately approved
  limitations and invalidation conditions
```

Publication must be create-only and atomic. Verification recomputes internal hashes
and schema invariants but explicitly does not certify source truth, model validity, or
financial correctness.

Operational telemetry may include status, reason code, duration, dimensions, and
result identity. It must not include raw alpha, positions, covariance entries, returns,
absolute private paths, or credentials.

## 7. Statistical analysis plan

Before consequential real-data use, create
`docs/TRANSFER_COEFFICIENT_ANALYSIS_PLAN.md` from the production template's
[statistical analysis plan](../templates/STATISTICAL_ANALYSIS_PLAN.md).
It must resolve at least:

- the decision the comparison informs and the minimum economically material
  \(\Delta\operatorname{SR}\);
- strategy population, sample window, return frequency, and excess-return definition;
- exact pristine and implemented strategy definitions and whether either was selected
  using the assessment interval;
- gross/net cost treatment, leverage, risk budget, cash, financing, and stale-price
  policy;
- missing dates, outliers, market closures, overlapping returns, and corporate actions;
- development, method-selection, and locked final-assessment boundaries;
- block-bootstrap method, block-length rule, \(B\), seed, interval type, and minimum
  sample size;
- multiplicity policy if many strategies, constraint sets, samples, or bootstrap
  designs are compared;
- regime, instrument, liquidity, and model-vintage stability slices;
- falsification, fallback, monitoring, and retirement conditions; and
- accountable research, data, engineering, and model-risk reviewers.

## 8. Verification strategy

### 8.1 Deterministic mathematical fixtures

1. **Optimal diagonal:** \(w=c\alpha/\sigma^2\), \(c>0\), gives alignment 1.
2. **Opposite direction:** \(w=-c\alpha/\sigma^2\) gives alignment -1.
3. **Risk orthogonal:** construct \(w\) with \(\alpha^\top w=0\); alignment is 0.
4. **Scale invariance:** positive weight scaling changes risk and numerator but not
   alignment.
5. **Diagonal/full equivalence:** diagonal specialized calculation matches the general
   covariance calculation.
6. **Hand-worked correlated case:** two- and three-asset examples reconcile against
   independently calculated values.
7. **Centering counterexample:** cosine and Pearson correlation differ when the
   risk-adjusted vectors have nonzero mean; the canonical result matches the Sharpe
   ratio identity.
8. **Constraint example:** a supplied constrained weight vector has lower model
   alignment while a separate noisy-input simulation demonstrates that this does not
   prove lower out-of-sample Sharpe.

### 8.2 Property and adversarial tests

- Symmetric positive-definite matrices across controlled condition numbers.
- Permuting assets jointly leaves every result unchanged.
- Dropping or independently permuting one input fails.
- Near-singular, indefinite, asymmetric, NaN, infinity, duplicate asset, empty,
  zero-alpha, and zero-risk cases follow declared policies.
- Alignment remains within bounds up to declared floating-point tolerance.
- No caller input is mutated.

### 8.3 Bootstrap validation

- Fixed seeds reproduce indices, estimates, and serialized evidence.
- Every bootstrap draw preserves pristine/implemented pair identity.
- Identical return series give exactly zero observed Sharpe difference and a
  degenerate zero interval when variance is nonzero.
- Synthetic positive and negative implementation-drag cases recover the correct sign
  at adequate sample sizes.
- Autocorrelated synthetic returns show why iid resampling is not the default.
- Heavy-tailed, volatility-clustered, constant, near-zero-volatility, missing-pair,
  and short-history cases produce bounded behavior or explicit unavailability.
- Monte Carlo calibration records empirical interval coverage over predeclared data-
  generating processes. It is evidence about those processes, not universal proof.

### 8.4 End-to-end evidence

- One tiny fixture runs from input validation through calculation, atomic publication,
  and verification.
- A golden JSON artifact locks schema and equation semantics without overfitting
  incidental formatting.
- Retry cannot overwrite a different artifact; concurrent publication has one winner.
- Tampering, schema-version mismatch, config drift, and input-hash mismatch are found.
- A clean clone/frozen install runs tests, static checks, build, fixture, and verifier.

## 9. Delivery phases and gates

| Phase | Deliverable | Exit evidence |
|---|---|---|
| 0 — Repository and decision discovery | Inspect Red Five's brief, memory, source, tests, CLI, data conventions, and deployment model; assign owners; complete feature brief and analysis plan | Approved integration map; resolved open decisions; no provisional path names left in implementation ticket |
| 1 — Pure alignment core | Typed inputs, covariance validation, solve-based risk-space alignment, diagonal diagnostics | Hand-worked fixtures, property tests, numerical-failure tests, independent math review |
| 2 — Paired comparison core | Sharpe convention, exact date alignment, paired block bootstrap, optional explicitly requested JK diagnostic | Deterministic and Monte Carlo tests; missing/alignment attacks; analysis-plan linkage |
| 3 — Evidence and CLI | Existing Red Five adapters, immutable artifact, stable reason codes, verifier | End-to-end golden fixture; atomicity/tamper/retry tests; JSON schema review |
| 4 — Historical replay | Snapshot replay, coverage and stability summaries, gross/net decomposition | Point-in-time replay; reconciliation to independently calculated sample; resource measurements |
| 5 — Production hardening | Documentation, threat model, telemetry, runbook, data retention/access, rollback | Repository quality gate; dependency/license audit; restore/rollback exercise; adversarial review |
| 6 — Consequential-use gate | Locked assessment and accountable approval | Final evidence reviewed by quant, engineering, data, and model-risk owners; explicit live-eligibility decision |

Phase 1 must not wait for real data. Phase 4 must not begin until pristine and
implemented strategy semantics are identical apart from the implementation feature
being studied. A documentation update alone cannot close an evidence gate.

## 10. Acceptance evidence

| Requirement | Verification | Owner | Status |
|---|---|---|---|
| Forecast-based diagnostic is not mislabeled as exact TC | Schema, CLI snapshot, docs review | Quant + product | Proposed |
| General covariance identity is correct | Hand calculations, property tests, independent review | Quant | Proposed |
| Diagonal formula reconciles to source note | Golden fixture including centering counterexample | Quant | Proposed |
| Pairing and timestamp semantics are fail-closed | Contract and end-to-end tests | Data + engineering | Proposed |
| Serial dependence is respected | Block-bootstrap tests and simulation record | Quant | Proposed |
| Numerical failures are explicit | Ill-conditioning/PSD/adversarial matrix tests | Engineering | Proposed |
| Evidence is reproducible and immutable | Clean-run hash, retry/race/tamper tests | Engineering | Proposed |
| Sensitive inputs do not enter telemetry | Schema test and telemetry review | Security + engineering | Proposed |
| Runtime and memory are bounded | Representative benchmark with declared dimensions | Engineering | Proposed |
| Rollback is safe | Feature disable/removal drill; old artifacts remain verifiable | Operations | Proposed |

## 11. Project constraints and risk

### Data classification and retention

Expected returns, holdings, covariance matrices, and realized strategy returns may be
proprietary investment data. Treat them as restricted until the owner assigns a less
restrictive classification. Do not commit real inputs or derived position-level
artifacts. Define retention, artifact access, encryption, deletion propagation, and
backup policy before Phase 4.

### Capacity and performance

The dominant alignment cost is covariance factorization, typically \(O(N^3)\) time
and \(O(N^2)\) memory for dense matrices. Phase 0 must record representative asset
counts and whether the existing risk model is dense, sparse, or factor structured.
Do not promise intraday or live latency until benchmarks on representative matrices
establish p50/p95/p99 runtime and peak memory. Bound bootstrap replicate count,
sample length, concurrent jobs, and output size.

### Top failure scenarios

| Failure | Consequence | Control |
|---|---|---|
| Forecast alpha is presented as true alpha | False causal explanation of realized Sharpe | Naming, mandatory warning, schema separation, review test |
| Pearson correlation replaces risk-space cosine | Identity fails under nonzero means | Canonical solve-based formula and centering fixture |
| Risk model and weights use different asset order | Plausible but wrong coefficient | Exact identity join, recorded reorder, permutation tests |
| Near-singular covariance produces unstable results | Extreme or non-reproducible coefficient | Condition checks, fail-closed default, no explicit inverse |
| Random iid bootstrap ignores serial dependence | Understated uncertainty | Paired block default, overlap declaration, simulation |
| Gross pristine is compared with net implementation | Cost and construction drag conflated | Matching `return_basis`, separate named comparisons |
| Strategy selection leaks into assessment | Optimistic inference | Analysis plan, trial history, locked assessment |
| Missing dates are silently inner-joined | Biased paired sample | Exact alignment and exclusion accounting |
| Sensitive positions appear in logs | Confidentiality breach | Aggregate telemetry only; schema/fixture tests |
| New artifact overwrites prior evidence | Audit and reproducibility loss | Create-only atomic publication and verifier |

## 12. Deployment, observability, and rollback

- Ship disabled by default behind Red Five's existing feature/config mechanism.
- First release is offline/research-only and emits `live_eligible=false` unless an
  accountable later decision changes that field.
- Observe run status, stable error code, duration, asset count, observation count,
  bootstrap replicates, and result identity—not financial inputs.
- Alert on repeated invalid risk models, falling paired coverage, numerical-
  unreliability rates, stale risk/forecast snapshots, and artifact publication failure.
- Rollback disables new evaluation while keeping the reader/verifier for previously
  produced schema versions. Schema changes are additive or explicitly migrated; never
  strand old evidence.

## 13. Open decisions

| Question | Needed by | Decision owner | Record |
|---|---|---|---|
| What is Red Five's current package/CLI/evidence architecture? | Phase 0 | Engineering | Integration note |
| Is this feature diagnostic-only, or does Red Five also produce the implemented weights? | Phase 0 | Product + quant | Project brief |
| What are the canonical return, cash, leverage, and annualization conventions? | Phase 0 | Quant | Analysis plan |
| Are covariance matrices PD by contract, or must factor/PSD risk models be supported? | Phase 0 | Risk + engineering | ADR if PSD |
| Which paired block bootstrap and block-length rule is primary? | Phase 2 | Quant | Analysis plan |
| What minimum sample and coverage produce `available` rather than `insufficient_evidence`? | Phase 2 | Quant + model risk | Analysis plan |
| Which cost bases are available for gross/net decomposition? | Phase 4 | Execution + data | Data contract |
| What data classification, retention, and artifact access policy applies? | Before real data | Data + security | Threat model/brief |
| What practical \(\Delta\operatorname{SR}\) matters for a decision? | Before locked assessment | Decision owner | Analysis plan |
| Is Jobson–Korkie worth supporting, and what verified variance formula/convention applies? | Phase 2 | Quant | Derivation fixture plus ADR or rejection note |

## 14. Template guidance applied

This plan applies the local template's:

- [project brief](../PROJECT_BRIEF.md)
  for outcome, non-goals, constraints, failure scenarios, system outline, acceptance
  evidence, and open decisions;
- [statistical analysis plan](../templates/STATISTICAL_ANALYSIS_PLAN.md)
  for estimand, point-in-time data, validation, uncertainty, and approval;
- [production repository standard](PRODUCTION_REPOSITORY_STANDARD.md)
  for reproducible dependencies, repository quality, security, evidence, and release
  controls;
- [quant statistical-learning point of view](STATISTICAL_LEARNING_POINT_OF_VIEW.md)
  for decision-first design, credible baselines, temporal evidence, fragility checks,
  and research/production parity; and
- [production blueprint](TRANSFER_INTEGRATION.md)
  for pure-core/adapters structure, explicit boundaries, bounded failure behavior, and
  operational readiness.

The recommended first implementation slice is Phase 1's pure calculation core plus a
single synthetic CLI/evidence path. It creates an inspectable vertical slice without
claiming that the statistical comparison, real-data contract, or production rollout
is complete.
