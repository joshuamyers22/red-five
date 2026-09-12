# Notebooks

Start with `composition-cookbook.ipynb`: `make notebook` opens independent section
evaluation, styling, caller-owned subplots and partial exports. See
`docs/COMPOSITION.md` for the API and display-versus-evaluation boundary.

Open `quantile-diagnostics.ipynb` for independent frozen-bin means, coverage,
spread/monotonicity tables and model-specific plots. See `docs/QUANTILES.md` for
the explicit cutoff, tie policy and descriptive-only limitations.

Open `temporal-trials.ipynb` for fold audits, row membership, individually registered
fold sections and retained failure history. The local journal persists under
`build/`; reruns create new attempts rather than overwrite existing trials. See
`docs/TEMPORAL_TRIALS.md` for purge rules and research-history limitations.

Open `uncertainty.ipynb` for independently usable conditional interval charts and
tables, explicit block/seed/time-grid options, and registered estimator variants.
No correction or locked final assessment is inferred; see `docs/UNCERTAINTY.md`.

For the original full-report workflow, open `signal-report.ipynb`,
then run all cells. It generates a synthetic report through production functions,
displays the shared report view and exports a verified bundle under ignored
`build/`. To inspect your own report, use `load_report(path)` instead of the
synthetic-generation cell. `view.table()` returns a Polars frame;
`view.figure(kind, page=0)` returns an independent Matplotlib Figure.

Launch through `make notebook` so the kernel uses the project's locked environment.
Do not expose Jupyter beyond loopback or disable its authentication. CI uses
`make notebook-check` to execute all five; tracked notebooks contain no cell outputs.

Use notebooks for exploration and communication. Import production calculations
from `src/`; do not maintain a second implementation in cells. Clear sensitive
outputs and large data before committing. Promote stable behavior into typed
modules and tests before relying on it operationally.

Use Polars for tabular exploration so notebook and production semantics remain
aligned. A pandas-only visualization or dependency must stay at an explicit
interop boundary rather than becoming a second transformation pipeline.

Use Statsmodels for statistical inference and regression. Import a reviewed
modeling function from `src/` once an analysis becomes consequential; notebook
cells must not hide sample filters, intercepts, covariance choices, or missing
data behavior.
