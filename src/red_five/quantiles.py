"""Training-only score bins and descriptive forward-return diagnostics."""

from __future__ import annotations

from bisect import bisect_left
from collections import defaultdict
from dataclasses import asdict, dataclass
from math import ceil, fsum, isfinite

from .contracts import ContractError, EvaluationConfig, Prediction, timestamp
from .visualization import Cell, Table

QUANTILE_FIELDS = (
    "bin",
    "lower_bound",
    "upper_bound",
    "requested_bins",
    "effective_bins",
    "training_observations",
    "observations",
    "eligible_observations",
    "immature_labels",
    "missing_mature_labels",
    "out_of_range",
    "mean_return",
    "status",
    "reason",
    "spread",
    "spread_reason",
    "monotonicity",
    "monotonicity_reason",
)


@dataclass(frozen=True)
class QuantileConfig:
    training_end: str
    bins: int = 5
    minimum_training: int = 20
    minimum_bin: int = 3

    def __post_init__(self) -> None:
        cutoff = timestamp(self.training_end, "training_end")
        object.__setattr__(self, "training_end", cutoff.isoformat())
        if type(self.bins) is not int or not 2 <= self.bins <= 10:
            raise ContractError("quantile bins must be an integer in [2, 10]")
        if (
            type(self.minimum_training) is not int
            or not self.bins <= self.minimum_training <= 100000
        ):
            raise ContractError("minimum_training must be between bins and 100000")
        if type(self.minimum_bin) is not int or not 1 <= self.minimum_bin <= 100000:
            raise ContractError("minimum_bin must be an integer in [1, 100000]")


def _mean(values: list[float]) -> float | None:
    if not values:
        return None
    try:
        # Divide before summing to avoid overflowing on finite large observations.
        result = fsum(v / len(values) for v in values)
    except OverflowError:
        return None
    return result if isfinite(result) else None


def evaluate_quantiles(
    rows: tuple[Prediction, ...],
    config: EvaluationConfig,
    options: QuantileConfig,
) -> tuple[Table, dict[str, object]]:
    cutoff = timestamp(options.training_end, "training_end")
    if cutoff > config.as_of:
        raise ContractError("training_end exceeds evaluation cutoff")
    # One model scale across instruments in cross-sectional mode; one contract
    # history per model in time-series mode. Never fit using evaluation scores.
    training: dict[tuple[str, ...], list[float]] = defaultdict(list)
    samples: dict[tuple[str, ...], list[Prediction]] = defaultdict(list)
    fit_keys: set[tuple[str, ...]] = set()
    for row in rows:
        key = (
            (row.model_id, row.instrument_id, row.contract_id)
            if config.mode == "time_series"
            else (row.model_id,)
        )
        fit_keys.add(key)
        if row.decision_time < cutoff:
            training[key].append(row.signal)
        else:
            evaluation_key = (
                key
                if config.mode == "time_series"
                else (*key, row.decision_time.isoformat())
            )
            samples[evaluation_key].append(row)
    fits: dict[
        tuple[str, ...], tuple[list[float], float | None, float | None, str | None]
    ] = {}
    fitting_evidence: list[dict[str, object]] = []
    for key in sorted(fit_keys):
        scores = sorted(training[key])
        minimum, maximum = (scores[0], scores[-1]) if scores else (None, None)
        reason = (
            "insufficient-training"
            if len(scores) < options.minimum_training
            else ("constant-training-scores" if minimum == maximum else None)
        )
        cuts = (
            []
            if reason
            else sorted(
                {
                    scores[ceil(j * len(scores) / options.bins) - 1]
                    for j in range(1, options.bins)
                    if scores[ceil(j * len(scores) / options.bins) - 1] < scores[-1]
                }
            )
        )
        fits[key] = cuts, minimum, maximum, reason
        fitting_evidence.append(
            {
                "group": key,
                "training_observations": len(scores),
                "cutpoints": cuts,
                "training_min": minimum,
                "training_max": maximum,
                "reason": reason,
            }
        )
        if config.mode == "time_series":
            samples.setdefault(key, [])
    columns = (
        ("model_id", "instrument_id", "contract_id")
        if config.mode == "time_series"
        else ("model_id", "decision_time")
    )
    output: list[tuple[Cell, ...]] = []
    for group, sample in sorted(samples.items()):
        key = group if config.mode == "time_series" else group[:1]
        cuts, minimum, maximum, fit_reason = fits[key]
        effective = 0 if fit_reason else len(cuts) + 1
        buckets: list[list[Prediction]] = [[] for _ in range(max(1, effective))]
        for row in sample:
            buckets[0 if fit_reason else bisect_left(cuts, row.signal)].append(row)
        means: list[float | None] = []
        bin_rows: list[tuple[Cell, ...]] = []
        for i, bucket in enumerate(buckets):
            ready = [r for r in bucket if r.label_available_at <= config.as_of]
            labels = [r.forward_return for r in ready if r.forward_return is not None]
            reason = fit_reason or (
                "empty-bin"
                if not bucket
                else "insufficient-bin-labels"
                if len(labels) < options.minimum_bin
                else None
            )
            mean = None if reason else _mean(labels)
            if mean is None and reason is None:
                reason = "numerical-degeneracy"
            means.append(mean)
            outside = sum(
                1
                for r in bucket
                if minimum is not None
                and maximum is not None
                and (r.signal < minimum or r.signal > maximum)
            )
            bin_rows.append(
                (
                    *group,
                    0 if fit_reason else i + 1,
                    "unavailable"
                    if fit_reason
                    else ("-inf" if i == 0 else repr(cuts[i - 1])),
                    "unavailable"
                    if fit_reason
                    else ("+inf" if i == effective - 1 else repr(cuts[i])),
                    options.bins,
                    effective,
                    len(training[key]),
                    len(bucket),
                    len(labels),
                    len(bucket) - len(ready),
                    len(ready) - len(labels),
                    outside,
                    mean,
                    "available" if reason is None else "unavailable",
                    reason,
                )
            )
        spread: float | None = None
        spread_reason = fit_reason or "tail-bins-unavailable"
        if effective >= 2 and means[0] is not None and means[-1] is not None:
            delta = means[-1] - means[0]
            spread, spread_reason = (
                (delta, None) if isfinite(delta) else (None, "numerical-degeneracy")
            )
        complete = [m for m in means if m is not None]
        monotonicity: str | None = None
        mono_reason = fit_reason or "incomplete-bin-means"
        if effective >= 2 and len(complete) == effective:
            up = all(a <= b for a, b in zip(complete, complete[1:], strict=False))
            down = all(a >= b for a, b in zip(complete, complete[1:], strict=False))
            monotonicity = (
                "flat"
                if up and down
                else "nondecreasing"
                if up
                else "nonincreasing"
                if down
                else "nonmonotonic"
            )
            mono_reason = None
        output.extend(
            (*row, spread, spread_reason, monotonicity, mono_reason) for row in bin_rows
        )
    return Table((*columns, *QUANTILE_FIELDS), tuple(output)), {
        "policy": asdict(options),
        "method": "empirical-inverse-cdf/right-closed",
        "ties": "collapse-repeated-cutpoints; equality-goes-to-lower-bin",
        "out_of_range_policy": "assign-to-tail-bin-and-count",
        "fit_groups": fitting_evidence,
        "training_labels_used": False,
        "scope": "fixed training-reference bins; descriptive, not portfolio returns",
    }
