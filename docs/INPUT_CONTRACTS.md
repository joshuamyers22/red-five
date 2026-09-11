# Evaluation input contracts — v1

Inputs are immutable snapshots supplied by upstream research/portfolio workflows.
The evaluator checks their structure and timing; it cannot authenticate a vendor's
availability claim or infer that an upstream model was trained out of sample.
See `examples/` for complete synthetic files.

## Configuration

`examples/evaluation.json` shows the exact required fields; unknown/missing keys and
duplicate JSON keys fail. Declare `red-five-config/v1`, study ID, signal version,
upstream return-model version, return kind (`residual` or `total`), one horizon,
calendar, evaluation cutoff, mode and minimum observations. The cutoff must include
a timezone offset. `weighting_policy_id` is nullable only when weights are omitted.
All IDs are nonblank, at most 256 characters, without surrounding whitespace or
control characters. No defaults choose your market, weighting, residualizer or
statistical significance policy.

The minimum observation count must be 3–100,000. It governs whether a descriptive
correlation can be displayed, not whether the signal has sufficient evidence for
acceptance. `time_series` groups by model/instrument/contract;
`cross_sectional` groups by model/decision timestamp. Version separate model
variants in `model_id` or separate runs; each time-series model ID identifies one
instrument/contract. Use a stable marker such as `spot` for non-contract instruments.

## Signal CSV

Columns, in order:

```text
model_id,instrument_id,contract_id,decision_time,signal_available_at,label_start,label_end,label_available_at,signal,forward_return
```

- Times are ISO timestamps with explicit offsets, normalized to UTC.
- Require `signal_available_at <= decision_time <= label_start < label_end <= label_available_at`
  and `decision_time <= as_of`.
- The upstream system defines exact horizon/calendar/return construction. Red Five
  does not build labels, fit a factor model or validate exchange-session arithmetic.
- `signal` is finite numeric text. `forward_return` is a finite fractional return
  (`0.01` means 1%) or an empty cell. No other field can be missing.
- A label whose availability exceeds the cutoff is excluded even if its value is
  present. Missing mature labels are counted separately. Neither becomes zero.
- Unique key: model, instrument, contract and UTC decision time. Input row order
  does not change grouping; duplicate timestamps with equivalent offsets fail.
- Ties use average rank. Constant inputs, insufficient counts or numerical
  degeneracy produce unavailable metrics and explicit reasons.

Do not mix horizons or return kinds in one input snapshot. The manifest's declaration
applies to all rows. A model's instrument history is never pooled with another
instrument's observations to manufacture a larger sample.

## Optional supplied-weight CSV

Columns, in order:

```text
portfolio_id,instrument_id,contract_id,decision_time,weights_available_at,label_start,label_end,label_available_at,pre_trade_weight,target_weight,asset_total_return,trade_cost_bps,holding_cost_nav_bps
```

Weights are signed fractions of pre-trade portfolio NAV. Supply the **drifted**
pre-trade weight and the external target weight; Red Five does not construct either.
Asset returns are implementable **total** returns for the supplied interval, even
when the signal diagnostic target is residual. Upstream returns must include the
declared corporate-action, contract multiplier, currency and valuation conventions.

Require weights to be available at the decision and all ledger returns to be mature
at cutoff. Every supplied weight interval must match an instrument/contract/time
interval in the signal panel. The optional ledger may cover fewer dates than the
signal panel; output is explicitly per supplied interval and is not a full-history
portfolio backtest. Constituents within one portfolio/decision must share the same
interval. Duplicate portfolio/instrument/contract/decision keys fail.

Per constituent:

```text
gross_return = target_weight * asset_total_return
trading_cost_return = abs(target_weight - pre_trade_weight) * trade_cost_bps / 10000
holding_cost_return = holding_cost_nav_bps / 10000
net_return = gross_return - trading_cost_return - holding_cost_return
```

`trade_cost_bps` is cost per absolute traded notional, **per side**. An entry and
exit in separate rows are both charged. A flip crosses the full absolute weight
change. `holding_cost_nav_bps` is the per-constituent contribution to portfolio-NAV
holding/financing cost, already sized upstream: do not multiply it by weight again
or repeat a portfolio total on every constituent. Costs must be nonnegative; rebates
need a later explicit contract.

Decimal arithmetic uses 80-digit local precision. Numeric inputs support at most
18 decimal places and absolute value at most `1e12`; these limits bound arithmetic
and are schema limits, not portfolio risk approval. Results serialize as decimal
strings. Cash/funding effects not in supplied returns must be included in supplied
holding/financing costs. No inferred fills, cross-interval NAV chaining, Sharpe,
capacity or optimization is performed. The provider owns position/cash continuity.

## Evidence and failure behavior

CLI file inputs are capped at 16 MiB; CSVs at 100,000 rows. Run identity includes
input/config/analysis-plan/lock hashes, configuration, installed package version,
package source digest and Python/library versions. Paths and execution wall clock
are excluded from deterministic evidence. This version retains descriptive results
and accounting, not full row-level input data; retain the original snapshots to
reproduce them. Content hashes detect changes but cannot reconstruct deleted inputs.

JSON publication uses a same-directory temporary file and an atomic no-overwrite
link. Identical reruns succeed; differing existing evidence or an output symlink
fails. Interrupted staging files may require cleanup; full crash/restore guarantees
and Postgres publication belong to later phases. The trusted local output directory
must not be writable by untrusted users.

Successful calculations produce `data_status: valid` and a decision status of
`insufficient-evidence`, with `verdict: null`. Invalid input/file operations exit 2
and emit one versioned error event to stderr, without raw data or sensitive paths.
`verify` checks stored schema/content and run-identity hashes; it does not rerun
metrics, prove authorship or certify financial assumptions.
