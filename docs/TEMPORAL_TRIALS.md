# Declared folds and local trial history

Open `notebooks/temporal-trials.ipynb` from JupyterLab (`make notebook`), or:

```sh
uv run --frozen --group notebook jupyter lab --ip=127.0.0.1 notebooks/temporal-trials.ipynb
```

These APIs consume supplied predictions. They do not invoke the template's
regression-fitting `validate_walk_forward`, fit residualizers, or construct weights.
They remain descriptive and produce no significance or acceptance verdict.

## Declare and inspect folds independently

```python
from red_five.temporal import FoldSpec, audit_folds, evaluate_fold_section

fold = FoldSpec(
    "first",
    "2026-01-01T00:00:00Z",
    "2026-01-21T00:00:00Z",
    "2026-01-26T00:00:00Z",
    gap_seconds=0,
)
audit = audit_folds(signals, config, (fold,))
display(audit.summary.dataframe())
display(audit.membership.dataframe())
coverage = evaluate_fold_section("coverage", signals, config, plan, lock, fold=fold)
display(coverage.select().figure())
```

Windows use aware UTC-normalized times. Test membership is
`test_start <= decision_time < test_end`; `test_end` cannot exceed report `as_of`.
An audit accepts an explicitly ordered tuple of 1–20 folds, unique fold IDs and
nonoverlapping test decision windows. Train starts may differ for rolling windows;
keeping them equal yields expanding windows. No calendar, horizon-based gap or
fold schedule is silently inferred. Maximum gap is 365 elapsed days.

Each input row receives exactly one role **per fold**, in this precedence:

| Role | Meaning |
|---|---|
| `test` | Decision lies in the test window, regardless of label maturity |
| `outside_window` | Decision is before train start or at/after test end |
| `gap` | Training candidate decision is at/after `test_start - gap_seconds` |
| `unavailable_training_label` | Earlier candidate label is not available strictly before that cutoff |
| `missing_training_label` | Available training label is missing |
| `training` | Remaining candidate; known nonmissing label before cutoff |

The existing input contract ensures label end does not exceed label availability,
so this conservative availability purge also removes training labels crossing the
training boundary. Label availability exactly at the cutoff is excluded. Counts
are disjoint, not independent-observation estimates. Membership retains model,
instrument/contract, decision and label times without embedding raw scores/returns.
All groups, including those with no test rows, remain visible in the audit summary.
Membership expansion is capped at 100,000 rows. Summary/membership frames are
explicit notebook inspection APIs, not full-report components.

## Evaluate one fold section

Supported names: `standalone`, `coverage`, `quantiles`. Correlations/coverage use
only test rows, with missing/immature labels counted and metrics using labels
available by report `as_of`, not by test-window end. No train fit is required for
these supplied-score diagnostics; an empty test group appears in the audit rather
than receiving fabricated metrics. No-test results are unavailable.

Quantiles require `QuantileConfig(training_end=fold.test_start, ...)`. Boundary
fitting sees only retained training rows. **This is stricter than the original
score-only quantile API:** training observations with missing/unavailable labels
are excluded even though numerical return values are never used to fit cuts.
This explicit conservative population policy prevents a future supervised
transformation from quietly inheriting unpurged rows. It can change cuts through
eligibility; changing a retained return's numeric value cannot change cuts.
Test scores cannot alter training boundaries. Time-series contracts stay separate;
cross-sectional cuts remain per-model historical reference bins with per-date
test results. See [quantile semantics](QUANTILES.md).

Fold sections use existing immutable `SectionResult` schemas and composition:
exact tables, custom `PlotOptions`, caller-owned axes, model selection and verified
partial exports. Diagnostics retain the fold/audit, test keys, membership digest,
and `upstream_out_of_sample: unverified`; identity binds original inputs and fold.
Captions disclose the test window. Full report v1 does not gain fold evidence.

## Record attempts before computation

```python
from pathlib import Path
from red_five.quantiles import QuantileConfig
from red_five.trials import TrialLedger

ledger = TrialLedger(Path("build/research-trials.sqlite"))
result = ledger.run(
    "unique-attempt-001",
    "declared-family",
    "quantiles",
    signals,
    config,
    plan,
    lock,
    fold=fold,
    quantiles=QuantileConfig(
        fold.test_start, bins=5, minimum_training=15, minimum_bin=1
    ),
)
display(ledger.table().dataframe())
```

Registration stores family ID, section, fold/quantile policy, hashes of inputs,
configuration, analysis plan and lock, source identity and software versions.
Computation starts only after registration commits. Terminal events are
`computed`, `unavailable`, or `failed`; completed events retain exact section
evidence and are checked against the registered request. Failure records contain
only the exception class, never raw exception text. Invalid trial/family IDs or
objects that cannot be constructed are rejected before registration.

No update/delete/retry API exists. Reusing a trial ID raises before evaluation;
even identical reruns need a new attempt ID. Historical attempts are not inferred
from the current files. Interruptions or failed outcome publication may leave
`registered` entries; a failed publication raises and does not return success.
Inspect/reconcile unfinished entries manually before research decisions. The
notebook creates a fresh prefix for each new run and does not erase its journal.

SQLite from the Python standard library provides local transactions (5-second
lock timeout). A registration or outcome append obtains a write transaction,
verifies the existing hash chain and state transitions, and verifies the prospective
chain before committing. Concurrent duplicate attempts cannot both register.
Read-only snapshots do not create a database. Symbolic-link paths are rejected.
Event count and aggregate payload size are bounded at 1,000 and 16 MiB; limits
can leave an unfinished attempt if completion cannot be persisted. No automatic
rotation, deletion or outcome retry hides that failure. This is a bounded research
journal, not the planned Postgres signal registry or a shared-service deployment.

## What this does not establish

- Historical search completeness remains `unknown`; family IDs are declarations,
  not validated hypothesis families. A trial count is not a correction factor.
- Local timestamps show wrapper execution order, not that a human predeclared
  a choice before inspecting results. Unlogged notebooks remain possible.
- Hash chaining detects changed events and missing interior events, not a fully
  rewritten chain, deleted journal or removed tail without an external anchor.
  No signature, trusted clock, remote witness, immutable backup or recovery SLA.
- Only the supplied fold tuple is checked for nonoverlap. Separate exploratory
  requests may overlap deliberately and must not be pooled as independent tests.
- Nonoverlapping decision windows do not ensure nonoverlapping forward labels,
  independent dates/models or nested selection. Later folds may use earlier test
  labels only after they become eligible training observations; no final holdout
  lock or post-test training/embargo scheme is implemented.
- There is no certificate of upstream fold-local model fitting or residualization,
  predictive R² calibration, HAC/bootstrap uncertainty, winner selection, automatic
  Bonferroni/Holm choice, corrected p-value or acceptance decision.

Keep real journals outside public Git with restricted filesystem permissions and
a deliberate backup plan. They may contain sensitive model names and statistics.
SQLite patterns are ignored in this repository. The notebook's synthetic journal
is under `build/`; deleting build artifacts also deletes that research history.
Do not use a disposable location for consequential studies. CI exercises only
synthetic fixtures. See [verification](TEMPORAL_VERIFICATION.md).
