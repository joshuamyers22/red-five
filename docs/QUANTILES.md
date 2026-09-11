# Quantile diagnostics in a notebook

Open `notebooks/quantile-diagnostics.ipynb` from `make notebook`, or launch it directly:

```sh
uv run --frozen --group notebook jupyter lab --ip=127.0.0.1 notebooks/quantile-diagnostics.ipynb
```

Compute this section independently of correlations, weights and full reports:

```python
from red_five.quantiles import QuantileConfig
from red_five.sections import evaluate_section
from red_five.composition import PlotOptions, Selection

result = evaluate_section(
    "quantiles",
    signals,
    config,
    plan,
    lock,
    quantiles=QuantileConfig(
        training_end="2026-01-21T00:00:00Z",
        bins=5,
        minimum_training=20,
        minimum_bin=3,
    ),
)
panel = result.select(Selection(model_ids=("ES-model",), precision=4))
display(panel.table())
display(panel.figure(options=PlotOptions(colors=("#0072B2",))))
display(panel.figure("quantile_counts"))
display(result.diagnostics)
```

`panel.plot(ax=...)`, selections, table-only exports and `export_components` use
the same [composition contract](COMPOSITION.md). Styling never recalculates
results. Plotted metrics must remain in the companion exported table. The Polars
table is also available for custom visualizations. A full v1 report does not
contain this evidence: `view.section("quantiles")` fails explicitly; use the
independent evaluator. Existing section v1 files remain supported; quantile
sections use `red-five-section/v2` with digest-bound fitting metadata.

## Declared calculation

- Fit using score observations with `decision_time < training_end`; equality
  belongs to evaluation. The cutoff must not exceed the report's `as_of`.
  Availability validation still applies. Training returns are not read for
  fitting, so immature training labels do not exclude an otherwise known score.
- In time-series mode fit separately for each model/instrument/contract; the
  input contract requires a separate model for each instrument/contract. There
  is no stitching across rolls or pooling unrelated score scales.
- In cross-sectional mode fit the model's historical panel scores, then evaluate
  each model/date separately. Scores within that model must be comparable.
  These are **fixed historical reference bins**, not per-date equal-count ranks.
  Observation weighting during boundary fitting is uniform; dates with more
  instruments contribute more scores. This is not portfolio weighting.
- For sorted training scores of size `n` and requested bins `k`, choose cut `j`
  at one-based rank `ceil(j*n/k)`, for `j=1,...,k-1`. Deduplicate cuts and discard
  those equal to the training maximum. Bins are right-closed; equality goes to
  the lower bin. No jitter or arbitrary tie splitting. Effective bin count can
  be less than requested, including one with an extreme tied distribution.
- Outer bounds are unbounded. Count evaluation scores outside the observed
  training range and put them in tail bins; never refit using them.
- Too few training observations or constant training scores produce unavailable
  results (placeholder bin zero), never a test-fitted fallback. Empty bins stay
  visible. Training-only time-series models retain empty evaluation bins;
  cross-sectional models with no evaluation dates appear only in fit metadata.
- Means use only nonmissing labels available by `as_of`, and require the declared
  `minimum_bin`. Report eligible, immature, missing-mature and total counts.
  Minimum counts are availability thresholds, not independence or power claims.
- Spread is highest-bin minus lowest-bin mean, available only with two effective
  bins and both tail means. Middle bins may still be unavailable. It is not a
  weighted long/short portfolio return. Monotonicity requires all effective-bin
  means and reports flat, nondecreasing, nonincreasing or nonmonotonic. Overflow
  remains null with a numerical-degeneracy reason.

Each tidy table row represents one evaluation group/bin. Spread and monotonicity
repeat within the group for convenient display; never sum those repeated values.
The notebook shows a unique group-level summary. Boundaries, fitting counts,
extrema, policy and exclusion reasons are stored with immutable section evidence.
Null means have an unavailable annotation, not a zero-height observation.

## Limits

This is descriptive, single-cutoff software, not confirmatory financial evidence.
No p-values, confidence bands, effective breadth, learned weights, decision verdict
or automatic sign reversal. Overlapping labels and serial/cross-model dependence
remain unresolved. A timestamped holdout does not prove upstream model fitting was
out of sample. No automatic purge, walk-forward refit, contract-roll stitching or
final assessment lock exists yet. Changing bin policy after inspecting outcomes
is another research trial, not cosmetic customization. The existing section
limit is 200 output rows (including group × bin expansion); larger analyses fail
closed rather than silently truncate. Figures page at 20 rows.

See [verification](QUANTILE_VERIFICATION.md) and [ADR 0004](adr/0004-fixed-quantile-bins.md).
