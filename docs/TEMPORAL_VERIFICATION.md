# Temporal validation and trial tracking verification

Objective: independently inspect declared chronological folds, audit conservative
training-label purging, evaluate existing descriptive sections within each fold,
and retain local registered/computed/unavailable/failed trials. Scope is synthetic
development evidence, not financial approval, upstream model fitting or inference.

Starting revision: 912aa56, clean worktree. Blocking invariants: nonoverlapping
test decision windows; no training label unavailable at the declared boundary;
every input row accounted for; no test value moves training boundaries; model
identities preserved; trial registration precedes evaluation; failures retained;
no overwritten trial IDs or silent log mutation. Unknown historical searches and
upstream leakage remain explicitly unresolved.

Three evidence-changing passes, maximum two hours: hand-worked/adversarial fold
tests; transaction/provenance and notebook integration; full quality/build/kernel
and installed-package execution. Stop after scoped gates pass or domain authority
is required. No dependency, deployment, significance or live-promotion policy change.

## Executed evidence — 2026-09-11

1. Hand-worked/adversarial partitions: 30 temporal/journal tests. The synthetic
   first fold retains 19 training observations, excludes one boundary-available
   label and evaluates five observations per contract. Second fold retains 24.
   Every input appears exactly once per fold; gap and missing-label reasons are
   disjoint. Future test scores/returns and purged training values cannot move
   earlier quantile cuts. Tests also cover invalid windows/order/overlap, cutoff
   equality, cross-sectional date grouping, maturity, no-test windows and options.
2. Transaction/provenance checks: registration is observable before computation;
   exact section evidence is retained and reconciled with request hashes/fold/
   policy. Failed and unavailable trials remain visible, duplicate concurrent
   requests register once, KeyboardInterrupt leaves an unfinished registration,
   and unrelated results cannot complete a request. Corrupted/interior-deleted/
   oversized/wrong-version journals fail closed. Event capacity preserves existing
   history; completion-size failure raises without returning unlogged success.
   Symbolic-link paths fail; fold components export and verify using existing APIs.
3. Execution gates: `make check` passed Ruff lint/format, strict Pyright and all
   **194 tests**, **92.69% package coverage** (unchanged 85% floor). Temporal module
   statement coverage is 97%, journal 94%. `make notebook-check` executed all four
   notebooks in real local kernels; tracked notebooks have no outputs. `make audit
   build` found no known vulnerabilities/adverse statuses in 111 non-dev packages,
   passed license policy and built wheel/sdist. No dependency or lock change.
   The wheel was installed in the separate runtime environment and
   `tools/smoke_sections.py` ran from `/private/tmp`: original section/quantile
   exports plus fold auditing and registered journal completion passed. Existing
   CI invokes the extended smoke and all four notebooks.

Inspected an exported fold mean-return PNG: readable bin identities and values,
visible half-open window, signal units, omitted-row counts and unverified upstream
OOS/no-verdict caption. Exported fold evidence is partial; journal contents stay
local. Confirmed `build/temporal-trials.sqlite` is ignored. No raw market data,
credentials or journal output was added to Git.

Review corrections: strengthened terminal events to reconcile the result against
the original request; bounded aggregate journal payload before fetching blobs;
added explicit fold captions so graphs cannot hide their sample windows. Strict
typing caught a private cross-module sealing helper and untyped test stub; the
helper now has a shared module interface and tests retain full typing. Formatting
checks caught unformatted documentation examples before the final gate. No global
typing/coverage threshold or safety/release policy was relaxed.

## Exit and remaining uncertainty

Stop: scoped gates passed. No production or financial approval is claimed. The
development API cannot certify upstream model fitting, complete historic searches,
pre-result human choices, independence of overlapping labels, final assessment
isolation or an appropriate multiplicity correction. Local hash chaining cannot
detect tail removal/full replacement without an external anchor. Real storage
needs restricted permissions, backup and access/retention/recovery ownership.
No database server, remote witness, infrastructure deployment or verdict logic.
Jupyter warns its local loopback kernel TCP is unencrypted; no shared/public server
was started. Local commits have not yet run in remote CI. The current limits and
deferred decisions are maintained in TEMPORAL_TRIALS.md, ADR 0005 and the plan.
