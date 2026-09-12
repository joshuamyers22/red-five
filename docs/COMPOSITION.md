# Notebook composition

Run `make notebook` to open `notebooks/composition-cookbook.ipynb`. The original
full-report notebook remains available; `make notebook-check` executes all five,
including the [quantile notebook](../notebooks/quantile-diagnostics.ipynb) and
[fold/trial notebook](../notebooks/temporal-trials.ipynb). Fold evaluators return the
same section API with explicit window/provenance captions; see [fold contracts](TEMPORAL_TRIALS.md).

## Independent sections

`evaluate_section(name, signal_bytes, config_bytes, plan_bytes, lock_bytes,
weight_bytes=...)` returns an immutable `SectionResult`, without a full report,
file write or unrelated calculation. Supported names:

- `standalone`: per-group correlations and observation counts; no weights.
- `coverage`: counts only; no correlations or weights.
- `economics`: supplied-weight interval accounting; weights are mandatory and
  checked against the signal panel. No standalone correlations are calculated.
- `quantiles`: fixed training-reference bins, counts/means/spreads/monotonicity;
  requires `quantiles=QuantileConfig(...)`, never weights. See [quantile policy](QUANTILES.md).
- `uncertainty`: conditional block-bootstrap bounds/standard errors; requires
  `uncertainty=BootstrapConfig(...)`, never weights. See [method and limitations](UNCERTAINTY.md).

All use existing production numerical functions. Input contracts, label maturity
and availability checks still apply. Unsupported sections and invalid inputs raise
`ContractError`; no successful or partly written result is emitted for that failure.
Valid sections record `computed` or `unavailable`, `scope: partial`, `verdict: null`
and the names of unrequested sections. A computed section is not full eligibility.

`view.section(name)` extracts the same API from an existing `ReportView` with no
reevaluation for sections actually present (v1 full reports have no quantiles).
Values match independent evaluation on identical inputs; IDs may
differ because extracted sections retain full-report lineage. Independent section
IDs bind exact values and input, configuration, plan, lock, code and software
identity. Reuse a result object across notebook cells; styling never reevaluates it.
`SectionResult.content` is versioned JSON; `load_section(path)` validates saved
section bytes. Hashes detect change, not publisher authenticity.

## Display and customize

```python
from red_five.composition import PlotOptions, Selection

panel = view.section("standalone").select(
    Selection(model_ids=("ES-model",), columns=("model_id", "rank_ic"), precision=3)
)
display(panel)  # Formatted HTML; selected/omitted counts remain visible
display(panel.table())  # Exact, unrounded Polars values
display(panel.figure(options=PlotOptions(colors=("#009E73",), metrics=("rank_ic",))))
```

Selections accept immutable tuples of model, instrument, contract, portfolio or
decision-time identities, plus columns and stable sorting (`sort_by`, `descending`).
Decision times are exact stored strings and only work on tables with that axis.
Nulls sort last; decimal accounting text sorts numerically. `precision` changes
HTML formatting only. Filtering an existing aggregate row does not recompute its
correlation: new sample dates/eligibility require new validated inputs/configuration
and a new `evaluate_section` call. A view states how many rows were omitted;
unavailable rows are retained unless excluded by the explicit selection.

`panel.plot(ax=your_axes, options=...)` draws into caller-owned axes and returns
them. Subplot grids and arbitrary notebook layout remain yours. It never calls
`show()`, closes figures, changes unrelated axes or changes source values. Occupied
axes require `overlay=True` and matching plot kind, group identities/order, target,
horizon, calendar and scales; quantile overlays also require identical bin bounds,
and uncertainty overlays require matching metrics/estimands.
Unsupported overlays fail. Use `label_prefix` to
identify overlay series. Manual changes after plotting are exploratory: the library
cannot guarantee semantic compatibility after arbitrary caller edits.

`PlotOptions` supports size/DPI, hex colors, markers, font size, title/x-label,
legend visibility, metric selection, linear/symlog scale and y limits. Custom scales
and limits visibly disclose possible clipping. Options are serializable and bounded.
Colors/markers cycle; units and numerical values never change. Styles are temporary;
rendering remains serial within a process. For additional Matplotlib annotations
or layout controls, edit the returned Figure/Axes directly, with the export caveat
below. Existing `view.figure()` and full-report exports remain supported.

## Partial and custom exports

`panel.export(path)` exports just its table; add `kind="correlations"` (or another
supported kind), `options=...`, and `page=...` for one figure page plus exact table.
`export_components([Component(panel, kind, options), ...], path)` exports a chosen
ordered collection. A component with `kind=None` does not invoke plotting. Section
tables remain limited to 200 rows and chart pages to 20 groups, as before.
For a chart export, selected table columns must include all plotted metrics so
the companion CSV remains usable; otherwise export fails with a clear error.

Each bundle includes source section JSON, CSV, requested SVG/PNG pages, HTML and a
`red-five-components/v1` manifest. It records selection, display options, source IDs,
artifact hashes and partial scope. `red-five verify-bundle path` accepts full or
partial manifests; partial verification also reconciles CSV to its source selection.
A partial bundle has no single full-report run ID, so the CLI reports `run_id: null`.
Publication remains non-overwriting and completion-manifest based. There are at
most 20 components, 16 MiB per file, 32 MiB per bundle and cooperative time checks.

Standard component exports replay recorded options, not arbitrary manual edits to
returned figures. Custom subplot-layout serialization, capture of manual artists,
widgets, advanced formatter callbacks and later analytical sections remain future
work. You may save an exploratory Matplotlib figure directly, but that is not a
verified Red Five bundle. Keep real data and notebook outputs out of public Git.
