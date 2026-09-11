# Initial walking-skeleton verification

Authority: owner requested starting Red Five from the reviewed project plan.
Starting state: new local `python-data-quant` archetype; no existing destination.
Scope: descriptive signal evaluation and accounting for supplied weights.

## Rubric and stopping rules

Blocking: future observations influencing a metric, mixing instrument/contract
models, silent zero imputation, incorrect trade-side accounting, overwritten
evidence, or acceptance without a configured policy. Required evidence: adversarial
unit/integration cases, strict typing/lint, full suite, package build and
installed-wheel CLI smoke. No production approval is implied by self-review.

Ceiling: three evidence-changing verification rounds / two hours for the initial
slice, no paid compute or live financial data. Stop once the scoped behavior and
gates pass; keep later phases and domain choices explicitly open.

## Evidence

Executed locally on 2026-09-11 with Python 3.12.11:

- `uv sync --frozen --dev`: passed with the dependency lock.
- `make check`: Ruff lint/format passed; strict Pyright reported zero errors;
  77 tests passed, package coverage 91.34% against an 85% floor.
- `make build`: built the v0.1.0 source distribution and wheel.
- `make audit`: no known vulnerabilities or adverse statuses in 16 runtime
  packages; dependency license policy passed.
- README example `eval` and `verify`: passed for two instrument/contract models
  and supplied-weight accounting, with status `insufficient-evidence`.
- Installed the wheel in an isolated environment with hash-checked dependencies
  exported from `uv.lock`; both commands passed outside the source checkout.
  `cmp` confirmed wheel and source reports were byte-identical.

Synthetic fixture run identity:
`553527b5c19272f9e0d79a45c5d42774601bda285b9ec677a1013761fd4a41af`.
It binds input/configuration/analysis-plan bytes, package source and environment
identity, not this verification document. Reports are ignored build artifacts.

Adversarial cases in `tests/test_signal_evaluation.py` exercise future/missing
labels, future signals/weights, invalid numeric data, duplicates, separate model
histories, timezones, ties/extreme values, Decimal limits, trade sides and drift,
cost stress, concurrency, tampering and non-overwriting/symlink behavior.
The first full gate exposed typing errors and coverage below the floor. Typed
callbacks and smoke tests for retained template CLIs resolved them; no gate was
waived or reduced.

CI specifies quality, audit, build and isolated-wheel checks. Remote CI has not
run: this is a local project without a remote or deployment.

## Remaining gates

This is scoped development verification, not independent financial approval.
Inference/multiplicity policy, quantiles, effective breadth, marginal replay, NAV
chaining, calibrated execution, exchange calendars, Postgres recovery, scheduling
and representative production-load evidence remain unimplemented. Upstream
provenance is supplied, not authenticated. Checksums detect changes, not malicious
publishers. Local atomic publication is not a production recovery guarantee.
Full Phase 0 and production acceptance remain open in `PROJECT_PLAN.md`.
