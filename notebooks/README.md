# Notebooks

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
