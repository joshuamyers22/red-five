# Red Five

Signal diagnostics and economic evaluation of externally supplied portfolios.
Python package: `red_five`; command: `red-five`.

The first implementation is a local research walking skeleton. It evaluates
timestamped predictions in cross-sectional or per-instrument/contract time-series
mode and optionally reconciles a supplied weight/return ledger. It does not fit
return residualizers, choose weights, optimize portfolios, or issue acceptance
verdicts. Inputs, configuration, analysis plan, source code and locked environment
are bound into a deterministic report identity.

```sh
make setup
make check
make build
uv run red-five eval examples/signals.csv \
  --config examples/evaluation.json \
  --analysis-plan STATISTICAL_ANALYSIS_PLAN.md \
  --weights examples/weights.csv \
  --output build/example-report.json
uv run red-five verify build/example-report.json
```

## Visualize in Jupyter

Run `make notebook` from the project directory to open
[the composition cookbook](notebooks/composition-cookbook.ipynb) in the locked local JupyterLab
environment. Compute individual sections, select models, customize charts/tables,
draw on your own subplot axes, and export only chosen components. No separate
kernel installation is needed. The [quantile notebook](notebooks/quantile-diagnostics.ipynb)
adds frozen training-only bins, separate model charts, coverage and spread tables;
see [its API and assumptions](docs/QUANTILES.md). `make notebook-check` executes all
three notebooks, including the original [full-report notebook](notebooks/signal-report.ipynb).

See [the composition API](docs/COMPOSITION.md) for `evaluate_section`, `Selection`,
`PlotOptions`, caller-owned axes, and partial exports. Existing full-report usage:

```python
from red_five.visualization import load_report

view = load_report("build/example-report.json")
display(view)  # Full inline report
display(view.table("signals"))  # Polars dataframe
display(view.figure("correlations"))
view.export("build/example-bundle")
```

From the command line:

```sh
uv run red-five render build/example-report.json --output-dir build/example-bundle
uv run red-five verify-bundle build/example-bundle
```

Bundles contain offline HTML, SVG/PNG figures, HTML/CSV tables, source JSON and a
hash manifest. See [reporting contracts](docs/REPORTING.md) for supported views,
limits and export safety, and [infrastructure](docs/INFRASTRUCTURE.md) for local
setup and deployment gates. Rendering remains descriptive, with no verdict.

All example inputs are synthetic. Evaluation output is JSON; the CLI prints its location,
identity and evidence status. Rerunning identical inputs is idempotent. A different
report cannot overwrite an existing output. `verify` checks the report's internal
content digest; it is not a source authenticity or financial correctness check.

Read [input contracts](docs/INPUT_CONTRACTS.md) before using your own files.
Dates must have offsets; values use explicitly declared units. Immature or missing
labels are counted separately and excluded from metrics. Future signals, duplicate
keys, malformed data, and incompatible model identities fail with a nonzero exit.
Metrics are descriptive: no p-values, selection-adjusted significance, inferred
Sharpe or live promotion is implied. The report explains what is unavailable.

Development uses Python 3.12, a frozen `uv.lock`, Polars, NumPy, Ruff, strict Pyright
and pytest. Statsmodels and the template's regression, temporal-validation and
Parquet utilities are retained as separately documented foundations; they are not
invoked to fit the external models in `red-five eval`. See the
[template utility guide](docs/TEMPLATE_GUIDE.md). Tests require no live network or
database. CI runs the same quality/build gates plus dependency/license audit.

The [project brief](PROJECT_BRIEF.md), [plan](docs/PROJECT_PLAN.md),
[analysis plan](STATISTICAL_ANALYSIS_PLAN.md), and
[initial verification record](docs/INITIAL_VERIFICATION.md) define scope and
remaining work. Next slices add time-aware inference/selection evidence,
breadth, paired marginal comparisons and the Postgres registry. Descriptive
fixed-training quantiles are available as an independent notebook section.
Production monitoring, deployment, calibrated costs and market-data onboarding
remain later gates. This repository has not been deployed.
