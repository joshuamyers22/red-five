# Red Five — project brief

Owner: Josh. Initial delivery: a local research walking skeleton.

## Outcome and scope

Evaluate signal quality, marginal contribution and economic viability with reproducible evidence. Support cross-sectional signals and time-series signals whose evaluation unit is an individual instrument/contract model.

Residualization and weighting are external. Consume their versioned outputs and validate timestamps, units and identity; do not fit factor models, optimize weights, route orders, or automatically change live registry membership.

The first slice succeeds when the documented CLI evaluates synthetic signals, optionally accounts for supplied weights/costs, produces repeatable evidence, rejects future/duplicate/invalid inputs, and passes the quality/build gates. The multi-phase plan is [docs/PROJECT_PLAN.md](docs/PROJECT_PLAN.md).

## Initial contracts and constraints

- Python 3.12 local package/CLI, Polars at CSV boundaries, NumPy for descriptive correlations. Statsmodels remains the planned inference engine.
- Input v1 is an explicit-timestamp snapshot for one horizon and return target. Models/predictions are supplied, never fitted in this workflow.
- UTC-normalized aware times; calendar and horizon identities supplied externally. No exchange calendar or forward-return construction is inferred from dates.
- File inputs capped at 16 MiB and CSVs at 100,000 rows in this slice; reject larger inputs. No queues, retries or network services.
- Finite float64 for correlations; Decimal for supplied-weight interval accounting. Return fractions, weights relative to pre-trade NAV, and costs in bps are explicit.
- No imputation, winsorization, implicit zero returns, or pooling of time-series instruments. Exact schema/duplicate checks and availability filters are mandatory.
- Repository fixtures are synthetic. Restricted inputs belong outside Git. Output artifacts live in ignored `build/` or an explicit user path.
- Local filesystem is the initial evidence adapter. Publication must not overwrite existing differing artifacts. Postgres snapshots and recoverable publication are later phases; no claim of production durability is made for the local adapter.
- Input bytes, config, analysis plan, package source files, lockfile and software versions identify a run. Machine-specific paths do not enter the report.

## Evidence and safety boundaries

Descriptive Pearson/Spearman correlations and per-interval supplied-portfolio accounting are allowed. All reports have an insufficient-evidence decision status and no acceptance verdict until a consequential analysis/decision policy exists. The minimum sample parameter is a mechanical diagnostic threshold, not power or statistical significance. No t-stat, Sharpe, economic IC conversion or Bonferroni policy is silently selected.

Highest-risk cases: future information, mixed instrument histories, stale/missing labels, omitted/repeated trade costs, and evidence overwritten under the same name. Focused tests must exercise those boundaries in addition to inherited template tests.

Runtime/memory targets for production panels, approved licensed data, calibrated cost model, final holdout/multiplicity policy, acceptance thresholds, registry retention/recovery and hosting/on-call remain open. They do not block this synthetic local slice. Before deployment, complete release, container, restore, freshness and production replay evidence.

## Notebook and reporting slice

Shared immutable report views serve Jupyter, CLI and offline HTML/CSV/SVG/PNG.
Matplotlib is a presentation adapter; the locked optional notebook group provides
JupyterLab and ipykernel. No computations move into notebook cells. Local setup,
CI notebook/package smoke tests and deployment gates follow the production
template; see `docs/REPORTING.md`, `docs/INFRASTRUCTURE.md` and ADR 0002.
