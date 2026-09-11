# Notebooks

Start with `signal-report.ipynb`: run `make notebook` from the repository root,
then run all cells. It generates a synthetic report through production functions,
displays the shared report view and exports a verified bundle under ignored
`build/`. To inspect your own report, use `load_report(path)` instead of the
synthetic-generation cell. `view.table()` returns a Polars frame;
`view.figure(kind, page=0)` returns an independent Matplotlib Figure.

Launch through `make notebook` so the kernel uses the project's locked environment.
Do not expose Jupyter beyond loopback or disable its authentication. CI uses
`make notebook-check`; the tracked notebook deliberately contains no cell outputs.

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
