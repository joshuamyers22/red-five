# Conditional block-bootstrap intervals

Open `notebooks/uncertainty.ipynb` from `make notebook`. Individual sections work
without a full report or a notebook, and can be recorded through `TrialLedger.run`.

```python
from red_five.sections import evaluate_section
from red_five.uncertainty import BootstrapConfig

options = BootstrapConfig(
    metric="pearson_ic",
    block_length=8,
    replicates=500,
    seed=372,
    confidence=0.95,
    step_seconds=86400,
    minimum_time_points=64,
)
result = evaluate_section(
    "uncertainty",
    signals,
    config,
    plan,
    lock,
    uncertainty=options,
)
display(result.select().table())
display(result.select().figure())
```

No parameter is inferred from the observed result. These are development
uncertainty estimates, conditional on a declared sample and method—not adjusted
for model/metric/block selection. They do not produce p-values, winner selection,
Sharpe/utility estimates or acceptance verdicts. Upstream OOS remains unverified.

## Estimand and resampling unit

- **Time series:** Pearson or Spearman correlation within each
  model/instrument/contract. Resample score/return **pairs together**, in their
  existing time order within blocks. Recompute the statistic, including tied
  average ranks for Spearman, on every resample. Never pool unrelated models.
- **Cross-sectional:** calculate the existing per-model/per-date IC first,
  respecting the declared minimum observations and report-time label maturity.
  Resample blocks of date ICs to estimate the **equal-date mean IC**. Do not
  resample individual instruments as though they were independent dates, pool raw
  scores across models, or reinterpret this as temporal correlation. Per-date
  estimates and coverage remain in diagnostics; eligible universes may differ.

The implemented method draws overlapping, noncircular, fixed-length blocks with
replacement, concatenates `ceil(n / block_length)` blocks and truncates to `n`.
Intervals are empirical lower/upper percentiles using NumPy's linear quantile
convention; standard error is the sample SD of replicate statistics (`ddof=1`).
This follows the moving-block construction described in
[CMU's bootstrap lecture](https://www.stat.cmu.edu/~cshalizi/dst/20/lectures/16/lecture-16.html).
The method preserves within-block order, not dependence across concatenation
boundaries. Approximate stationarity and an adequate block length remain
assumptions, not properties certified by the code.

Noncircular moving blocks also give edge observations different resampling
frequencies than interior observations; circular and stationary variants differ.
See [the arch time-series bootstrap documentation](https://bashtage.github.io/arch/bootstrap/timeseries-bootstraps.html).
No arch dependency is added and no automatic optimal-block selector is used.
NumPy handles resampling while the existing production correlation function is
reused. Statsmodels remains available for later, separately specified HAC/model
inference; this is not an upstream regression-fitting workflow.

## Explicit validity and resource checks

`BootstrapConfig` requires metric, block length, replicates, seed, confidence,
elapsed seconds per time step, and minimum time points. Supported bounds:
block length 1–1,000; replicates 200–2,000; unsigned 32-bit seed; confidence
0.80–0.99; time step 1–31,536,000 seconds; minimum time points 10–100,000.
There must be at least five expected draws in each requested percentile tail.
That is a numerical resolution floor, not proof of Monte Carlo precision.

- Every adjacent unique decision timestamp must match `step_seconds`. Missing
  dates are not filled or silently compressed. This first adapter does **not**
  infer exchange sessions, holidays or a trading-calendar grid. Provide a suitable
  validated regular elapsed-time sample or expect `irregular-time-grid`.
  Missing leading/trailing periods or an entirely absent model cannot be detected
  without a separately declared expected calendar/universe; this is not full
  sample-coverage certification.
- For time series, all time points need eligible labels; for cross-sectional
  inference every date needs a valid per-date IC. Otherwise interval evidence is
  unavailable (`incomplete-time-grid`). Point estimates may still describe the
  eligible subset; they are not estimates for imputed missing observations.
- Time-series sample size must meet both the evaluation configuration minimum
  and the bootstrap minimum. At least three blocks must fit in the sample. These
  are mechanical floors, not power or calibration claims.
- Block length must cover at least the longest label interval in time-step units.
  This is a conservative guard, not a test that blocks capture all dependence.
  Longer serial dependence can still make intervals inadequate. Block length one
  is explicitly the iid resampling special case, permitted only for compatible
  label spans; it is not the default.
- Any undefined bootstrap replicate makes the whole interval unavailable;
  invalid replicates are counted, never dropped to obtain a favorable interval.
  A replicate range at most `1e-12` is treated as degenerate, rather than showing
  a falsely precise zero-width band (including exact perfect correlations).
- Calls are capped at 2,000,000 input-row × replicate work units, in addition to
  existing input and 200-section-row limits. Over-budget calls fail before
  resampling. This is a bounded local workload, not a worker-level time/memory SLA.

The declared seed and a deterministic group-key digest initialize a separate
NumPy generator per model. Sorting and adding unrelated models cannot change an
existing model's interval. No cross-model/simultaneous covariance is estimated.
Intervals are reproducible with the bound inputs, code and locked environment;
they need not be identical across numerical-library versions.

## Notebook, provenance and trial integration

`uncertainty` uses independent section schema `red-five-section/v3`, leaving v1/v2
and full-report v1 compatibility intact. `view.section("uncertainty")` cannot
fabricate evidence from an old report; evaluate the section explicitly. Typed
policy, estimand, timestamps, time-point/row counts, replicate counts, method,
reasons, bounds and standard errors accompany the exact table and input identity.

`evaluate_fold_section(..., uncertainty=options)` restricts these calculations to
the declared test decision window. Nothing is fitted using training rows.
`TrialLedger.run(..., uncertainty=options)` registers the entire configuration
before calculation and reconciles the completed section against it. Changing a
metric, block, seed, confidence or sample is another attempt, not a style option.

Selections, caller-owned axes and partial exports reuse existing composition.
Dots represent point estimates and vertical segments percentile bounds; unavailable
intervals are annotated. Captions identify metric/confidence/block and explicitly
say not selection-adjusted. Chart exports must retain `estimate`, `lower`, `upper`
together; charts do not silently hide one side of an interval. Metric/estimand
mismatches cannot share an overlay. Manual figures remain exploratory.

## Verification and open decisions

The prespecified 24-seed iid/null and AR(1)-null checks passed their coarse
regression thresholds; see [executed evidence](UNCERTAINTY_VERIFICATION.md).
These limited simulations do not establish coverage for real contracts,
nonstationarity, long memory, irregular calendars, missing-not-at-random labels,
selected models, all block lengths, or all confidence levels.

The notebook fixture is synthetic: a single LCG stream starting at 81921 with
Box–Muller innovations, score AR coefficient .65, nuisance AR coefficient .6,
100 burn-in steps per model, then 200 observations per model. Targets are
`(beta * score + nuisance) / 100`, beta .2 for ES and -.15 for NQ. These names are
illustrative, not market data or fitted real instruments. Exact CSV bytes are bound
to evidence; the beta coefficients are not claimed to equal correlations.

Final holdout dates, nested selection, family/history completeness and correction
choice remain owner decisions. [FINAL_ASSESSMENT.md](FINAL_ASSESSMENT.md) records
what must be decided and enforced; it is not an implemented lock. Do not interpret
an interval excluding zero as a selection-adjusted promotion decision.
