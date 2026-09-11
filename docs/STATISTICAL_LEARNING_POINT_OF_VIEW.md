# Statistical-Learning Point of View

## Status and intent

This is an opinionated starting position for empirical quantitative work. It is
not a deterministic rulebook or a claim that one method is always correct. Make
the project's prior beliefs visible, then challenge them with a clearer
hypothesis, stronger evidence, or a real operating constraint.

An analysis may depart from a preference below when its owner records why, the
risk introduced, and what evidence will decide whether the choice works.
Security, legal, data-rights, and production-safety obligations apply
independently.

## The point of view

- Begin with the decision, prediction time, target availability, action, horizon,
  and economic or practical utility. Track model loss and decision outcomes
  separately; a better statistical score need not produce better net results.
- Prefer an observable, attributable first objective with guardrail metrics.
  State where it is only a proxy; keep risk appetite and policy outside the model.
- Start with a naive or domain heuristic and an interpretable statistical
  baseline. Polars is the default tabular engine and Statsmodels is the default
  statistical engine, but neither default chooses the appropriate model.
- Earn complexity through repeated out-of-sample improvement after uncertainty,
  costs, impact, capacity, latency, failure behavior, and maintenance burden.
  Simplicity is a baseline and operating advantage, not an ideology.
- Treat sample construction, target-aware cleaning, imputation, normalization,
  feature selection, dimension reduction, hyperparameter search, ensembling,
  calibration, and threshold selection as learned parts of the procedure. Fit
  them on the training portion inside every evaluation fold.
- Treat unsupervised use of future distributions as a review question too. Its
  acceptability depends on the estimand and the process available at prediction
  time, not merely on whether labels were used.
- Separate development and selection from final assessment. Once an evaluation
  influences the procedure, it is development evidence rather than an untouched
  final test.
- For ordered financial data, generally prefer expanding, rolling, or blocked
  time-forward evaluation with point-in-time inputs and label purging or embargo
  where information sets overlap. Random folds remain possible when the estimand
  and sampling mechanism make exchangeability defensible.
- Treat dependence, nonstationarity, feedback, crowding, and changing costs as
  risks to investigate, not universal axioms. Examine decision-relevant slices
  and report uncertainty and dispersion rather than only a pooled mean.
- Make data contracts, feature semantics, units, clocks, missingness, and
  provenance testable. Reuse calculation code or prove parity among research,
  batch, replay, and live paths. Version mutable joins and monitor skew.
- Define data-quality, drift, staleness, fallback, rollback, refit, and retirement
  behavior before consequential use.
- Bind retained evidence to immutable data identity, code, environment, analysis
  plan, candidate space, folds, baselines, and individual out-of-sample
  predictions. Preserve disappointing candidates where policy permits.

An artifact proves what was run; it does not prove that the source data are
truthful, the estimand is meaningful, the model is identified, or the decision
is safe. Consequential use calls for independent data, statistical, software,
and operational review.

## Review prompts

For correct statistical implementation, use
[the Bayesian regression guide](BAYESIAN_REGRESSION_IMPLEMENTATION.md).
It emphasizes regression specification, priors, numerical computation, and
verification, without drawing conclusions about applications to finance.

1. What decision changes, and what is the cost of a wrong answer?
2. Is the objective observable and aligned with net value after costs?
3. Which heuristic and statistical baselines must the candidate beat?
4. Which steps learned from data, and were they fit inside each fold?
5. Which evidence was used for iteration, selection, and final assessment?
6. Could every feature, universe member, label, and revision have been known at
   prediction time?
7. How sensitive is the result to time, regime, sample, specification, costs,
   and researcher choice?
8. How are research and production calculations compared and rolled back?
9. What evidence would falsify the thesis or trigger retirement?
10. Which preference here was rejected, and why is that sensible for this work?

## Sources

This view draws on Hastie, Tibshirani, and Friedman's [*The Elements of
Statistical Learning*](https://hastie.su.domains/ElemStatLearn/printings/ESLII_print12_toc.pdf),
the [Headlands practitioner review](https://blog.headlandstech.com/2022/02/16/elements-of-statistical-learning-8-10/),
and Google's [*Rules of Machine Learning*](https://developers.google.com/machine-learning/guides/rules-of-ml).
These sources inform judgment; they do not replace project evidence.
