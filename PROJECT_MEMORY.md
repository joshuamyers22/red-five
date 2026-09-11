# Red Five Project Memory

This is a bounded retrieval index for durable project knowledge. It is not an
activity log, task tracker, transcript, or source of truth. Verify every entry
against the linked implementation, test, issue, or decision record before acting.

Do not record secrets, personal data, client data, hidden reasoning, or other
restricted material. Consult an existing key before editing and update it in
place. Remove stale entries and resolved work instead of preserving a narrative;
Git history provides the audit trail.

## Durable constraints

| Key | Constraint | Evidence | Last verified |
|---|---|---|---|
| `external-models` | Residualization and weighting remain external; consume supplied outputs and provenance. | `docs/adr/0001-external-models-and-initial-slice.md` | 2026-09-11 |
| `model-unit` | Time-series diagnostics treat each instrument/contract as its own model. | `src/red_five/signal_io.py`, `tests/test_signal_evaluation.py` | 2026-09-11 |
| `no-verdict` | Reports remain descriptive, insufficient-evidence, with no acceptance verdict. | `STATISTICAL_ANALYSIS_PLAN.md`, `src/red_five/evaluation.py` | 2026-09-11 |

## Accepted decisions

| Key | Decision and rationale | Evidence | Last verified |
|---|---|---|---|
| `initial-adapter` | Bounded CSV/config files and non-overwriting local JSON precede Postgres. | `docs/adr/0001-external-models-and-initial-slice.md` | 2026-09-11 |
| `interval-economics` | Decimal accounting consumes pre-trade/target weights, total returns and explicit costs; no NAV chaining. | `docs/INPUT_CONTRACTS.md`, `src/red_five/economics.py` | 2026-09-11 |

## Non-obvious current state

| Key | State worth retrieving later | Evidence | Last verified |
|---|---|---|---|
| `initial-evidence` | Local quality/build/audit and installed wheel passed; pushed baseline c56a955 passed GitHub CI. Quantile edits remain locally verified; production approval is outstanding. | `docs/INITIAL_VERIFICATION.md`, `docs/QUANTILE_VERIFICATION.md` | 2026-09-11 |
| `template-utilities` | Inherited regression/dataset utilities are separate from signal evaluation. | `docs/TEMPLATE_GUIDE.md`, `tests/test_template_cli_smoke.py` | 2026-09-11 |
| `identity-limit` | Installed wheels use a source digest; lock hashing does not attest the whole installed environment. | `REPRODUCIBILITY.md`, `src/red_five/reporting.py` | 2026-09-11 |
| `notebook-views` | `make notebook` uses the locked notebook group; immutable views serve notebook and exports without recomputing metrics. | `notebooks/signal-report.ipynb`, `docs/adr/0002-notebook-reporting.md` | 2026-09-11 |
| `render-boundary` | Rendering is serial, limited to 200 groups/intervals and requires manifest verification; real bundles stay private. | `docs/REPORTING.md`, `tests/test_visualization.py` | 2026-09-11 |
| `notebook-composition` | Independent sections, immutable selections/options, caller-owned axes and partial exports are implemented. `make notebook` opens the cookbook. | `docs/COMPOSITION.md`, `tests/test_composition.py`, `docs/COMPOSITION_VERIFICATION.md` | 2026-09-11 |
| `quantile-boundaries` | Independent section v2 fits fixed pre-cutoff score bins, separately per time-series contract; CS uses per-model historical cuts and per-date evaluation. New notebook exposes means/counts/spread/monotonicity and partial exports; no inference or v1 full-report quantiles. | `docs/QUANTILES.md`, `tests/test_quantiles.py`, `docs/QUANTILE_VERIFICATION.md` | 2026-09-11 |
| `fold-audits` | Explicit nonoverlapping test windows, every-row roles and conservative training-label purge feed independent descriptive fold sections; numeric models remain external and upstream OOS unverified. | `src/red_five/temporal.py`, `docs/TEMPORAL_TRIALS.md`, `tests/test_temporal_trials.py` | 2026-09-11 |
| `local-trial-history` | SQLite journal registers before evaluation; preserves computed/unavailable/failed/unfinished attempts, rejects duplicate IDs, verifies chain/request linkage. Local history is not complete or externally anchored; fourth notebook demonstrates it. | `src/red_five/trials.py`, `docs/TEMPORAL_VERIFICATION.md` | 2026-09-11 |

## Verified traps and failed approaches

| Key | Symptom and cause | Evidence or reproducer | Last verified |
|---|---|---|---|
| `mature-only` | Even populated future returns must not influence metrics. | `tests/test_signal_evaluation.py::test_future_labels_do_not_influence_metrics` | 2026-09-11 |
| `immutable-output` | Changed evidence requires a new path; identical reruns are idempotent. | `tests/test_signal_evaluation.py::test_immutable_publication_and_integrity` | 2026-09-11 |

## Open threads

| Key | Unresolved question or next evidence | Owner | Review by |
|---|---|---|---|
| `decision-policy` | Select hypothesis family, dependence-aware inference, holdout and thresholds before any verdict. | Josh / research | Before inference slice |
| `next-slices` | Upstream fold-local provenance, nested/final assessment policy and dependence-aware uncertainty remain open; local fold audits/trial journaling do not close these gates. Breadth, paired marginal replay and production registry follow. | Unassigned | Next phase planning |
| `reporting-followup` | Validate representative panel size, narrow/print accessibility and production artifact recovery before expanding local rendering limits. | Engineering / research; `docs/REPORTING.md` | Before production reporting |
| `composition-followup` | Optional widgets, arbitrary layout/artist serialization and failed-section history remain future work; standard exports replay recorded options only. | Engineering / research; `docs/COMPOSITION.md` | When requested |
| `production-gates` | Data licensing, calibrated costs, workload budget, recovery and monitoring ownership remain open. | Unassigned | Before deployment |
