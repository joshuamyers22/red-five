# Final assessment — decisions still required

Status: specification checklist, **not an implemented holdout lock**. No real-data
assessment window or owner policy has been selected from the synthetic examples.
This document does not change release, approval or access-control policy.

Before consequential evaluation, Josh/research must declare:

1. Dataset/version, eligible instruments/contracts, target and horizon; trusted
   upstream fold-local fitting/residualization provenance.
2. Development/selection windows and the untouched final-assessment start/end,
   with label maturity, overlap purge, minimum history and calendar rules.
3. The primary estimator and practical utility hurdle; uncertainty method,
   dependence/block/lag rationale, level, sensitivity and failure handling.
4. Hypothesis family and retained historical trial/search record, including sign,
   horizon, universe and estimator variants; unknown history cannot imply a
   known correction denominator. Select/justify any correction explicitly.
5. Who may reserve/unseal the assessment, what independent review is required,
   where protected history is retained, and what invalidates or reopens a study.

Implementation acceptance after those choices:

- Commit a versioned specification and immutable data/reference identity before
  assessment. Capture a trusted external timestamp/witness, not just local hashes.
- Prevent development/selection APIs from accessing the reserved assessment
  window under that study. Do not call an advisory date field an access lock.
- Reconcile all trial/specification identities before an authorized assessment;
  preserve unsuccessful/unavailable attempts and an externally anchored audit.
- Treat an outcome-viewed specification change as a new study, not a reset.
  Design crash/retry states so failures cannot permit duplicate unsealing or hide
  a prior result. Exercise concurrent/recovery and access-control tests.
- Keep acceptance predicates unset until all numerical, practical, provenance and
  review requirements are satisfied; no automatic live promotion.

Current fold windows, trial registration and conditional intervals are useful
development evidence, but cannot enforce these properties on their own. Local
files can be read outside the wrapper and the local journal can be truncated or
replaced without an external anchor. Real final-assessment controls require the
declared authority/storage model; they are intentionally not simulated here.
