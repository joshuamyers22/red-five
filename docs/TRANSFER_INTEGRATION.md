# Transfer alignment integration

The user corrected the project name from Echo Five to Red Five on 2026-09-20.
The repository was inspected at `c6bae32d40805f185fed1e8b5864dcb183fdbfc5`.
The original Dropbox plan remains unchanged; [the adapted plan](TRANSFER_COEFFICIENT_PLAN.md)
retains its mathematical, statistical and consequential-use acceptance gates.
The linked source note was unavailable locally; no independent paper review is claimed.

## Existing architecture and selected first slice

| Concern | Existing integration | Current delivery |
|---|---|---|
| Package and CLI | `src/red_five`, `red_five.cli:main` | `red-five transfer alignment` and `transfer verify` |
| Pure numerical core | NumPy already locked; supplied weights external | Flat `transfer.py`, immutable tuple input/result types |
| File adapters | `signal_io.read_bytes`, `json_object`, 16 MiB bound | `transfer_io.py`; explicit JSON snapshots, at most 256 assets |
| Identity and publication | `reporting` source/version identity, sealing, atomic hard-link publication | Same publisher; separate `red-five-transfer-report/v1` validation |
| Signal reports and notebooks | Existing v1 reports, composable sections | Existing calculations retained; transfer notebook/render integration deferred |
| Inference | `uncertainty.py` has conditional IC block intervals | No reuse as Sharpe inference without separate estimator/calibration work |
| Portfolio accounting | Decimal supplied-weight interval ledger | Forecast alignment does not infer realized returns or change weights |
| Deployment | Local research package; no deployed service | Explicit config opt-in, `live_eligible=false`; no production release |

Flat modules fit current source hashing (`reporting.source_identity` hashes package
`.py` files). A new subpackage would require changing that identity contract.
There is no new dependency or separate publication mechanism. JSON is appropriate
for a tiny dense snapshot; proposed Parquet/replay commands are later adapters.
Asset order must match exactly. Reordering, PSD projection and covariance repair
are unsupported. Exact symmetry is required even within the declared diagnostic
asymmetry tolerance; callers must resolve/reissue asymmetric source artifacts.

Dense compute is capped at 256 assets and input/output at 16 MiB. These are local
resource guardrails, not representative production benchmarks or latency promises.
No annualization is applied: model Sharpes are for the declared common horizon.
The explicit evaluation timestamp is a caller assertion and is hashed; it is not
proof of historical availability. Identical bytes/config/environment reproduce the
same report. Source SHA-256 identifies the code revision, including uncommitted
source; the environment lock and NumPy/BLAS name/version are recorded separately.
No absolute source paths, alpha, weights, covariance entries or returns are logged.

## Delivered command

```sh
uv run --frozen red-five transfer alignment \
  --forecast examples/transfer-forecast.json \
  --covariance examples/transfer-covariance.json \
  --config examples/transfer-config.json \
  --analysis-plan docs/TRANSFER_COEFFICIENT_ANALYSIS_PLAN.md \
  --output build/transfer-alignment.json
uv run --frozen red-five transfer verify build/transfer-alignment.json
```

`red-five verify` also accepts transfer evidence. Transfer evidence cannot be
rendered using the signal-report renderer. `transfer compare` and batch replay
are not implemented. Failed contracts exit 2 with a stable `TRANSFER_*` reason;
ill-conditioned PD covariance produces a retained `numerically_unreliable` result
with null metrics. Overall evidence status stays `insufficient_evidence` even
when the alignment calculation succeeds.

## Input files and configuration

All fields in the three versioned JSON examples are required; unknown or duplicate
keys fail. Numeric arrays contain finite JSON numbers, not strings or booleans.

| Input | Contract and example |
|---|---|
| Forecast | [Forecast JSON](../examples/transfer-forecast.json): unique ordered asset IDs, expected excess returns, supplied weights, model/universe/snapshot IDs, aware as-of time and horizon |
| Covariance | [Covariance JSON](../examples/transfer-covariance.json): same asset order, risk-model ID, horizon and as-of time; square symmetric PD matrix |
| Configuration | [Config JSON](../examples/transfer-config.json): analysis ID, explicit enable flag, evaluation time and numerical policy |
| Analysis plan | Required nonempty file; example is the [synthetic development plan](TRANSFER_COEFFICIENT_ANALYSIS_PLAN.md) |
| Lockfile | Defaults to `uv.lock`; provide `--lock /path/to/uv.lock` when running outside the repository |

Forecast return units must be `simple_excess_return_fraction`; weight units must
be `fraction_of_nav`; covariance units must be `simple_return_fraction_squared`.
Forecast and covariance as-of times must match after UTC normalization and cannot
exceed `evaluated_at_utc`. Asset vectors/matrix rows and columns must agree exactly;
there is no automatic reordering or repair.

The config requires `enabled: true` to evaluate. `max_condition_number` accepts
[1, 1e12] (example: 1e10). `symmetry_relative_tolerance` and `bound_tolerance`
accept [0, 1e-10] (example: 1e-12). Symmetry tolerance classifies the error;
nonzero asymmetry still fails. Set `diagonal_diagnostic: true` only for a diagonal
matrix; otherwise use false. It adds risk-coordinate means and the optional
Pearson diagnostic without replacing the canonical cosine.

The example produces alignment approximately 1, model and optimal model Sharpe
approximately 0.1414213562, and portfolio risk approximately 0.0707106781 for the
one-day horizon. Its constant risk coordinates make Pearson unavailable (`null`).
Changing inputs, config, plan, code or environment creates a different identity;
use a new output path. Verification needs only the output artifact and checks its
internal integrity, not the authenticity of retained source inputs.

## Python API

The library core performs no file I/O. Supply immutable tuples in identical asset
order and keep provenance in the calling adapter:

```python
from red_five.transfer import AlignmentInput, AlignmentPolicy, calculate_alignment

snapshot = AlignmentInput(
    asset_ids=("A", "B"),
    covariance_asset_ids=("A", "B"),
    expected_excess_returns=(0.01, 0.02),
    implemented_weights=(0.5, 0.25),
    covariance=((0.01, 0.0), (0.0, 0.04)),
)
result = calculate_alignment(snapshot, AlignmentPolicy(diagonal_diagnostic=True))
print(result.status, result.ex_ante_transfer_alignment)
```

The CLI uses this same calculation through `transfer_io.evaluate_alignment`,
which adds file contracts and evidence. Library callers must inspect `status` and
`reason_code` before using nullable metrics. Invalid contracts raise `TransferError`,
a `ContractError` subclass with a stable `.code`.

## Open gates and owners

Josh approved implementation commit `5530c38` for merge to `main` on 2026-09-20.
Engineering discovery and integration are accepted for the first research slice.
Quant, data, independent fixture-review, model-risk and operations reviewer
assignments remain open. Phase 1 independent mathematical review and the full
real-data Phase 0 decisions remain open.
Phases 2–6 require paired-return contracts/calibration, replay, production evidence
and consequential-use decisions. Jobson–Korkie remains blocked by the source
formula issue. PSD risk models require a separate reviewed ADR.

Before real data: define classification/access/retention, strategy semantics,
observation windows and cost bases, minimum sample/coverage, practical Sharpe effect,
bootstrap design and selection policy in the analysis plan. Pure-core fixtures do
not authorize a real-data assessment or validate forecasts.

Rollback: disable alignment with `enabled=false` or stop invoking the command;
keep v1 verification available. No schema or existing artifact migration is needed.
The shared local publisher is atomic and create-only with identical-byte retries;
it does not claim production storage durability, external authenticity or recovery.
