# Red Five — Signal Evaluation & Economic Viability

Project: **Red Five**. Repository/CLI: `red-five`; Python package: `red_five`. Python `src/` layout, pytest, planned Postgres registry.

> **Adversarial review integrated — 2026-09-11.** This is a research and implementation plan, not evidence of production readiness. The production project template review is recorded in §§12–16. High-severity findings remain open until their acceptance evidence exists; changes to this document alone do not close them. Revised phase gates in §10 and the contracts in §14 govern implementation.

> **Owner scope decisions — 2026-09-11:** residualization and portfolio weighting happen outside this project. `red_five` consumes their versioned outputs and checks their input contracts; it does not fit factor models, construct portfolio weights, or optimize allocations. Time-series signals are in scope: each instrument/contract is a separate model/evaluation unit, with shared breadth and quantile diagnostics generalized as specified in §14.7. These decisions supersede the original open questions and the review's proposed internal-model defaults.

## 1. What this thing is for

Three questions to investigate. Standalone diagnostics are not universal hard gates: a hedge or interaction can improve a portfolio despite weak standalone IC. The final decision is incremental net value under a declared portfolio policy.

1. **Is it good on its own?** IC, rank IC, ICIR, decay across horizons.
2. **Does it add anything to what I already run?** Orthogonalized IC, threshold rule, combined-Sharpe math, effective breadth.
3. **Does it survive contact with costs?** Breakeven IC given spread, turnover, dispersion, and holding period — the `min_correlation` workbook, generalized.

The project's hypothesis is that economic viability and marginal value eliminate many statistically promising candidates. Track rejection reasons to test that hypothesis rather than assuming which constraint will bind.

The architectural spine is a **signal registry**: a persisted set of the signals currently in production. "Marginal value" is meaningless without a baseline, so the baseline has to be a first-class stored object, not a notebook variable.

---

## 2. Data contract (build this first, resist the urge to skip it)

Everything downstream is a function of one aligned object.

```text
SignalPanel:   index = (date, asset), column = signal value
ForwardReturns: index = (date, asset), columns = configured horizons
ResidualReturns: externally residualized labels plus upstream model/data manifest
PortfolioWeights: externally constructed target weights/holdings plus policy manifest
ModelIdentity: signal/model version + instrument/contract identity for time-series models
```

Non-negotiable checks at construction time:

- **Point-in-time alignment.** Signal at close of `t` maps to return from `t+1` open (or whatever the implementable lag is). One off-by-one here invalidates every number in the report.
- **Universe membership is PIT.** No survivorship in the asset list.
- **Separate return targets.** Consume externally residualized returns for residual-target diagnostics and implementable total returns for economic viability. Residualization does not establish independence, and residual P&L is not automatically tradable. Require the upstream residualizer/data version and availability/target semantics; fitting the factor model and exposures is outside this workflow. Consume externally supplied hedge holdings and account for their costs if a hedge is assumed. Total-return diagnostics are legitimate when explicitly labeled.

Ship a `validate_panel()` that fails on invalid contracts. Expected immature labels and insufficient samples produce explicit unavailable metrics, with coverage and reason codes; they must not become zeros or disappear silently. The full timestamp, schema, and missingness contract is in §14.2.

---

## 3. Module 1 — Standalone metrics

`red_five.standalone`

| Metric | Implementation | Notes |
|---|---|---|
| Rank IC | Spearman, cross-sectional, per date | **Default.** Fat tails, ranking objective, monotone non-linearity |
| Pearson IC | Optional diagnostic; required for a Pearson-based analytical model | A gap versus rank IC prompts influence/nonlinearity checks; it does not prove outlier dependence |
| ICIR | `mean(IC) / std(IC)` over dates | Descriptive; no universal stability thresholds; report sampling frequency and dependence |
| t-stat | `mean(IC) / SE(mean(IC))` | Dependence-aware SE; `ICIR × sqrt(T)` is only the iid special case |
| R² | Squared Pearson correlation for simple in-sample OLS with intercept | Not squared rank IC; predictive out-of-sample R² uses a declared baseline and can be negative |
| Hit rate | Measured sign agreement, with explicit zero/tie policy | Arcsine expression is a centered bivariate-normal Pearson-correlation benchmark, not a general IC conversion |
| Horizon/decay diagnostics | IC across configured {1, 5, 21, 63, 126}d horizons | Cumulative-horizon IC is not itself an alpha half-life; use lagged incremental-return diagnostics and net replay to select holding policy |

For time-series signals, calculate these diagnostics over time separately for each instrument/contract model. Cross-sectional per-date IC remains a distinct mode. Reuse quantile and breadth machinery with explicit grouping/aggregation contracts (§14.7); never silently pool different model scales or pretend model count establishes independence.

Two things to add beyond the source note:

- **IC by regime.** IC in the top/bottom vol quintile, by sector, by liquidity bucket. A signal with IC 0.04 that is 0.09 in calm and −0.01 in stress is a different animal than a flat 0.04.
- **Quantile spread and monotonicity.** Q1–Q5 forward return, plus whether the middle buckets order correctly. IC can be respectable while the payoff lives entirely in one tail. Use `binspect` for the binned signal-vs-forward-return plot — this is exactly the diagnostic-plus-good-plot case it was built for.

Inspect unusually large IC for leakage, concentration, and target errors. The rough 0.01–0.10 band is a context-dependent research heuristic, not validation evidence or an automatic rejection threshold.

---

## 4. Module 2 — Marginal value

`red_five.marginal`

This is where the registry earns its keep. Three tools, cheapest first:

**a. Screen — correlation to the existing set.** Fast, run it before anything else.

**b. Threshold rule.** Under a compatible linear, frictionless single-baseline model, the following is a directional screen:

```
IC_new  >  IC_existing × ρ(new, existing)
```

and in portfolio terms `SR_new > ρ_new × SR_portfolio`, using strategy-return correlation for the Sharpe expression. Fix signal orientation on development data. Pairwise screens cannot reject all multivariate, hedge, or nonlinear candidates; a maximum over registry pairs is not a portfolio inclusion rule.

**c. Orthogonalized IC.** Regress the candidate on the baseline signals using a declared design matrix, then compute residual-signal IC as a redundancy diagnostic. This is not generally partial rank correlation and does not decide inclusion. Freeze transformations and regularization within training folds; a predeclared contemporaneous projection may use only signals available at decision time. Decide inclusion from held-out baseline-versus-augmented portfolio replay, after constraints and incremental costs (§14.3).

**Combination math** (`red_five.marginal.combine`), used for "what would adding this do":

```
uncorrelated:  R²_comb = ΣR²ᵢ            SR_comb = sqrt(ΣSRᵢ²)
two correlated: R²_comb = (r₁² + r₂² − 2r₁r₂ρ) / (1 − ρ²)
n uniform-ρ:    SR_comb = SR × sqrt(n / (1 + (n−1)ρ))
```

For equal standalone Sharpe and fixed positive equicorrelation, the multiplier ceiling as `n → ∞` is `1/sqrt(ρ)`, not `1/ρ`. At ρ=0.5 it is 1.41×, versus 1.29× at n=5. This does not imply that the first few decorrelated signals exhaust diversification: at ρ=0 the multiplier is `sqrt(n)`. Treat these as analytical scenarios, with the assumptions and PSD/singularity checks in F06; distinguish them from measured portfolio gains.

**Deferred experiment — the multivariate case.** A modified Shapley/random-probe gate may be evaluated as an alternative backend to `marginal.rank_features()`. One random probe is not evidence of false-discovery control. Require a precise utility, dependence-preserving null construction, repeated probes, nested selection, compute limits, and a held-out comparison with simpler baselines before adoption (F16).

---

## 5. Module 3 — Effective breadth

`red_five.breadth`

`IR = IC × sqrt(BR)` is an idealized relation, not an estimator of achieved portfolio IR. Independence alone is insufficient: forecast calibration and implementation constraints also matter. The following proposed heuristics are retained as diagnostic scenarios, not decision inputs:

```python
# cross-sectional: residual returns aren't really orthogonal
rho_cross   = mean_pairwise_corr(residual_returns)
N_effective = N / (1 + (N - 1) * rho_cross)

# temporal: proposed AR(1) proxy; not a validated count of independent bets
rho_time    = corr(signal_t, signal_{t+1})
T_effective = T_nominal * (1 - rho_time) / (1 + rho_time)

BR_effective = N_effective * T_effective
```

Label these as **unvalidated heuristics borrowed from portfolio variance and effective-sample-size**. They need not have the right magnitude or even act as haircuts. The first can exceed N or diverge under negative average correlation; the second describes an AR(1) sample-mean approximation, not generic independent trading opportunities. Do not multiply them without a justified separability model. Report domains, uncertainty, covariance diagnostics, and `unavailable` when invalid; use replay for achieved IR (F07).

Signal autocorrelation is one diagnostic. The upstream portfolio workflow chooses rebalance policy; this project evaluates the supplied policy against alpha decay, realized trades, constraints, and costs. Autocorrelation does not determine turnover or an optimal holding period by itself.

---

## 6. Module 4 — Economic viability

`red_five.economics` — the `min_correlation` workbook, generalized and made honest.

Sheet logic as transcribed in the original plan; the source workbook has not been audited in this review:

```
breakeven_IC = cost_bps × 1e-4 / (z_spread × vol × sqrt(holding_days))
gross_edge_bps = IC × vol_bps
daily_SR = net_edge / vol ;  annual_SR = daily_SR × sqrt(252)
```

with tiers at 1.0× / 1.5× / 2.0× breakeven ("absolute minimum" / "ok" / "good"). At cost=6bp, z=3, vol=1%, daily rebalance: breakeven IC = 0.02, so the example IC of 0.03 clears the floor but not the "good" hurdle.

Before porting, reconcile units, gross exposure, turnover, trade sides, and horizon against an explicit cash-flow ledger. Under the one-period spread example above, 0.03 × 3 × 1% gives 9bp gross and 3bp net after a 6bp total cost. This example does not establish portfolio Sharpe or prove that the source workbook double-charges costs (F04).

Generalizations worth building:

- **Cost model as a function, not a constant.** Charge traded notional for each trade side; calibrate spread, impact, fees, borrow, and financing with units and timestamps. Square-root participation impact is a candidate model requiring a coefficient, valid range, and execution-window definition.
- **Turnover from actual target and drifted pre-trade holdings.** Include initial entry, exits, universe changes, hedges, and constrained or unfilled orders. Autocorrelation is only a cross-check.
- **Capacity curve.** Sweep AUM under participation, liquidity, borrow, and risk limits. Report the first binding constraint and a cost-stressed range. A zero crossing may be absent or nonmonotonic; do not extrapolate past the calibrated model domain.
- **Breakeven surface.** Heatmap of required IC over (cost, dispersion) or (cost, holding period). Far more useful than a single tier table, and it answers "what would have to be true for this to work."
- **Alpha decay scenarios.** Treat 5%/yr as an illustrative assumption, not an empirical forecast. Define relative versus absolute decay and include abrupt loss or reversal alongside gradual deterioration.

---

## 7. Corrections to carry into the implementation

The original draft attributed these corrections to source notes. This review checks the transcribed math, not the unprovided source documents; reconcile the actual notes/workbook and retain their versions before porting:

1. **Correlation ceiling.** The draft attributes a multiplier ceiling of `1/ρ` to the note (2× at ρ=0.5, 3.3× at ρ=0.3). Under the fixed-positive-equicorrelation model, the Sharpe multiplier ceiling is `1/sqrt(ρ)` — 1.41× and 1.83×. `1/ρ` is the ceiling on the *squared* multiplier; the discrepancy is not a universal factor of two.
2. **IC t-stat.** Replacing securities N with observation periods T fixes only the observation-unit error. `ICIR × sqrt(T)` still requires iid-style mean inference; overlapping horizons and serial dependence require an appropriate SE (F02).
3. **Hit rate.** Denominator is `π`; the expression yields 53.2% at Pearson correlation 0.10 under centered bivariate-normal assumptions. It is not a universal mapping from rank IC to realized hit rate.
4. **Worked example typo.** "IC of 0.10 and 0.008 (R² of 1% and 0.64%)" — the second IC is 0.08.
5. **Workbook unit mismatch.** In the transcribed formulas, breakeven divides by `z_spread × vol`, while gross edge uses `IC × vol`. Establish whether both refer to the same portfolio/score spread, then use one convention. `α = IC_Pearson × σ × z` is a conditional linear-model shortcut; see §14.3 for calibration and NAV conversion.
6. **Possible double-charging costs.** `IC − 2×breakeven` is incorrect if breakeven already includes the full round trip, but may represent two trade sides if it does not. Resolve source-cell definitions before changing it. Keep cost multiples separate as economic safety margins; they are not statistical confidence levels.
7. **Holding-period scaling.** A fixed round-trip cost divided by T is an average daily cost only for the specified holding policy. Volatility scales as `sqrt(T)` only under suitable return assumptions. Derive horizon edge and costs together; do not infer holding-period alpha from risk scaling alone.

---

## 8. Output — scorecard, graphics and tables

One versioned `SignalReport` object, one rendered page backed by immutable evidence. The numbers below are layout placeholders, not a reconciled calculation or measured result. Add data/label cutoff, baseline and run identity, validation split, confidence intervals, coverage, cost assumptions, and decision reason codes (§14.4). Structure:

```
STATUS: valid | invalid-data | insufficient-evidence | stale | failed
VERDICT (only when eligible): reject | monitor | accept-small | accept

Standalone     rank IC 0.034 | ICIR 0.41 | t 2.8 | decay half-life 9d
Marginal       max ρ to registry 0.38 | orthogonalized IC 0.028 | ΔSR +0.11
Breadth        nominal 126,000 | effective 1,840 | implied IR 0.71
Economics      breakeven IC 0.020 | net edge 1.4bp | net SR 0.44
               zero-crossing AUM $180mm
Fragility      IC in stress quintile −0.01 | post-decay SR 0.31
```

Graphical and tabular output are first-class deliverables, not a final cosmetic step. Start with views supported by the existing descriptive JSON; add inference, quantiles, marginal comparisons and portfolio-path views only when their underlying evidence contracts exist. The figures in the layout above remain illustrative and must never appear as fallback values in an actual report.

### 8.1 Report bundle and rendering boundary

- **Offline HTML report:** one navigable page with run/status banner, summary scorecard, graphics, accessible data tables, assumptions and provenance. No server, CDN, remote fonts or network connection required; no live dashboard in this scope.
- **Figure exports:** SVG for scalable review and PNG for sharing, with stable figure IDs, captions and corresponding table IDs. Use a consistent ggplot-style theme; select and lock the rendering library during implementation. Keep `binspect` interoperability behind the plotting adapter rather than in numerical domain code.
- **Table exports:** semantic HTML tables plus UTF-8 CSV files with a documented schema (column types, null encoding, units and precision). Include full-precision values in machine-readable evidence; rounding is display-only. Preserve instrument/contract identifiers as text and provide spreadsheet-safe handling for untrusted text fields without changing canonical values.
- **Canonical evidence:** plots and tables consume verified, versioned report JSON and any manifest-referenced, hash-verified tabular evidence. They cannot refit models, select weights, infer missing results, change verdicts or compute new statistical/economic metrics. New rolling series, confidence intervals, bin summaries, drawdowns and scenarios must first be produced and tested by the evaluation layer. Render-only ordering, faceting and formatting are permitted.
- **CLI and notebook API:** `red-five render report.json --output-dir report-bundle` produces HTML, figures, tables and a manifest without rerunning evaluation. `load_report(path)` supplies the same views in Jupyter; `make notebook` opens the synthetic example. These descriptive interfaces are implemented; advanced views remain phased below. The manifest records source report hash, renderer/source/config versions and output hashes. Preserve non-overwriting publication and require manifest verification before consuming a bundle; rendering failure leaves source evidence unchanged.
- **Distribution boundary:** the public GitHub repository contains synthetic examples only. Real report bundles remain ignored/private by default and require an explicit data-release decision before publication; rendering must not upload anything.

### 8.2 Required views and evidence dependencies

| Review question / phase | Graphical output | Companion table and eligibility |
|---|---|---|
| Is the run usable? First reporting slice | Eligible, missing-mature and immature observation counts by evaluation group; separate timeline/coverage map only once time-indexed coverage evidence exists | Run identity, as-of/label cutoff, mode, target, horizon, model identities, status/reasons and eligible/excluded counts. Always retain invalid/insufficient groups. |
| How does each model behave? First reporting slice, then Phase 1 | Per-group Pearson/Spearman dot plots; later cross-sectional per-date IC with trailing rolling mean, or per-instrument/contract temporal diagnostics, explicitly labeled by axis | Group estimates, eligible count, exclusions and reason codes; uncertainty/method only when computed. Do not call temporal correlation a cross-sectional IC series. |
| Is behavior stable across horizons and bins? Phase 1 | Horizon/lag decay curves and within-model quantile mean-return plots; interval bands only from the declared estimator | Horizon/target definition, training-only bin boundaries, ties, counts, coverage, means, spreads and uncertainty. Distinguish cumulative-horizon profiles from fitted incremental decay/half-life. |
| What do supplied positions earn after costs? First reporting slice, then Phase 2 | Initially gross/net interval-return and cost-component bars; later gross/net NAV and drawdown curves after validated non-overlapping portfolio-path accounting | Supplied portfolio/interval, gross return, trading and holding costs, net return, turnover and units. NAV, Sharpe and drawdown are unavailable from the current interval-only report. |
| What assumptions make it viable? Phase 2 | Cost/AUM sensitivity heatmaps and capacity curves with infeasible regions masked | Scenario assumptions, calibrated validity ranges, net utility, constraints and crossing status; no extrapolated crossing or rank-IC-to-P&L conversion. |
| Does it improve the existing portfolio? Phase 3 | Paired baseline/augmented performance views and incremental utility estimates with valid intervals | Baseline snapshot, matched evaluation dates, supplied weighting policies, gross/net comparison, delta, coverage and uncertainty. Missing paired evidence is unavailable, not zero improvement. |
| How redundant are the model streams? Phase 4 | Correlation/dependence heatmap with overlap counts; covariance spectrum and explicitly labeled breadth scenarios | Model/instrument/contract IDs, pairwise overlap, missingness policy, matrix validity, concentration and scenario assumptions. No assertion that one contract equals one independent bet. |
| Why was a decision reached? Phase 5 | Summary annotations linking to supporting figures; no acceptance-colored badge before eligibility | Versioned decision predicates, inputs, thresholds, outcomes, reason codes, trial family/search history and evidence links. Unconfigured predicates remain unavailable. |

### 8.3 Display and statistical integrity

- Every figure/table identifies the run, evaluation sample, target/horizon, units and grouping. Put sample size, exclusions, uncertainty method/level and major assumptions beside the estimate, not only in a tooltip. Show `unavailable` plus a reason instead of substituting zeros or omitting failed models.
- Time-series views facet by model/instrument/contract; a single model is supported. Do not pool unrelated score scales. Training-only bins stay fixed when future observations change. Cross-model aggregation, if desired, requires an explicit evaluation-layer policy and coverage disclosure.
- Use trailing, never centered, rolling windows with declared lookback and minimum count. Visually distinguish observations, fitted estimates, uncertainty and hypothetical scenarios. Confidence bands must identify pointwise versus simultaneous coverage and must not imply multiplicity adjustment unless it was actually performed.
- Expose time gaps and label immaturity; do not connect missing periods as if observations were continuous. Label return percentages versus bps, cost sign conventions and log axes; bars start at zero and correlation heatmaps use a fixed, labeled scale. Avoid decorative dual axes and three-dimensional charts.
- Use colorblind-safe colors plus labels/line styles, sufficient contrast, meaningful captions and accessible HTML headings/tables. Every chart has a usable text/table equivalent. Dense panels use deterministic, declared pagination/faceting; any display downsampling is disclosed and does not alter metrics or the complete table export.
- Escape all metadata in HTML/SVG, defend CSV exports against formula injection, reject unsafe output paths, and avoid raw signals/positions in default summary reports. Bound figure/table counts, output bytes and render time; publish explicit truncation/limit failures, not silent omission.

### 8.4 Delivery and acceptance

1. **Descriptive report bundle, then composable notebook sections.** The initial bundle is implemented for current JSON fields: run/status summary, per-group correlations/counts and supplied-weight interval accounting. Next deliver §8.5's independently computed/rendered sections and flexible notebook composition. Unsupported views remain explicit; no new significance or portfolio-path claims.
2. **Incremental analytical views.** Add each row of §8.2 as its Phase 1–4 evidence becomes available. Version extended schemas and maintain old-report compatibility or give a clear unsupported-version error. Reporting must not delay core offline evaluation or require a database.
3. **Phase 5 integration.** Complete the scorecard and decision audit links. Test known-value JSON-to-table-to-chart-data parity, display rounding, negative/zero/constant values, ties, missing/immature/all-ineligible groups, one model, many models, long/non-ASCII identifiers, tampered evidence and hostile metadata/CSV strings.
4. **Release evidence.** Run render/verify smoke checks from the installed wheel with networking disabled; inspect representative synthetic reports at desktop and narrow/print layouts. Exercise missing rendering dependencies, output conflicts and mid-render failure with no partially complete bundle. Require deterministic table/plot-data/manifest output under pinned settings; use structure/data assertions and toleranced image comparisons, not cross-platform pixel equality as a numerical oracle. Rendering must leave source report hashes, computed values and decision status unchanged.

### 8.5 Notebook-first, independently usable report components

**Owner requirement:** users must be able to create only the portions of a report they need in Jupyter, customize their visualization, and combine them in their own layout. The full report is a convenience composition of those components, not the required entry point.

**Current versus planned:** individual section evaluation, full-report section extraction, caller-owned axes, typed visual options, display selections and partial/custom component exports are now implemented for standalone, coverage and economics. See [composition API](COMPOSITION.md) and [verification](COMPOSITION_VERIFICATION.md). Optional widgets, arbitrary artist/layout serialization, failed-section history and later analytical sections remain future work. Standard exports replay recorded options, not arbitrary manual edits to returned figures.

#### Independent sections and evaluation

- Expose typed library functions for standalone diagnostics, coverage, supplied-portfolio economics, quantiles, and later marginal and breadth sections. A supported section can be evaluated and displayed without producing the full report or writing files. It validates its required inputs and dependencies only: standalone diagnostics must not require weights, a baseline registry, or economic calculations. Economics still requires the declared external weights/returns and alignment evidence; independence is not permission to bypass validation.
- Return immutable, versioned section results containing estimates, exact-value tables, supported plot data, coverage, status/reasons and provenance. Rendering accepts either such a section result or the corresponding section extracted from a full report. Reuse production calculation functions rather than duplicating computations in notebook cells.
- Track section dependency and completion status explicitly. Distinguish `not requested`, `unavailable`, `failed` and successfully computed evidence. A partial report is labeled partial; success of a selected section cannot imply full-report eligibility or an acceptance verdict. Unsupported later-phase sections remain unavailable until their numerical contracts are implemented.
- Bind section identity to input/configuration/analysis-plan/code hashes and sample/model selection. Cache/reuse verified results within a session; changing styling must not rerun evaluation. Changes to dates, horizon, sample eligibility, aggregation or statistical parameters require a new evaluation/result identity, not a plotting-side recalculation.

#### Flexible plots, tables and composition

- Plot functions accept a caller-owned Matplotlib `Axes` or create and return their own figure/axes. Support notebook subplot grids, side-by-side panels, overlays of compatible already-computed series, and a single instrument/contract view. Do not create extra figures, call `show()`, close caller figures or change their unrelated axes. Unsupported combinations fail explicitly.
- Provide documented, typed display options for figure size/DPI, palette, markers/line styles, fonts, labels, legends, annotations, axis formatting, faceting, metric selection and display order. Defaults remain accessible and statistically honest. Permit explicit axis zoom/scale overrides with visible clipping/scale disclosure; do not silently change units, pool score scales or remove unavailable groups. Temporary styles must not leak into other notebook cells.
- Tables support selected columns, stable display sorting, model/contract/portfolio filters, formatting and precision, while exposing exact underlying Polars data for further exploration. Existing group/interval selection is a labeled display subset, not a new evaluation sample. Filtering dates cannot recompute a full-history correlation from an aggregate row; request a fresh section evaluation for that sample instead. Record what was selected or omitted, including unavailable groups, so a selected view is not mistaken for complete coverage.
- Offer an optional local interactive layer for controls such as section, model, metric and display range. Controls operate on verified evidence and call the same public APIs; no dashboard service, mandatory widget dependency or new plotting backend is implied. Static notebook display/export must remain usable without widgets.
- Let users assemble selected components in arbitrary order with notebook Markdown and their own subplot layouts. Full HTML reports compose the same section primitives. Export a single chart, a single table, one section or a custom collection without rendering unrelated sections. Attach source/section identity, selection, display configuration, units/status and output hashes; verification must understand partial bundles rather than demand every full-report artifact.
- Version serializable display specifications separately from numerical configuration so custom views can be reproduced. Preserve raw result values and source hashes across all styling/export operations. Arbitrary manual Matplotlib edits remain available for exploration; do not claim they are reproduced by a standard export unless an explicit custom-figure export captures them and labels their provenance/verification limits.

#### Acceptance evidence and next delivery

The local standalone/coverage/economics composition slice is implemented; extend the same contract as later analyses arrive. The cookbook demonstrates one section from inputs, one model, exact-value tables, custom styling, caller-owned subplots, and single/custom exports. Tests establish weight-free standalone evaluation, computation isolation, extracted/independent value parity, unchanged numerical hashes under styling, caller-axis/global-style preservation, disclosed display subsets, empty/unavailable states and partial verification. Both notebooks execute in clean kernels; installed-wheel section smoke passes. See COMPOSITION_VERIFICATION.md for executed evidence and remaining production/advanced-interface limits. Selected chart-export tables must retain their plotted metrics.

The verdict policy must be versioned and predeclared, with every predicate and supporting observation stored. Acceptance is a research recommendation; changing live registry membership or weights is a separate recorded action. An invalid, stale, failed, or underpowered run cannot inherit an earlier acceptance as a fresh result.

---

## 9. Infrastructure

- **Postgres**: version signal definitions and immutable baseline snapshots, retain candidate/trial history, and record run attempts and evidence references. Historical reproduction must resolve the original snapshot, not current registry weights. Use the identity and publication contract in §14.5.
- **Airflow**: nightly re-evaluation of the live registry. Signals die quietly; a monitoring DAG that recomputes rolling IC and flags decay is worth more than any one-off study.
- **Evidence identity**: canonical config and analysis-plan hashes plus input manifests, signal/model versions, baseline snapshot, code revision, dependency lock, calendar, seed, and evaluation/label cutoffs. A config hash alone is insufficient.

---

## 10. Phasing

| Phase | Deliverable and exit evidence |
|---|---|
| 0 | Complete project brief and statistical analysis plan; generate `python-data-quant` foundation under `~/Projects/red-five` when implementation starts. Freeze PIT, target, portfolio, cost, and baseline contracts; CLI fixture → validation → one metric and trade ledger → persisted evidence → minimal report; `make check` and build pass. No acceptance verdict yet. |
| 0R | Next slice: offline descriptive HTML report, accessible tables/CSV and SVG/PNG figures from current verified JSON (§8.4); render/data parity and installed-wheel smoke pass. Unsupported analyses remain unavailable. No verdict yet. |
| 0N | Next notebook extension: independently evaluated/rendered sections, caller-owned subplot composition, typed visual/table options, explicit selections and partial/custom exports (§8.5); dependency-isolation, parity, provenance and clean-kernel cookbook tests pass. |
| 1 | Standalone metrics, temporal folds, dependence-aware inference, trial ledger, negative controls, decay and quantile diagnostics with companion graphics/tables (§8.2); leakage and missingness attacks pass. |
| 2 | Executable portfolio accounting, independently reconciled workbook convention, calibrated/stressed costs and feasible capacity sweep; deterministic cash-flow and trade-side tests pass. Economics remains early but now has a portfolio contract. |
| 3 | Versioned Postgres registry and baseline snapshots; held-out baseline/augmented replay with incremental net utility and uncertainty; concurrency, retry, migration, and reproduction checks pass. |
| 4 | Optional breadth sensitivity diagnostics and analytical combination tests; no verdict dependence on unvalidated breadth heuristics. |
| 5 | Integrated HTML scorecard, figure/table export bundle, versioned verdict policy and audit trail (§8); every decision reconstructs from retained evidence; parity, accessibility, escaping and invalid/stale/insufficient paths tested. |
| 6 | Containerized Airflow job after batch replay parity; maturity-aware evaluation, bounded retries, freshness alerts, restore and rollback exercises, representative runtime/memory evidence. |
| 7 | Optional Shapley/probe experiment only after simpler baseline comparison and predeclared research protocol; no production gate by default. |

Phase 0 needs both statistical-oracle fixtures and causal end-to-end fixtures. For independent standardized normal X and E, construct `Y = r*X + sqrt(1-r*r)*E`: population Pearson correlation is r, while sample correlation has uncertainty and rank correlation has a different target. A forward-return-injected signal is acceptable only as a labeled estimator fixture; the PIT integration path must detect its future availability. Add null, negative, tied, constant, missing, collinear, and delayed-label cases (F15).

---

## 11. Scope decisions and remaining open questions

- **Resolved — residualization:** performed upstream, outside the project. Accept residual returns and provenance/availability metadata; validate the boundary without implementing the residualizer.
- **Resolved — weighting:** performed upstream, outside the project. Accept versioned baseline/candidate/augmented target weights or holdings; evaluate supplied portfolios without selecting a weighting scheme or fitting combination weights. Missing weights permit signal diagnostics but not an invented portfolio-level economics verdict.
- **Resolved — time-series signals:** each instrument/contract in the sample is its own model. Support instrument-level temporal metrics and generalize common breadth and quantile machinery (§14.7).
- **Open — multiple testing:** define the hypothesis family, trial accounting, correction method, temporal validation and final holdout policy. Instrument-specific model searches and upstream residualization/weighting searches that influence selection belong in the supplied research history, even though their implementation is external.

The [Systematic Long Short survey](MULTIPLE_TESTING_SURVEY.md) identifies four direct discussions, including explicit Bonferroni references in the March 24 research-mistakes article and March 5 factor-model article. Consider a configurable Bonferroni baseline with raw/adjusted p-values and declared family size, while retaining dependence-aware inference and untouched assessment. This is a proposed method, not a resolved policy; do not hard-code the factor article's approximate t-ratio threshold.

Remaining input choices and phase deadlines are in §14.1. Multiple-testing and baseline-version controls are required before consequential assessment.

---

## 12. Adversarial review record

### 12.1 Scope and rubric

- **Reviewed artifact:** `Downloads/signal-viability-project-plan.md`, original 209-line draft; original SHA-256 `ebc37c9a9e0ed9212faf5e73f0dbb20a8a36c31fe50812ec928d75ce1a95c77c`. Finding locations below refer to original line numbers and stable section names.
- **Reviewer/date:** Codex, 2026-09-11. Single-context document review; not independent financial-model approval.
- **Template:** local `../Projects/production-project-template`, base commit `d59f3e661a1fa3456505cf36f91b51f4a1c873ac`. The local checkout contains existing README/source-material changes; this review used the files on disk and did not change that repository.
- **Applied materials:** [adversarial review template](https://github.com/joshuamyers22/production-project-template/blob/d59f3e661a1fa3456505cf36f91b51f4a1c873ac/templates/ADVERSARIAL_CODE_ARCHITECTURE_REVIEW.md), [review playbook](https://github.com/joshuamyers22/production-project-template/blob/d59f3e661a1fa3456505cf36f91b51f4a1c873ac/docs/ADVERSARIAL_REVIEW_PLAYBOOK.md), [production standard](https://github.com/joshuamyers22/production-project-template/blob/d59f3e661a1fa3456505cf36f91b51f4a1c873ac/standards/PRODUCTION_REPOSITORY_STANDARD.md), [project brief](https://github.com/joshuamyers22/production-project-template/blob/d59f3e661a1fa3456505cf36f91b51f4a1c873ac/templates/PROJECT_BRIEF.md), [statistical analysis plan](https://github.com/joshuamyers22/production-project-template/blob/d59f3e661a1fa3456505cf36f91b51f4a1c873ac/templates/STATISTICAL_ANALYSIS_PLAN.md), [improvement plan](https://github.com/joshuamyers22/production-project-template/blob/d59f3e661a1fa3456505cf36f91b51f4a1c873ac/templates/IMPROVEMENT_PLAN.md), engineering defaults, production blueprint, quant statistical-learning guidance, and `python-data-quant` README/reproducibility contract.
- **Scope:** plan consistency, quantitative assumptions, temporal validity, reproducibility, storage/failure contracts, delivery and acceptance evidence. No signal implementation, source workbook cells, underlying FLAM note, licensed market dataset, or running deployment was supplied as review evidence. Their behavior is unverified.
- **North star:** reproducibly assess whether a candidate improves a declared baseline's net out-of-sample utility at feasible size, while exposing uncertainty and invalid evidence.
- **Rubric v1:** template severity definitions; High findings block consequential acceptance in their affected path. Medium findings need owners and phase deadlines. No Critical implementation defect is asserted from a plan alone.
- **Review bound:** one substantive falsification pass plus one consistency/arithmetic pass, maximum 45 minutes; no model fitting or paid compute. Stop after actionable findings and contract checks; revisit only on new evidence or a changed plan. Domain assumptions without evidence remain open.

### 12.2 Executive verdict

**Grade: substantial revision required. Production recommendation: block consequential use pending evidence.** The useful organizing idea is the three-part standalone/marginal/economic report and an explicit baseline registry. The highest risk is a precise-looking acceptance recommendation built from incompatible statistical and economic quantities. The first improvement is one reproducible path from available-at timestamps through portfolio trades to net returns and a report with an explicit evidence status.

The recommended next work is the Phase 0 synthetic walking skeleton. The review amendments below are proposed implementation requirements; all findings remain open pending tests or accountable decisions.

### 12.3 Verification evidence and limits

| Check | Evidence / command | Outcome |
|---|---|---|
| Source and template inspection | `nl -ba Downloads/signal-viability-project-plan.md`; targeted reads of linked template files; `git -C Projects/production-project-template rev-parse HEAD` and `status --short` | Original scope and existing template changes identified. |
| Analytical counterexamples | Standard-library Python calculations of the equations printed in the plan | At n=5, ρ=.5: 1.290994×, limit 1.414214×. At IC=.03, z=3, σ=.01: 9bp gross, 3bp net for a 6bp total cost. Breadth heuristic at N=100, ρ=−.005: 198.0198; at ρ=−1/99 its denominator is zero. |
| Statistical source check | Primary research / official documentation linked beside F02, F03, F04 | Supports dependence, selection-bias, and cost-accounting concerns; does not validate a particular strategy. |
| Architecture contracts | Document trace of proposed data → evaluation → verdict → registry publication | No executable dependency graph exists in scope; §14 specifies the required boundaries. |
| Formatting, lint, typing, unit/integration tests, coverage, package build, security audit, performance | Not run: plan-only change, no `red_five` implementation under review | Not applicable as completed project evidence. Required future checks appear in §§10 and 15. |

---

## 13. Findings, ordered by severity and remediation value

For every finding, **current protection is unverified**: the original plan names pytest and one synthetic fixture but supplies no test results. Scope estimates refer to future implementation, not this markdown edit. Owners are proposed roles, not assigned people.

### F01 — High: Date/asset keys do not establish point-in-time validity

- **Location/evidence:** original lines 25–35, §2: only `(date, asset)` and a verbal close-to-next-open lag; §3 requests 126d labels absent from the original schema. Principle: data boundaries and correctness.
- **Failure:** revised fundamentals, present-day identifiers, delisted assets, stale prices, or labels that have not matured can enter a plausible-looking panel. Global row dropping may change each horizon's population without disclosure.
- **Change:** implement the availability, market-session, revision, adjustment, and join contracts in §14.2; use one horizon configuration for labels, metrics, and monitoring.
- **Acceptance:** future/revised observations cannot affect earlier evaluations; duplicate joins fail; delistings and corporate actions reconcile; a 126d request either has mature labels or returns an explicit insufficiency reason; all exclusions are counted by date/horizon.
- **Scope / owner / due:** large / data owner / Phase 0.

### F02 — High: IC significance and annualized Sharpe ignore dependence

- **Location/evidence:** original lines 48–51, 117–121, 142–143, §§3/6/7: iid t-stat, unconditional R²/hit-rate mappings, and square-root annualization. Principle: numerical contracts.
- **Failure:** daily 21d labels overlap; treating their IC observations as independent can understate uncertainty. Rank IC is not the Pearson input to the arcsine identity or linear R². Serial dependence can invalidate simple Sharpe annualization.
- **Change:** report a specified HAC estimate or date-block bootstrap for mean IC, including horizon/lag rationale and sensitivity. Define Sharpe on realized excess portfolio returns and IR on benchmark-relative returns; report dependence-aware uncertainty and time aggregation. Keep iid expressions only as labeled special cases. See [Newey–West](https://www.nber.org/papers/t0055) and [Lo, The Statistics of Sharpe Ratios](https://rpc.cfainstitute.org/research/financial-analysts-journal/2002/the-statistics-of-sharpe-ratios).
- **Additional diagnostic contract:** a curve against cumulative horizon returns does not identify an exponential alpha half-life. Specify lagged incremental targets, a decay model and fit uncertainty before reporting half-life; a Pearson/Spearman gap similarly requires influence and nonlinearity diagnostics before attributing it to outliers.
- **Acceptance:** iid and serially dependent simulated IC series validate SE behavior over predeclared repeated-seed tolerances; overlapping labels are not treated as independent securities; constant IC/zero return variance returns unavailable; negative predictive R² remains negative; measured hit rate is not filled from IC.
- **Scope / owner / due:** medium / quant lead / Phase 1.

### F03 — High: Selection controls are an open question after the metrics are built

- **Location/evidence:** original lines 54–59 and 209, §§3/11: regimes/horizons are explored before any trial accounting or assessment boundary. Principle: separation of selection and evidence.
- **Failure:** choosing signal sign, horizon, universe, cost assumptions, and verdict thresholds on the same history can manufacture an apparent winner. The production-only registry excludes rejected trials.
- **Change:** predeclare primary estimand, practical threshold, temporal folds, label-availability purge, fold-local transformations, and final assessment policy. Retain candidate families and all trials, including failed/null results. Use a justified selection correction where applicable; a DSR calculation is not a replacement for untouched evidence. [Bailey and López de Prado's DSR paper](https://www.davidhbailey.com/dhbpapers/deflated-sharpe.pdf) addresses selection bias and non-normality, not every source of leakage.
- **Acceptance:** test-window changes cannot change earlier fits; no unavailable training label crosses a fold boundary; every reported winner links its search history and selection window. Unknown historical trial counts are disclosed and prevent a selection-adjusted acceptance claim.
- **Scope / owner / due:** large / quant lead / Phase 0 specification, Phase 1 implementation.

### F04 — High: Breakeven IC is not yet connected to executable net P&L

- **Location/evidence:** original lines 115–133 and 145–147, §§6/7: α changes conventions, volatility and exposure bases are unspecified, turnover is inferred from autocorrelation, and double charging is asserted without inspecting the workbook. Principle: units and accounting invariants.
- **Failure:** rank IC, residual dispersion, spread returns, NAV returns, one-way cost, and round-trip cost can be mixed. A 6bp cost per side differs from 6bp for the full trade; a spread return differs from the return on a gross-1 portfolio.
- **Change:** adopt §14.3's trade/holdings ledger; inspect source workbook formulas and reconcile a hand-worked example before porting. Rank IC does not directly calibrate an expected-return slope. Separate transaction costs from holding/financing costs, as illustrated by the [official Cvxportfolio cost model contract](https://www.cvxportfolio.com/en/stable/costs.html); this is a reference, not a dependency requirement.
- **Acceptance:** entry/hold/exit, both trade sides, drift, split, borrow, hedge, and cash reconcile to NAV; zero trades incur zero trading cost; increasing cost with fixed trades cannot improve net P&L; analytical and replay results agree under the same assumptions. Record whether 6bp means one-way or round-trip before claiming a workbook defect.
- **Scope / owner / due:** large / quant and execution owners / Phase 0 specification, Phase 2 implementation.

### F05 — High: Orthogonalized IC cannot decide portfolio inclusion

- **Location/evidence:** original lines 69–79, §4: “only worth analyzing further” and “the number that decides inclusion.” Principle: decision policy and proxy validity.
- **Failure:** residualizing only the candidate and then ranking is not general partial rank correlation. Collinearity makes a projection unstable; weak standalone alpha can provide hedging or interaction value. Strong residual IC can still lose after constraints and turnover.
- **Change:** specify intercept, transformations, missingness, weights, rank/conditioning checks, and regularization for the diagnostic projection. Use compatible feature correlations for diagnostics and realized strategy correlations for portfolio math. Consume the externally chosen combination and evaluate it against a frozen baseline on identical held-out dates, using the same declared risk budget and execution assumptions. Diagnostic residualization of a candidate against baseline signals remains in scope; residualization of return labels and allocation fitting are upstream.
- **Acceptance:** duplicate/nearly duplicate signals produce a stable documented outcome; adding a redundant candidate does not manufacture gain; hedge and interaction fixtures are not automatically rejected by a pairwise screen; report incremental net utility and uncertainty from replay.
- **Scope / owner / due:** large / quant lead / Phase 3.

### F06 — High: Combination formulas omit their admissible domains

- **Location/evidence:** original lines 83–90, §4: linear R² and Sharpe equations next to rank-IC diagnostics; finite-correlation ceiling generalized to decorrelated signals. Principle: explicit mathematical preconditions.
- **Failure:** combining estimates from different samples or confusing forecast and strategy-return correlations can produce impossible R² or exaggerated gains. At `abs(ρ)=1`, the two-predictor formula divides by zero. Negative fixed equicorrelation cannot remain valid for arbitrarily large n.
- **Change:** label linear Pearson R² formulas as same-target, same-sample population/in-sample OLS relationships; label Sharpe formulas with equal-SR/weight or unconstrained-optimal assumptions as applicable. Validate the joint correlation matrix, numerical rank, PSD tolerance, and `−1/(n−1) ≤ ρ ≤ 1` for finite equicorrelation. The infinite-n ceiling requires fixed positive ρ. Use stable solves rather than explicit inversion.
- **Acceptance:** compare against direct regression/portfolio variance for valid synthetic matrices; reject incompatible joint correlations; handle singular cases explicitly; `ρ=0` gives `sqrt(n)` and `ρ=1` identical strategies give no diversification improvement. Never silently clip impossible R² into plausibility.
- **Scope / owner / due:** medium / quant lead / Phase 3.

### F07 — High: “Effective breadth” can be infinite and is not calibrated to achieved IR

- **Location/evidence:** original lines 96–107, §5: product of average-correlation and AR(1) adjustments, described as directionally correct. Principle: model validity and failure handling.
- **Failure:** N=100 and average ρ=−.005 imply 198 effective names; ρ=−1/99 makes the denominator zero. Factor neutrality itself can induce negative correlations. Signal persistence is not necessarily IC or P&L dependence, and time/asset dependence need not be separable.
- **Change:** demote breadth to a sensitivity diagnostic with an explicit model and domain; report covariance concentration and portfolio risk alongside it. Any eigenvalue-based concentration measure must be labeled as such, not renamed independent predictive bets. Keep achieved IR from replay separate from idealized IC/breadth scenarios.
- **Acceptance:** negative-correlation, block-correlated, degenerate, and time-varying fixtures cannot create an acceptance or a finite number from a zero denominator. No unvalidated breadth quantity is consumed by verdict policy.
- **Scope / owner / due:** medium / quant lead / Phase 4.

### F08 — High: Residual returns are treated as independent and economically tradable

- **Location/evidence:** original lines 32–35, §2: residual returns assumed uncorrelated and raw returns automatically taint the report. Principle: estimand and data lineage.
- **Failure:** a fitted factor residual can retain dependence; revised exposures can leak; residual diagnostic profits omit the costs of achieving the corresponding exposures.
- **Change:** distinguish externally supplied residual targets, raw total-return diagnostics, and implementable portfolio/hedge returns. Require upstream evidence that exposures use as-of data; ex-post realized factor returns may define labels but cannot enter decisions before availability. Retain the external residualizer/data manifest, without fitting that model here.
- **Acceptance:** precomputed factor-only and correctly residualized fixtures preserve both target views; missing/incompatible upstream manifests are rejected; new upstream revisions cannot silently alter an old replay; supplied hedge costs enter net P&L. Upstream model correctness remains the provider's responsibility.
- **Scope / owner / due:** medium / data and quant owners / Phase 0 specification, Phase 2 evidence.

### F09 — High: Current registry state cannot reproduce historical marginal value

- **Location/evidence:** original lines 15 and 181–183, §§1/9: live weights and `(signal, config hash, as-of date)` are the only stated identity. Principle: immutable evidence and temporal state.
- **Failure:** changing a live weight, data vintage, code version, or factor model changes a prior result under the same key. A hindsight comparison to today's baseline can be mistaken for a historical deployable decision.
- **Change:** use §14.5's immutable baseline/run manifests. Distinguish `historical-as-known` evaluation from `current-baseline historical counterfactual`; record signal invention/availability and membership history for the former.
- **Acceptance:** old evidence reproduces within declared numeric tolerances after live weights and source data change; manifests distinguish both evaluation modes; an unavailable vintage blocks reconstruction instead of substituting current data.
- **Scope / owner / due:** large / engineering and data owners / Phase 0 identity contract, Phase 3 persistence.

### F10 — High: The scorecard lacks invalid states and a reproducible acceptance policy

- **Location/evidence:** original lines 155–175, §8: four verdicts, point estimates, unspecified thresholds, apparently precise AUM and ΔSR. Principle: state transitions and error handling.
- **Failure:** no-data, stale-data, failed models, or wide intervals can collapse into a plausible verdict. A research recommendation can be confused with permission to alter the production baseline.
- **Change:** implement §14.4 status/verdict separation, predeclared predicates and minimum evidence requirements, machine-readable reasons, full provenance, and a separate promotion action.
- **Acceptance:** insufficient/stale/failed runs cannot emit acceptance; changing thresholds creates a new policy version; boundary cases are tested; report and JSON agree; every recommendation reconstructs from the recorded observations and predicates.
- **Scope / owner / due:** medium / research decision owner / Phase 0 policy outline, Phase 5 implementation.

### F11 — High: Nightly reevaluation can report immature labels or partial success

- **Location/evidence:** original lines 181–182 and 197, §§9/10: nightly DAG without maturity, retry, concurrency, or publication semantics. Principle: transactional boundaries and operability.
- **Failure:** the newest 63d labels do not exist; silently truncating them changes the period. Retries can duplicate runs, baseline edits can mix snapshots, and a crash can publish a report without complete evidence. Missing or overdue evaluation can look like healthy silence.
- **Change:** schedule by horizon-specific label watermark and expected market calendar; freeze inputs at start; use unique run identity, bounded attempts, and atomic completion. Monitor expected runs independently of whether jobs emit success events.
- **Acceptance:** concurrent identical requests publish one canonical completed result; crashes before/after artifact publication recover without false success; unavailable long-horizon labels are explicit; overdue job, stale input, and actual measured decay have distinct alerts. Backfills cannot overwrite newer live status.
- **Scope / owner / due:** large / engineering and operations owners / Phase 3 publication, Phase 6 scheduling.

### F12 — Medium: Capacity and decay outputs imply unsupported precision

- **Location/evidence:** original lines 129–133 and 169–170, §§6/8: square-root impact, zero-crossing AUM, fixed annual decay. Principle: model-domain limits.
- **Failure:** capacity may bind on participation or borrow before net Sharpe crosses zero. A model calibrated at small trades can extrapolate to an implausible AUM; a 5% haircut need not cover regime reversal.
- **Change:** parameterize market/venue/time-specific impact and holding costs with validity ranges; sweep feasible AUM and realistic alpha/cost scenarios. Define crossing interpolation and report “outside evaluated range,” “already unviable,” or binding constraint instead of inventing a scalar.
- **Acceptance:** zero ADV, missing borrow, infeasible participation, no crossing, and multiple crossings have explicit outcomes; both gradual and abrupt alpha loss are reported; the report identifies assumptions separately from observed estimates.
- **Scope / owner / due:** medium / execution owner / Phase 2.

### F13 — Medium: No owned production baseline, quality gate, or dependency boundary

- **Location/evidence:** original lines 3, 60, 173, 179–198: Python/pytest/Postgres/Airflow/plotting are named, but build, ownership, package boundaries, and delivery evidence are absent. Principle: dependency rule and reproducible delivery.
- **Failure:** calculations can become coupled to database sessions and Airflow, or plotting dependencies can block batch evaluation; notebook/package behavior can diverge. A dependency update can alter numeric results without evidence.
- **Change:** use the quant archetype and §14.6 architecture; pin runtime/dependencies, set meaningful quality gates, keep reporting optional at the boundary, and add package/container smoke evidence. Confirm `binspect` API/license/availability before relying on it; a simple plotting adapter is sufficient if it is unavailable.
- **Acceptance:** core evaluation runs with in-memory adapters and no database, Airflow, network, or plot renderer; frozen clean install, lint/format, strict typing, focused numerical tests, integration tests, build and smoke checks pass. Dependency upgrades run numeric regression checks.
- **Scope / owner / due:** medium / engineering owner / Phase 0 foundation, Phase 6 deployment.

### F14 — Medium: Data rights, recovery, and resource budgets are unspecified

- **Location/evidence:** original lines 181–183, §9: “every report ever produced” with no retention, access, backup, or scale contract. Principle: data ownership and bounded operations.
- **Failure:** unrestricted retention may conflict with feed licenses; reports can expose proprietary signals; a database loss may destroy baseline history; dense covariance matrices or whole-history panels can exceed memory.
- **Change:** classify inputs/outputs and define authorized retention, credentials, database roles, report access, backup/restore, migrations, row/AUM/candidate limits, runtime/memory ceilings, and overload behavior in the project brief. Scope a threat model to ingestion, artifact publication, registry mutation, and report output. Avoid raw positions/signals in telemetry.
- **Acceptance:** role restrictions and report escaping are tested; a representative backup restores manifests and referenced datasets within owner-set recovery targets; measured workload fits declared limits; oversize jobs fail explicitly without partially updating results.
- **Scope / owner / due:** medium / data and operations owners / before real-data onboarding; deployment evidence in Phase 6.

### F15 — Medium: The lone proposed synthetic test can pass while the pipeline leaks

- **Location/evidence:** original lines 191 and 200, §10: inject forward returns into a signal to recover known IC. Principle: tests and boundary coverage.
- **Failure:** recovering a population Pearson parameter does not verify Spearman, small-sample behavior, PIT correctness, joins, units, or execution. A leaking fixture can normalize the exact defect validation should prevent.
- **Change:** separate estimator-oracle tests from causal integration fixtures; use known population versus sample targets deliberately. Add falsification cases to each finding's acceptance suite rather than only asserting an attractive IC.
- **Acceptance:** time-shifted/future-available inputs fail PIT integration; null simulations meet predeclared false-positive tolerances; negative/tied/constant/nonfinite inputs have documented results; hand-calculated trade-ledger tests detect one omitted cost side and a shifted execution timestamp.
- **Scope / owner / due:** medium / engineering and quant owners / Phases 0–2.

### F16 — Medium: Random-probe gating has no defined null or decision utility

- **Location/evidence:** original line 92, §4: one random variable is called the right tool and used as an iteration cutoff. Principle: complexity earned by evidence.
- **Failure:** independent noise is not necessarily a valid comparator for temporally dependent, grouped financial predictors; repeated selection can favor noise. Coalition utility and compute growth are undefined.
- **Change:** defer until the core replay exists; specify group utility, null/probe construction, repetitions, selection boundary, uncertainty, and compute ceiling. Compare with regularized and simpler ablation baselines on outer held-out periods.
- **Acceptance:** null/dependent/group-interaction simulations quantify false inclusion and power; held-out net utility justifies added complexity under the same trial accounting. Otherwise retain it as an exploratory backend.
- **Scope / owner / due:** medium / research owner / optional Phase 7.

---

## 14. Proposed implementation contracts and decisions

### 14.1 Project brief and decisions needed before their dependent phase

**Confirmed scope:** cross-sectional signals and time-series signals with one model per instrument/contract, configured horizons/calendars, a research CLI, immutable evidence, and later monitoring. Residualization and portfolio weighting are external workflows. Evaluation consumes their outputs; it does not create factor exposures or allocation weights. No order routing or automatic live-weight changes are implied by a report.

Success means a second reviewer can reproduce a candidate's eligibility, baseline comparison, trades/costs, and recommendation from recorded inputs and policy; the null/leakage/cost adversarial cases must fail appropriately. Predicting a minimum number of accepted signals is not a success criterion.

| Decision | Proposed starting position | Owner / deadline |
|---|---|---|
| Investment decision and practical utility | Compare baseline and augmented portfolios at equal declared risk budget and feasible AUM; specify minimum net utility improvement and guardrails before viewing final assessment | Research decision owner / Phase 0 |
| Markets, currencies, timing, horizon, universe | Cross-sectional and per-instrument/contract time-series modes; exact markets/calendars/currencies, contract/roll identities and executable entry/exit convention require specification | Data + quant / Phase 0 |
| Weighting and constraints | Resolved: external workflow supplies target weights/holdings and constraint, capital, rebalance and policy metadata. This project evaluates those inputs and does not optimize or choose weights | Upstream portfolio owner + engineering / Phase 0 input contract |
| Residualization | Resolved: external workflow supplies residual returns, target/availability semantics and model/data manifest. No factor-model selection/fitting inside this project | Upstream data owner + engineering / Phase 0 input contract |
| Statistical evidence | Complete the template analysis plan: ordered outer assessment, inner selection, label purge, primary outcome, uncertainty, multiplicity, candidate ledger, and predeclared failure rules | Quant / Phase 0 |
| Baseline semantics | Separate historical-as-known from today's-baseline counterfactual; never silently substitute one for the other | Research owner / Phase 0 |
| Deployment and storage | Pure calculation core; Postgres metadata/baseline snapshots; choose database panel storage versus manifest-verified Parquet using measured volume and licensing | Engineering + data / Phase 0 contract, Phase 3 adapter |
| Evidence thresholds | Owner selects minimum history/coverage and uncertainty thresholds, including liquidity/regime slices, before consequential evaluation; unset policy yields insufficient-evidence | Research owner / Phase 0 |
| Delivery constraints | Name owners, implementation budget/deadline, job freshness target, representative data shape, runtime/memory limits, recovery targets, and retention; currently unknown | Project + operations owners / before scheduling or real-data persistence |

Unresolved choices above do not prevent synthetic scaffolding. They prevent claims that depend on their answer. Record consequential choices as ADRs when the project is created.

### 14.2 Panel, availability, and sample contract

- Keys include stable instrument ID, observation/decision timestamp, signal version, and data vintage. Retain source event time, `available_at`/first-observed time, and revision identity; distinguish knowledge time from economic effective time.
- Normalize timestamps to UTC while preserving the declared exchange session/calendar. Define close/open auctions, trading-day horizons, half-days, holidays, timezone transitions, and price convention. Derive `label_start`, `label_end`, and `label_available_at` from the executable policy.
- No feature may arrive after its decision; no training label may be used before its availability. At evaluation cutoff, immature future labels are unavailable. A split purges unavailable/overlapping training outcomes according to the analysis plan.
- PIT universe includes entry/exit and delisting treatment, corporate actions, ticker changes, tradability, suspensions, missing/stale quotes, and currency/FX policy. Define total-return adjustments and whether prices are executable observations or adjusted series.
- Enforce unique join keys, declared join cardinality, numeric/finite domains, signal scale/orientation, minimum cross-sectional counts, tie/constant handling, weights and coverage. Never globally inner-join all horizons and silently shrink the sample. Use paired sample rules for baseline/candidate comparisons.
- Any outlier, winsorization, imputation, normalization, or regime threshold learned across dates is fit within training data; predeclared decision-time cross-sectional transforms use only eligible contemporaneous values. Preserve masks, exclusion counts, and versions in evidence.

### 14.3 Portfolio and cost accounting contract

The authoritative economics output is a time series of net portfolio returns from actual simulated holdings and trades, not an IC-to-Sharpe conversion.

```text
externally supplied target holdings + frozen policy/constraint manifest
    -> validate identity, availability, coverage and declared limits
    -> trades versus drifted pre-trade holdings
    -> fills, cash, hedge, borrow and financing ledger
    -> marked NAV and net excess/active return series
    -> paired baseline/augmented utility and uncertainty
```

For one explicitly defined interval, let `q_i` be signed filled trade dollars, `V_pre` pre-trade NAV, and `c_i` cost per absolute traded dollar for that trade side. Then:

```text
trading_cost_dollars = sum_i(abs(q_i) * c_i)
turnover_abs = sum_i(abs(q_i)) / V_pre
net_pnl_dollars = marked_gross_pnl_dollars
                  - trading_cost_dollars - holding_and_financing_costs
```

Declare whether a displayed “one-way turnover” equals `turnover_abs / 2`; never apply that convention silently. The ledger must specify cost timing, cash treatment, deposits/withdrawals, dividend ownership, marks, unfilled orders, borrow availability, and daily NAV reconciliation. Both entry and exit are charged when traded. Include drift and universe changes even when signal values do not change.

The analytical shortcut `alpha_h = beta_h * score` needs a calibrated horizon-specific slope. Only under an appropriate linear Pearson model can `beta_h` be written as `IC_Pearson,h * sigma_return,h / sigma_score`. A chosen score spread then yields gross spread edge. Convert to the same NAV/gross-exposure basis as costs before solving a breakeven IC. Label `sigma` as time-series risk, cross-sectional dispersion, or residual dispersion; they are not interchangeable. Do not apply `sqrt(h)` to rank IC or expected alpha.

Run supplied baseline and augmented portfolios on the same dates and inputs. Require upstream provenance showing how combination weights were fitted/selected using development/training data and applied forward; do not fit them here. Net incremental costs are `cost(augmented trades) − cost(baseline trades)` under portfolio-level netting, not necessarily standalone candidate cost. Retain daily paired returns, trades, risk/exposure paths, utility delta, and dependence-aware confidence intervals. Missing external weights/holdings yield `economics-unavailable` for the affected metrics, while valid standalone diagnostics remain usable. A capacity sweep may scale a supplied policy only within its declared rules; if it requires reoptimization, request upstream scenario weights rather than silently adding an optimizer.

### 14.4 Evidence status, report, and verdict policy

- Separate `status` from `verdict`: `invalid-data`, `failed`, `stale`, and `insufficient-evidence` are not economic rejections. Only an eligible valid run can have a verdict.
- A versioned policy declares primary utility, practical hurdle, uncertainty estimator/level, coverage/history requirements, selection treatment, cost/capacity stresses, and risk limits. An unset predicate cannot default to passing. `accept-small` requires an explicit feasible size cap and all evidence gates; it is not a workaround for inadequate evidence.
- Store each predicate's input, threshold, result, reason code, and links to evidence. Report uncertainty, sample dates/counts, current label watermark, baseline identity, target type, execution and cost convention, trial history, and unsupported assumptions beside estimates.
- JSON is the canonical report data; HTML/plots/tables consume it and verified referenced evidence and cannot recompute business rules. Apply §8's render manifest, parity, export, accessibility and privacy contracts. Escape user-controlled titles/metadata; missing renderer support must not alter numerical results.
- Promotion/retirement of live registry membership is a separately authorized, versioned event with prior state and rollback reference. Monitoring can recommend action but cannot change weights as a side effect of evaluation.

### 14.5 Storage, evidence identity, and publication

- Version `signal_definitions`, `baseline_snapshots`, `research_studies/trials`, input manifests, and policy/config schemas. Track effective and recorded times for registry membership and weights. Keep rejected candidates outside the live set but inside permitted research history.
- Define an explicit empty-registry baseline, such as cash or a declared domain strategy. Mark marginal IC/Sharpe quantities unavailable where undefined (including zero-volatility cash); compare net utility without inventing baseline Sharpe. Reject candidate self-comparisons and document partial signal-history coverage.
- Derive evaluation identity from canonical config/plan, input hashes/vintages, code revision, dependency lock, signal version, baseline snapshot, seed, calendar, and all relevant cutoffs. Separate this deterministic identity from attempt ID and wall-clock execution time. Define canonical serialization and numeric comparison tolerances.
- Runs progress `pending → running → succeeded | failed | cancelled`; retries are bounded attempts for the same identity. One frozen snapshot is used throughout. Publish immutable verified artifacts first, then atomically mark the database record complete with manifest/hash references. Consumers read only complete verified evidence. Recover or garbage-collect orphan artifacts under retention rules.
- Migrations are versioned and tested against empty and prior schemas. Define unique constraints, transaction isolation, statement timeouts, concurrent-run conflict handling, and backfill publication rules. No retry may overwrite historical evidence or promote incomplete output.
- Restore exercises must recover database records **and** their referenced data/evidence versions. Retention expiration must identify which old reports can no longer be reproduced; hashes alone do not reconstruct missing licensed inputs.

### 14.6 Architecture and production-template baseline

This is a proposed dependency map; there is no implemented graph to certify yet.

| Boundary | Responsibility and dependency direction |
|---|---|
| Domain | Panel and external-output contracts, metrics, accounting/cost evaluation, uncertainty results, verdict predicates; no factor-model fitting or allocation construction; no Postgres, Airflow, environment, network, or rendering imports |
| Application | `evaluate`, `compare_to_baseline`, `publish_report`, `monitor`; owns run identity, snapshot scope, and publication coordination |
| Owned ports | Read an immutable input/baseline snapshot and publish/load evidence; introduce only where needed for real I/O substitution and fault tests |
| Adapters | Postgres, manifest-verified datasets, plotting, CLI, scheduler; depend inward on application/domain contracts |
| Composition root | Selects adapters, validates configuration, and supplies clock/randomness and explicit runtime limits |

Start from `python-data-quant`, retaining Python 3.12 as the template default, `src/`, `uv.lock`, Polars, explicit NumPy/Statsmodels boundary, Ruff, strict Pyright, pytest, and reproducibility artifacts. Choose supported runtime/dependency versions at implementation time; inherited sample regression/validation code must be adapted to panel data and these statistical contracts. An example HC3 regression is not a solution to serially dependent IC inference.

Required project artifacts include a completed brief and statistical analysis plan, README, contribution/security/reproducibility guidance, owner-selected license, changelog, `.env.example`, safe ignores, ADRs, `AGENTS.md`, bounded `PROJECT_MEMORY.md`, and a release checklist. Expose `make setup`, `make check`, and `make build`; CI uses a frozen lock, immutable action pins, numerical regression tests, disposable-Postgres integration checks, coverage policy, and built-package smoke checks. Keep binspect/plotting interoperability narrow and documented.

For the operational CLI/nightly job, add a non-root container pinned by digest with locked runtime dependencies, smoke evidence, deployment rollback, and supply-chain audit/SBOM evidence. Nightly evaluation is batch work; require representative throughput, runtime, memory and deadline measurements, not a low-latency C++ subsystem. Structured telemetry should expose run failures, stale watermarks, coverage, durations and retry exhaustion with safe IDs and stable codes; logs must not contain raw signals, positions, credentials, or licensed data. Name an alert owner and recurring review cadence before rollout.

---

### 14.7 Time-series models and generalized diagnostics

- **Evaluation unit:** `(signal_definition, model_version, instrument_id, contract_id)` with contract identity optional only for non-contract instruments. Each instrument/contract has its own predictions, labels, availability, temporal folds, sample counts, diagnostics and assessment record. Shared code must not imply a pooled fit. Record any upstream shared training or parameters as provenance.
- **Temporal metrics:** calculate Pearson/Spearman correlation and predictive R² within each model's eligible time sample, with dependence-aware uncertainty. Do not label the temporal correlation distribution as a cross-sectional per-date IC series. Report aggregate results separately, with a declared aggregation policy and instrument coverage; portfolio performance uses externally supplied weights.
- **Quantiles:** reuse binning, return summaries, monotonicity and plotting with an explicit grouping axis. For time-series mode, construct score bins within each instrument/contract from training-only boundaries and apply those boundaries forward; define tie, sparse-bin, out-of-range and minimum-count handling. Combine comparable within-model bin summaries only through an explicit reporting aggregation; do not pool raw scores across unrelated scales. Those bins are diagnostics, not a new trading-weight policy.
- **Implemented descriptive quantile policy:** explicit single training cutoff; pre-cutoff scores only; empirical inverse-CDF cuts, collapsed ties, right-closed bins and counted tail extrapolation. Training labels never fit boundaries. Report eligible/missing/immature counts, means, high-minus-low spread and complete-bin monotonicity, with nulls/reasons for unavailable evidence. Cross-sectional mode uses per-model historical reference cuts with per-date evaluation—not per-date equal-count ranks. Each time-series instrument/contract fits separately. Independent section v2, model-level notebook charts, exact tables and partial exports are implemented; full report v1 is unchanged and cannot supply quantile evidence. See [calculation/limits](QUANTILES.md), [ADR 0004](adr/0004-fixed-quantile-bins.md) and [verification](QUANTILE_VERIFICATION.md). This does not close temporal-fold, uncertainty, roll-stitching, breadth or trial-history gates. Changes to cutoffs/bins after inspecting outcomes are research trials, not display settings.
- **Breadth:** treat instrument/contract model outcomes as aligned streams. Reuse covariance/dependence diagnostics across streams and temporal diagnostics within each stream. Multiple contracts on one underlying can be strongly dependent; one model is not automatically one independent bet. Retain F07's invalid-domain and uncertainty controls, and report sample overlap and missing histories rather than filling absent returns with zero.
- **Contract semantics:** distinguish individual listed contracts from continuous research series. Declare roll mapping, expiry, contract multipliers, quote/currency units and treatment of overlaps/gaps. Do not join different contracts into one model without a separately declared continuous-series identity. External positions determine the actual roll trades and costs.
- **Acceptance:** a single-instrument sample produces temporal metrics/quantiles without requiring a cross-section; two identical instrument streams do not double effective independent breadth; heterogeneous score scales cannot change within-model bin assignments through unrelated instruments; future test values cannot move training bin boundaries; roll/gap/short-history fixtures have explicit outcomes. Selection history identifies instrument/contract models and searched variants across the declared hypothesis family.

### 14.8 Declared fold audits and local trial tracking — development slice

`audit_folds` accepts explicit ordered, nonoverlapping half-open test decision windows and accounts for every row. Training candidates require nonmissing labels available strictly before `test_start - gap_seconds`; equality is purged, and gap/unavailable/missing/outside reasons are disjoint. No calendar gap is inferred. `evaluate_fold_section` reuses standalone/coverage/quantile calculations on supplied test predictions; it never calls the inherited regression fitter. Fold quantiles deliberately apply stricter training eligibility than the original score-only fixed-cutoff API. Test label maturity is evaluated at report `as_of`. Audit rows, test identities, input/fold hashes and unverified upstream OOS status remain visible through notebook tables, captions and partial section exports.

`TrialLedger.run` commits a request before computation and appends exact computed/unavailable section evidence or a sanitized failure class. Duplicate IDs fail; interruptions or failed publication remain visibly registered/unfinished. Standard-library SQLite transactions and hash chaining supply bounded local integrity checks, not protected production history. Unknown historical searches prevent any selection-adjusted acceptance claim. Local timestamps do not prove ex-ante human choice; omitted/tail-deleted/fully rewritten histories require external anchors and governance to detect. Real journals require private storage and backup; no server or production registry is deployed. See [contracts and limitations](TEMPORAL_TRIALS.md), [ADR 0005](adr/0005-fold-audits-and-local-trials.md), and [executed evidence](TEMPORAL_VERIFICATION.md).

**Next evidence:** upstream fold-local fitting/selection attestations; a declared nested-selection and final-assessment policy; justified dependence-aware inference and null simulations; a complete hypothesis family/history and selected multiplicity policy. Nonoverlapping decision windows do not establish independent forward labels. These remain open; this slice does not close F02/F03 or the full Phase 1 gate.

### 14.9 Conditional uncertainty — development slice

An independent schema-v3 section adds explicit moving-block percentile intervals and replicate standard errors. Time-series models resample score/return pairs separately per instrument/contract and recompute Pearson/Spearman correlation (including ranks). Cross-sectional models resample the date-IC sequence and estimate equal-date mean IC. Numerical policy declares metric, block length, confidence, replicates, seed, elapsed-time grid and minimum history; no automatic estimator selection. Missing or irregular time points, inadequate block/history floors and degenerate replicates produce unavailable interval evidence. Counts, assumptions, exact bounds, policy and unadjusted status are visible in notebook tables/charts and partial exports, and the fold/trial APIs register the same configuration.

The prespecified iid/AR(1) null simulations are regression evidence, not general financial calibration. Intervals remain conditional on approximate stationarity and adequate block choice, are not selection-adjusted, and do not imply a winner or verdict. No HAC, automatic calendar handling, simultaneous-model intervals, quantile-spread intervals or corrected p-values are added. See [method and sources](UNCERTAINTY.md), [verification](UNCERTAINTY_VERIFICATION.md), and [ADR 0006](adr/0006-conditional-block-uncertainty.md). Actual final-assessment window, hypothesis-family/history, authority and protected storage remain owner decisions; [FINAL_ASSESSMENT.md](FINAL_ASSESSMENT.md) is a checklist, not an implemented lock. These open requirements still prevent full F02/F03 and Phase 1 closure.

## 15. Improvement plan and follow-up gates

Target outcome: one auditable, repeatable assessment whose financial verdict cannot be produced from invalid, leaked, unreconciled, or stale evidence. Baseline at review: this plan had no implementation evidence; current scoped evidence is recorded below. Guardrails: PIT semantics, NAV reconciliation, immutable history, explicit unsupported states, and no automatic live promotion. Stop/rollback any release that changes those invariants or cannot reproduce prior evidence within declared tolerance.

| Priority | Smallest delivery slice | Findings | Acceptance evidence | Proposed owner | Due | Status |
|---:|---|---|---|---|---|---|
| 1 | Brief + analysis plan + schema/portfolio/baseline contracts | F01, F03, F04, F08–F10 | Completed decisions, explicit timestamps/units, prespecified utility and folds | Research, quant, data | Phase 0 | Partial: development brief, analysis plan and external-input contracts; consequential policy/baseline pending |
| 2 | CLI fixture → ledger/metric → immutable evidence/report | F13, F15 | Clean frozen install/build, causal/invalid-input fixtures, offline core | Engineering | Phase 0 | Local descriptive slice verified; see INITIAL_VERIFICATION.md; full production gate pending |
| 2a | Offline graphics/table bundle shared with Jupyter | F10, F13–F15 | §8.4: HTML/CSV/SVG/PNG, value parity, safe metadata, unavailable states, manifest and installed-wheel/kernel smoke | Engineering, research reviewer | Phase 0R, expanded through Phase 5 | Local descriptive implementation; see REPORTING_VERIFICATION.md; production and advanced views remain open |
| 2b | Independent notebook sections and customizable composition | F10, F13–F15 | §8.5: isolated section evaluation, caller axes, display options/subsets, numerical parity, partial manifests and executed cookbook | Engineering, research reviewer | Phase 0N | Local core implemented and verified; see COMPOSITION_VERIFICATION.md; optional widgets/layout capture remain deferred |
| 3 | Temporal validation + trial ledger + uncertainty | F02, F03, F15 | Fold-leakage and null/dependence simulations; retained OOS observations | Quant | Phase 1 | Partial: folds, local journal and conditional block intervals implemented; upstream OOS, nested/final assessment, complete history and corrected decision policy remain open |
| 3b | Declared supplied-signal folds + local trial journal | F03, F10, F15 | Purge/equality/gap/row accounting, registered-before-evaluation, failed/unavailable/interrupted trials, transactional duplicates, notebook and installed-package checks | Engineering, research reviewer | Phase 1 subset | Local descriptive implementation; see TEMPORAL_VERIFICATION.md; no upstream OOS certification, final holdout lock or correction policy |
| 3c | Conditional block uncertainty + notebook interval views | F02, F03, F10, F15 | Paired/date resampling checks, prespecified null simulations, immutable policy, failure states, trial/plot/export parity | Quant, engineering, research reviewer | Phase 1 subset | Local conditional implementation; see UNCERTAINTY_VERIFICATION.md; no final-assessment or selection-adjusted claims |
| 3a | Descriptive fixed-training quantiles with independent notebook views | F02, F10, F15; §14.7 | Hand-worked bins, future-value invariance, ties/sparsity/maturity, model-scale isolation, kernel and installed-wheel checks | Engineering, research reviewer | Phase 1 subset | Local implementation; see QUANTILE_VERIFICATION.md; no inferential or full Phase 1 completion claim |
| 4 | Cost/portfolio reconciliation + feasible AUM stress | F04, F08, F12 | Hand-worked ledger, source workbook reconciliation, cost monotonicity and capacity boundaries | Quant, execution | Phase 2 | Proposed; unimplemented |
| 5 | Baseline snapshots + paired marginal replay | F05, F06, F09 | Same-date constrained net utility, singularity cases, historical reconstruction | Quant, engineering | Phase 3 | Proposed; unimplemented |
| 6 | Atomic run publication and database recovery | F09, F11, F14 | Retry/crash/concurrency/migration/restore integration evidence | Engineering, operations | Phase 3, restore by Phase 6 | Proposed; unimplemented |
| 7 | Optional breadth scenarios; verdict/report policy | F07, F10 | Invalid-domain cases, no heuristic gate dependency, JSON/render parity | Quant, research owner | Phases 4–5 | Proposed; unimplemented |
| 8 | Monitored scheduled artifact | F11, F13, F14 | Freshness/maturity alerts, bounded failures, image smoke, workload budget, exercised rollback | Operations | Phase 6 | Proposed; unimplemented |
| 9 | Probe/Shapley evidence experiment | F16 | Nested comparison, null calibration, compute bound, incremental net value | Research | Optional Phase 7 | Deferred |

Owners and calendar delivery dates remain unassigned; phase deadlines are dependencies, not staffing commitments. Follow-up review occurs at the first end-to-end artifact, completion of paired out-of-sample economics, and before scheduled production use. Close a finding only by linking the accepted decision and executed evidence, including commands, revision, input/plan hashes and result. Keep failed, inconclusive and waived findings visible with their rationale; do not report a documentation amendment as a tested fix.

## 16. Review change log

| Date | Change | Verification status |
|---|---|---|
| 2026-09-11 | Applied the local production project template to this plan; integrated 16 severity-ranked findings, corrected misleading formula/decision claims, revised phasing, and added explicit data, economics, evidence, storage, and operational contracts | Document/source inspection and analytical counterexamples only; implementation acceptance evidence remains outstanding |
| 2026-09-11 | Incorporated owner decisions: external residualization and weights; time-series models per instrument/contract; generalized quantile/breadth contracts and external-output validation | Scope/document update; future implementation checks remain required |
| 2026-09-11 | Linked signed-in Safari survey of 79 Systematic Long Short archive posts; identified four direct multiple-testing discussions and two explicit Bonferroni references | Targeted article-text scan and inspection of matching passages; multiple-testing policy remains open |
| 2026-09-11 | Added first-class graphical/table report bundle, evidence-dependent view inventory, phased delivery and rendering acceptance criteria (§8, Phase 0R) | Plan amendment only; graphical and tabular renderer remains unimplemented |
| 2026-09-11 | Implemented shared descriptive notebook/HTML/figure/table views; extended locked dependencies, CI and infrastructure guidance using the production template | Local evidence in REPORTING_VERIFICATION.md; no deployment or advanced analytical claims |
| 2026-09-11 | Added owner requirement for independently usable notebook report sections, flexible visualization/table controls, custom composition and partial exports (§8.5, Phase 0N) | Plan amendment only; expanded composable APIs require implementation and acceptance evidence |
| 2026-09-11 | Implemented independent descriptive sections, configurable notebook panels, caller-owned axes and partial exports; added cookbook and installed-wheel section smoke | 130 local tests, 92.04% coverage, both kernel executions, build/audit and installed-package checks; details in COMPOSITION_VERIFICATION.md |
| 2026-09-11 | Implemented explicit training-only quantile sections with per-contract fits, coverage/mean/spread tables, configurable charts and an independent Jupyter notebook | Scoped local evidence and limitations in QUANTILE_VERIFICATION.md; temporal inference, trial ledger and consequential decision policy remain open |
| 2026-09-11 | Added declared fold audits and row identities, conservative training-label purge, independent fold sections, and a transactional local trial journal with failure history | Scoped evidence in TEMPORAL_VERIFICATION.md; four notebooks, original models external, historical search completeness unknown; no inference/production approval |
| 2026-09-11 | Added conditional moving-block intervals with explicit policy, per-contract/date estimands, a fifth notebook, and a final-assessment decision checklist | Scoped evidence in UNCERTAINTY_VERIFICATION.md; no selected-model correction, final-assessment lock or production approval |

## Implementation status — 2026-09-11

Red Five has started as a local `python-data-quant` project. The initial Phase 0 slice includes strict external-input contracts, descriptive metrics in both evaluation modes, supplied-weight interval accounting, CLI and non-overwriting JSON evidence. That slice passed local lint, typing, 77 tests (91.34% package coverage), dependency/license audit, build and installed-wheel smoke. See [README](../README.md) and [initial evidence](INITIAL_VERIFICATION.md); the full Phase 0 gate is not yet claimed complete. This is not a deployed service or an approved financial decision system.

The reporting/composition slices add notebook and offline views plus independent section APIs; their 130-test baseline is recorded in [composition evidence](COMPOSITION_VERIFICATION.md). Fixed-training quantiles and fold/trial support are recorded in [quantile verification](QUANTILE_VERIFICATION.md) and [temporal verification](TEMPORAL_VERIFICATION.md). The latest local extension adds conditional block uncertainty and a fifth notebook; current evidence is in [uncertainty verification](UNCERTAINTY_VERIFICATION.md). Final-assessment/selection policy, breadth, paired marginal replay, Postgres and scheduling remain subsequent gates. No remote CI or deployment is claimed for the current local edits.
