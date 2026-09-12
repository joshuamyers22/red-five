from __future__ import annotations

import csv
import io
from dataclasses import asdict, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import cast

import numpy as np
import pytest

from red_five.composition import PlotOptions, Selection
from red_five.contracts import ContractError, EvaluationConfig, Prediction
from red_five.rendering import verify_bundle
from red_five.reporting import canonical
from red_five.sections import SectionResult, evaluate_section
from red_five.signal_io import digest, json_object
from red_five.temporal import FoldSpec
from red_five.trials import TrialLedger
from red_five.uncertainty import BootstrapConfig, evaluate_uncertainty
from red_five.visualization import mapping, sequence

ROOT = Path(__file__).resolve().parents[1]
CONFIG_BYTES = (ROOT / "examples/evaluation.json").read_bytes()
CONFIG = EvaluationConfig.parse(json_object(CONFIG_BYTES))
OPTIONS = BootstrapConfig("pearson_ic", 8, 200, 123, 0.95, 86400, 32)


def series(seed: int = 1, n: int = 96, rho: float = 0.5) -> tuple[Prediction, ...]:
    rng = np.random.default_rng(seed)
    x, y = 0.0, 0.0
    values: list[Prediction] = []
    for i in range(n + 100):
        x = rho * x + float(rng.standard_normal())
        y = rho * y + float(rng.standard_normal())
        if i >= 100:
            start = datetime(2025, 1, 1, tzinfo=UTC) + timedelta(days=i - 100)
            values.append(
                Prediction(
                    "model",
                    "ES",
                    "March",
                    start,
                    start,
                    start,
                    start + timedelta(days=1),
                    start + timedelta(days=1),
                    x,
                    y / 100,
                )
            )
    return tuple(values)


def csv_bytes(rows: tuple[Prediction, ...]) -> bytes:
    output = io.StringIO()
    writer = csv.DictWriter(
        output, fieldnames=list(asdict(rows[0])), lineterminator="\n"
    )
    writer.writeheader()
    for r in rows:
        writer.writerow(
            {
                k: v.isoformat() if isinstance(v, datetime) else v
                for k, v in asdict(r).items()
            }
        )
    return output.getvalue().encode()


def test_paired_blocks_match_independent_numpy_calculation() -> None:
    rows = series()
    result, _ = evaluate_uncertainty(rows, CONFIG, OPTIONS)
    group_seed = int(digest(canonical(("model", "ES", "March")))[:8], 16)
    rng = np.random.default_rng(np.random.SeedSequence([123, group_seed]))
    draws: list[float] = []
    for _ in range(200):
        indices = [
            i for s in rng.integers(0, 89, 12) for i in range(int(s), int(s) + 8)
        ]
        draws.append(
            float(
                np.corrcoef(
                    [rows[int(i)].signal for i in indices],
                    [cast(float, rows[int(i)].forward_return) for i in indices],
                )[0, 1]
            )
        )
    frame = result.dataframe()
    bounds = np.quantile(draws, [0.025, 0.975])
    assert frame["lower"][0] == pytest.approx(float(bounds[0]))
    assert frame["upper"][0] == pytest.approx(float(bounds[1]))
    assert frame["standard_error"][0] == pytest.approx(float(np.std(draws, ddof=1)))
    assert frame["valid_replicates"][0] == 200


def test_repeatability_order_and_other_model_isolation() -> None:
    original = series()
    a = evaluate_uncertainty(original, CONFIG, OPTIONS)
    assert a == evaluate_uncertainty(tuple(reversed(original)), CONFIG, OPTIONS)
    other = tuple(
        replace(r, model_id="z-model", instrument_id="NQ", signal=1000 * r.signal)
        for r in original
    )
    both = evaluate_uncertainty(original + other, CONFIG, OPTIONS)[0]
    assert both.rows[0] == a[0].rows[0]
    assert a != evaluate_uncertainty(original, CONFIG, replace(OPTIONS, seed=124))


@pytest.mark.parametrize(
    "attack,reason",
    [
        ("missing", "incomplete-time-grid"),
        ("future", "incomplete-time-grid"),
        ("gap", "irregular-time-grid"),
        ("short", "too-few-time-points"),
        ("constant", "constant-score-or-target"),
        ("perfect", "degenerate-bootstrap"),
        ("long-label", "block-shorter-than-label-span"),
    ],
)
def test_unavailable_cases_preserve_reasons(attack: str, reason: str) -> None:
    rows = series()
    if attack == "missing":
        rows = (replace(rows[0], forward_return=None), *rows[1:])
    elif attack == "future":
        rows = (
            replace(rows[0], label_available_at=datetime(2027, 1, 1, tzinfo=UTC)),
            *rows[1:],
        )
    elif attack == "gap":
        rows = rows[:5] + rows[6:]
    elif attack == "short":
        rows = rows[:20]
    elif attack == "constant":
        rows = tuple(replace(r, signal=1.0) for r in rows)
    elif attack == "perfect":
        rows = tuple(replace(r, forward_return=r.signal) for r in rows)
    else:
        rows = tuple(
            replace(
                r,
                label_end=r.label_start + timedelta(days=9),
                label_available_at=r.label_start + timedelta(days=9),
            )
            for r in rows
        )
    frame = evaluate_uncertainty(rows, CONFIG, OPTIONS)[0].dataframe()
    assert frame["reason"][0] == reason
    assert frame["lower"][0] is None and frame["upper"][0] is None


def test_degenerate_replicates_are_not_dropped() -> None:
    rows = tuple(replace(r, signal=0.0 if i else 1.0) for i, r in enumerate(series()))
    frame = evaluate_uncertainty(rows, CONFIG, replace(OPTIONS, block_length=1))[
        0
    ].dataframe()
    assert frame["reason"][0] == "degenerate-replicates"
    assert 0 < frame["valid_replicates"][0] < 200
    assert frame["lower"][0] is None


def test_rank_metric_and_cross_sectional_dates_not_instruments() -> None:
    sample = series(n=48)
    rank = evaluate_uncertainty(sample, CONFIG, replace(OPTIONS, metric="rank_ic"))[
        0
    ].dataframe()
    assert rank["status"][0] == "available"
    # Vary the per-date cross-sectional IC; resampling unit is the date, not asset.
    rows = tuple(
        replace(
            r,
            instrument_id=f"asset-{j}",
            signal=float(j),
            forward_return=float((j + i % 7) % 5),
        )
        for i, r in enumerate(sample)
        for j in range(5)
    )
    config = replace(CONFIG, mode="cross_sectional")
    table, details = evaluate_uncertainty(rows, config, OPTIONS)
    frame = table.dataframe()
    assert table.columns[0] == "model_id" and table.columns[1] == "metric"
    assert frame["time_points"][0] == 48
    assert frame["observations"][0] == 240
    dated = sequence(mapping(sequence(details["groups"])[0])["per_date"])
    assert frame["estimate"][0] == pytest.approx(
        float(np.mean([cast(float, mapping(r)["pearson_ic"]) for r in dated]))
    )
    assert frame["status"][0] == "available"


@pytest.mark.parametrize(
    "changes",
    [
        {"block_length": True},
        {"block_length": 0},
        {"replicates": 199},
        {"seed": -1},
        {"step_seconds": 0},
        {"confidence": 0.5},
        {"confidence": 0.99},
        {"minimum_time_points": 3},
        {"metric": "sharpe"},
    ],
)
def test_invalid_policy(changes: dict[str, object]) -> None:
    with pytest.raises(ContractError):
        BootstrapConfig.parse({**asdict(OPTIONS), **changes})


def test_block_count_and_work_limits() -> None:
    insufficient = evaluate_uncertainty(
        series(), replace(CONFIG, minimum_observations=100), OPTIONS
    )[0].dataframe()
    assert insufficient["reason"][0] == "too-few-time-points"
    frame = evaluate_uncertainty(series(), CONFIG, replace(OPTIONS, block_length=40))[
        0
    ].dataframe()
    assert frame["reason"][0] == "too-few-blocks"
    with pytest.raises(ContractError, match="row-replicates"):
        evaluate_uncertainty(series() * 11, CONFIG, replace(OPTIONS, replicates=2000))


def test_section_plot_export_and_trial_round_trip(tmp_path: Path) -> None:
    signals = csv_bytes(series())
    result = evaluate_section(
        "uncertainty", signals, CONFIG_BYTES, b"p", b"l", uncertainty=OPTIONS
    )
    assert SectionResult(result.content).data == result.data
    panel = result.select()
    assert "not selection-adjusted" in panel.caption
    assert len(panel.figure().axes[0].collections) == 2
    panel.export(tmp_path / "bundle", kind="uncertainty")
    assert verify_bundle(tmp_path / "bundle")["scope"] == "partial"
    with pytest.raises(ContractError, match="together"):
        panel.figure(options=PlotOptions(metrics=("estimate",)))
    with pytest.raises(ContractError, match="plotted metrics"):
        result.select(Selection(columns=("model_id", "estimate"))).export(
            tmp_path / "bad", kind="uncertainty"
        )
    fold = FoldSpec(
        "assessment",
        "2024-01-01T00:00:00Z",
        "2025-01-01T00:00:00Z",
        "2025-05-01T00:00:00Z",
    )
    ledger = TrialLedger(tmp_path / "trials.sqlite")
    retained = ledger.run(
        "attempt",
        "family",
        "uncertainty",
        signals,
        CONFIG_BYTES,
        b"p",
        b"l",
        fold=fold,
        uncertainty=OPTIONS,
    )
    assert retained.data == result.data
    assert ledger.table().dataframe()["status"].to_list() == ["computed"]


def test_policy_and_schema_tampering_and_missing_options() -> None:
    signals = csv_bytes(series())
    with pytest.raises(ContractError, match="bootstrap options"):
        evaluate_section("uncertainty", signals, CONFIG_BYTES, b"p", b"l")
    result = evaluate_section(
        "uncertainty", signals, CONFIG_BYTES, b"p", b"l", uncertainty=OPTIONS
    )
    value = json_object(result.content)
    value.pop("section_id")
    value["schema_version"] = "red-five-section/v1"
    with pytest.raises(ContractError):
        SectionResult(canonical({**value, "section_id": digest(canonical(value))}))


def test_incompatible_metric_overlay_and_unavailable_interval_plot() -> None:
    signals = csv_bytes(series())
    first = evaluate_section(
        "uncertainty", signals, CONFIG_BYTES, b"p", b"l", uncertainty=OPTIONS
    )
    second = evaluate_section(
        "uncertainty",
        signals,
        CONFIG_BYTES,
        b"p",
        b"l",
        uncertainty=replace(OPTIONS, metric="rank_ic"),
    )
    ax = first.select().figure().axes[0]
    with pytest.raises(ContractError, match="compatible overlay"):
        second.select().plot(ax=ax, options=PlotOptions(overlay=True))
    unavailable = evaluate_section(
        "uncertainty",
        csv_bytes(series(n=20)),
        CONFIG_BYTES,
        b"p",
        b"l",
        uncertainty=OPTIONS,
    )
    assert unavailable.status == "unavailable"
    axis = unavailable.select().figure().axes[0]
    assert len(axis.collections) == 1  # point estimate only; no fake interval
    assert any(t.get_text() == "unavailable" for t in axis.texts)


@pytest.mark.parametrize(
    "field,value",
    [
        ("lower", 2.0),
        ("upper", -1.0),
        ("standard_error", -1.0),
        ("metric", "rank_ic"),
        ("lower", None),
    ],
)
def test_invalid_interval_evidence_rejected(field: str, value: object) -> None:
    result = evaluate_section(
        "uncertainty",
        csv_bytes(series()),
        CONFIG_BYTES,
        b"p",
        b"l",
        uncertainty=OPTIONS,
    )
    payload = json_object(result.content)
    payload.pop("section_id")
    table = mapping(payload["table"])
    row = sequence(sequence(table["rows"])[0])
    row[sequence(table["columns"]).index(field)] = value
    with pytest.raises(ContractError):
        SectionResult(canonical({**payload, "section_id": digest(canonical(payload))}))


def test_prespecified_null_simulation_rubric() -> None:
    coverage: dict[str, int] = {"iid": 0, "ar": 0}
    ratios: list[float] = []
    for seed in range(24):
        for name, rho, block in (("iid", 0.0, 1), ("ar", 0.8, 16)):
            rows = series(seed, 256, rho)
            frame = evaluate_uncertainty(
                rows, CONFIG, replace(OPTIONS, block_length=block)
            )[0].dataframe()
            low, high = float(frame["lower"][0]), float(frame["upper"][0])
            coverage[name] += int(low <= 0 <= high)
            if name == "ar":
                iid = evaluate_uncertainty(
                    rows, CONFIG, replace(OPTIONS, block_length=1)
                )[0].dataframe()
                ratios.append(
                    (high - low) / (float(iid["upper"][0]) - float(iid["lower"][0]))
                )
    print(
        {
            "coverage_out_of_24": coverage,
            "median_ar_width_ratio": float(np.median(ratios)),
        }
    )
    assert coverage["iid"] >= 18 and coverage["ar"] >= 18
    assert float(np.median(ratios)) >= 1.25
