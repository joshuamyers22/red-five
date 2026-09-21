# Transfer alignment verification

Objective: implement the Dropbox plan's first offline alignment slice in Red Five.
Authority: TRANSFER_COEFFICIENT_PLAN.md and TRANSFER_INTEGRATION.md.
Baseline: c6bae32d40805f185fed1e8b5864dcb183fdbfc5; clean clone.
Risk: mathematical research code; no production or domain approval implied.

## Rubric and stopping rule (declared before implementation)

- Blocking: analytic diagonal/correlated/orthogonal fixtures, sign/scale/permutation
  invariants, Pearson counterexample and no input mutation.
- Blocking: invalid identity, timestamps, units, dimensions, finite/PD/conditioning
  failures; no silent covariance repair or matrix inverse.
- Blocking: synthetic CLI, immutable publication, retry/conflict/race, tampering,
  input/config/plan identity changes; old signal-report verification still works.
- Blocking: frozen install, existing quality gate, build and installed-wheel smoke.
- Limit: three evidence-changing verification passes and 90 minutes; stop once
  thresholds pass or record unresolved findings. Human math and independent
  end-to-end approval remain required before consequential use.

## Executed evidence

Verified locally on 2026-09-20:

| Pass | New evidence | Result |
|---|---|---|
| 1 | Analytic fixtures, random SPD identities, invalid snapshot contracts, repeatability and publication races | 34 focused transfer tests passed |
| 2 | Schema review and full existing quality gate | `make check build`: lint/format, strict Pyright, 259 tests passed, 92.58% package coverage; wheel and sdist built |
| 3 | Frozen runtime installation and installed wheel outside checkout | Transfer calculation/verification, original signal eval/verify/render/bundle verification, and section export smoke all passed |

`uv sync --frozen --dev` installed from a fresh clone. A separate runtime environment
was created under ignored `build/wheel-smoke`, installed with hash-checked runtime
requirements exported from the unchanged lockfile, then given the built wheel.
Commands were executed from outside the checkout. Transfer report identity:
`d8ac8362c0a7d144922d04eed8199d170588dd3dc3f3a0ba92a444e0dded351a`.
Synthetic outputs remain ignored under `build/`. CI's installed-wheel smoke now
includes the transfer commands; remote CI has not been verified in this session.
No notebook code changed; existing rendering/section tests and installed smoke
passed. Full notebook kernel execution was not repeated locally.

`make audit` found no known vulnerabilities/adverse statuses in 111 non-dev packages;
the dependency license policy passed. Manifest, lockfile and license were unchanged.
`git diff --check` and local Markdown-link checks passed.

## Review findings and disposition

- Preserve covariance rather than silently choosing one triangle: exact symmetry
  is required even for differences below the material-asymmetry tolerance. This
  narrower first-slice contract is documented and tested.
- Match actual source identity: flat package modules ensure the existing source
  digest includes the new implementation; no parallel hashing/publishing system.
- Reject resealed inconsistent evidence: validation checks declared status, policy,
  metadata, numerical identity and diagnostics as well as the existing content hash.
  Hashes remain integrity checks, not upstream authenticity or domain approval.
- Static analysis found test-array typing and redundant-cast issues; those were
  corrected without relaxing the strict type or coverage gates.

## Exit and remaining uncertainty

Stop: local first-slice rubric passed. No independent mathematical or end-to-end
review is claimed; these remain required before consequential use. No production
release/deployment, real-data validation, paired Sharpe/bootstrap calibration,
PSD support, replay, final-assessment access control, representative performance
benchmark or storage-recovery evidence is supplied by this change. The inherited
local publisher retains its documented production-durability limitation.

Durable scope and architecture are linked from PROJECT_MEMORY.md,
TRANSFER_INTEGRATION.md and TRANSFER_COEFFICIENT_ANALYSIS_PLAN.md.

## Owner approval for main — 2026-09-20

The owner approved implementation commit `5530c38` and explicitly requested a push
to `main` with updated documentation. Approval covers the delivered offline research
slice. The independent mathematical/end-to-end and production gates above retain
their recorded status. The merge follow-up updates documentation only; numerical
source, tests, dependency lock and CI configuration are unchanged from the verified
implementation. Local Markdown links, documented example values and diff whitespace
were checked for this follow-up. The prior quality/build/audit evidence applies to
the unchanged implementation; remote CI results are not claimed here.
