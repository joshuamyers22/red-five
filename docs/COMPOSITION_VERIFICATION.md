# Notebook composition verification

Scope: independent standalone/coverage/economics sections, immutable display
selections, configurable caller-owned plots, and verifiable partial exports.
Preserve existing full-report APIs and numerical calculations.

Blocking invariants: no unrelated computation for a requested section; no weights
required for standalone/coverage; exact agreement with full-report sections;
no presentation-side recalculation or hidden exclusions; caller axes, source hashes
and unrelated notebook styling remain intact; partial exports cannot imply full
eligibility. Validate malformed options, empty selections, tampered evidence,
publication failure, and notebook/package execution as well as happy paths.

Ceiling: three evidence-changing passes / two hours, synthetic data only. Stop on
passed scoped gates or a genuine new authority requirement. No deployment or
financial approval. Execution results will be recorded after verification.

## Executed evidence — 2026-09-11

- `make check`: Ruff lint/format and strict Pyright passed; 130 tests passed with
  92.04% package coverage against an unchanged 85% floor.
- `make notebook-check`: both the original full-report notebook and new composition
  cookbook executed in real local Jupyter kernels. Tracked notebooks remain free of
  outputs; executed copies are ignored under `build/`.
- `make audit build`: no known vulnerabilities/adverse statuses in 111 non-dev
  packages, license policy passed, wheel and source distribution built. No new
  dependency or lock change was needed.
- Installed the wheel in the separate runtime environment and ran
  `tools/smoke_sections.py` from outside the checkout. Independent section
  evaluation, model selection, custom chart export and partial verification passed.
  CI now runs this smoke test and both notebooks.
- Inspected the cookbook's two-panel figure: distinct model/coverage axes, visible
  group identities, section captions and no overlapping plot areas.
- Adversarial tests establish calculation isolation, full/partial value parity,
  immutable source bytes, exact tables, null/empty selections, global-style and
  caller-axis preservation, incompatible overlay rejection, malformed options,
  CSV/source reconciliation, source/manifest tampering and partial-write cleanup.

The export review found that custom table columns could omit plotted metrics;
exports now reject that configuration and a regression test covers it. Type checking
also caught a parser-variable shadowing error before the full quality gate passed.
No coverage or global typing threshold was relaxed.

## Explicit follow-up scope

Optional widgets, automatic capture/replay of arbitrary manual Matplotlib edits,
custom subplot-layout serialization, failed-section history, later analytical
sections, hard worker resource limits and production recovery remain unimplemented.
Manual axes edits can invalidate compatibility assumptions; caller-owned figures
remain exploratory unless exported using a recorded component specification.
Kernel transport is local loopback TCP (the kernel warns it is unencrypted); no
shared/public server was started. Remote CI has not been run for these local edits.
