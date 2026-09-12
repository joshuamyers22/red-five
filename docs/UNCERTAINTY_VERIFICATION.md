# Conditional uncertainty verification

Starting revision e0463a4; clean worktree. Objective: independent notebook intervals
for per-contract temporal correlation or mean per-date cross-sectional IC using
explicit moving-block resampling. No automatic holdout, multiplicity or verdict.

Blocking: paired rows stay paired; dates remain the CS sampling unit; unavailable
time points cannot be silently compressed; block/time/seed/confidence settings are
bound to evidence; degenerate replicates are not dropped; model isolation, prior
sections and trial history remain compatible. All claims are conditional on the
declared dependence/regular-grid assumptions and unverified upstream provenance.

Three passes / two hours: hand-worked and adversarial numerical tests; prespecified
simulation and integration checks; full quality/build/kernel/installed-wheel gates.
Simulation rubric: 24 fixed null seeds per iid and AR(1) scenario, n=256, 200
replicates, 95% intervals; coverage at least 18/24 in each (coarse regression check,
not production calibration). AR(1) rho=.8 block-16 median interval width must
exceed block-1 width by at least 25%. No threshold tuning after viewing results;
failures remain findings. No new dependency or release/safety policy changes.

## Executed evidence — 2026-09-11

- `make check build`: Ruff lint/format, strict Pyright, **225 tests passed**,
  **92.98% package coverage** against the unchanged 85% floor; wheel/sdist built.
  The uncertainty module has 99% statement coverage. No typing or coverage
  threshold was weakened.
- Thirty uncertainty tests cover independently recomputed NumPy paired-block
  percentile/SD values, repeatability and group isolation, rank/date semantics,
  missing/immature/irregular/short/constant/perfect-correlation cases, label-span
  and workload guards, undefined-replicate retention, malformed policy/evidence,
  table/plot/export round trips, and registered fold uncertainty. Original
  quantile, temporal, trial and full-report tests remain passing.
- Prespecified null simulations: iid coverage **24/24**, AR(.8) coverage **21/24**;
  median AR block-16/block-1 interval width ratio **1.7858284056362073**. The
  declared thresholds (at least 18/24; ratio at least 1.25) passed without changing
  seeds, thresholds or methodology. Observed AR coverage is below nominal 95%;
  this small simulation is a coarse regression check, not evidence of general
  nominal coverage or real-data approval.
- `make notebook-check` executed all five notebooks in actual local Jupyter
  kernels. Source notebooks have no saved outputs; executed copies and journals
  stay ignored under `build/`. Inspected the exported ES interval: point/bounds,
  model identity, window, explicit temporal estimand, policy and no-selection-
  adjustment caption remain visible. No p-value or acceptance marker appears.
- `make audit build`: no known vulnerabilities/adverse statuses in 111 non-dev
  packages; license policy passed. No dependency or lockfile changes.
- Reinstalled the wheel into the separate runtime environment, then ran
  `tools/smoke_sections.py` from `/private/tmp`. Existing section exports and
  journal checks, plus registered fold uncertainty and verified interval export,
  passed outside the checkout. CI invokes the extended smoke and all five notebooks.

The three evidence perspectives were numerical/adversarial fixtures, prespecified
simulations plus artifact/trial integration, then package/kernel/quality execution.
Review corrections: respect the configured TS minimum observation count; require
minimum empirical-tail resolution; retain metric/estimand overlay compatibility;
reject inconsistent policy/status/bound tables and exports that hide bounds.
A period-four CS test sequence with length-eight blocks correctly produced a
degenerate bootstrap; the availability fixture was changed to a nonmatching
period-seven sequence instead of bypassing degeneracy checks. Static typing caught
unknown NumPy test-array types, and formatting caught long caption/doc lines;
all were corrected before the final quality gate.

## Exit and remaining limits

Stop: scoped development gates passed. Intervals remain conditional, not
selection-adjusted. Regular-grid assumptions, missingness, block adequacy,
noncircular edge weights, nonstationarity, simultaneous-model dependence and
finite-sample/Monte Carlo calibration remain limitations. No HAC/quantile-spread
inference, automatic calendar adapter, p-values, real-data holdout selection,
protected assessment access or consequential verdict has been implemented.
FINAL_ASSESSMENT.md is an owner-decision and future-acceptance checklist only.

Jupyter warns its loopback kernel TCP is unencrypted; no shared/public server was
started. All fixtures are synthetic. Current commits are locally verified, not yet
run in remote CI or deployed. Primary method references and full assumptions are
recorded in UNCERTAINTY.md and ADR 0006; open decisions remain in the plan/memory.
