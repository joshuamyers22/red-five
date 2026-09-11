from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import cast

import pytest
from matplotlib.patches import Rectangle

from red_five import sections
from red_five.composition import PlotOptions, Selection
from red_five.contracts import ContractError, EvaluationConfig, Prediction
from red_five.evaluation import evaluate
from red_five.quantiles import QuantileConfig, evaluate_quantiles
from red_five.rendering import verify_bundle
from red_five.reporting import canonical, seal_report
from red_five.sections import SectionResult, evaluate_section
from red_five.signal_io import digest, json_object
from red_five.visualization import ReportView, mapping, sequence

ROOT = Path(__file__).resolve().parents[1]
BASE = datetime(2026, 1, 1, tzinfo=UTC)
OPTIONS = QuantileConfig("2026-01-09T00:00:00Z", 4, 8, 1)
_BASE_CONFIG = EvaluationConfig.parse(
    json_object((ROOT / "examples/evaluation.json").read_bytes())
)
CONFIG = replace(_BASE_CONFIG, as_of=BASE + timedelta(days=30))


def row(day: int, score: float, label: float | None = 0.0) -> Prediction:
    start = BASE + timedelta(days=day)
    return Prediction(
        "a",
        "ES",
        "March",
        start,
        start,
        start,
        start + timedelta(days=1),
        start + timedelta(days=1),
        score,
        label,
    )


def sample() -> tuple[Prediction, ...]:
    return tuple(row(i, float(i)) for i in range(8)) + tuple(
        row(8 + i, float(2 * i), (i + 1) / 100) for i in range(4)
    )


def test_hand_worked_bins_means_spread_and_cutoff_equality() -> None:
    table, metadata = evaluate_quantiles(sample(), CONFIG, OPTIONS)
    frame = table.dataframe()
    assert frame["mean_return"].to_list() == pytest.approx([0.01, 0.02, 0.03, 0.04])
    assert frame["spread"].to_list() == pytest.approx([0.03] * 4)
    assert frame["monotonicity"].to_list() == ["nondecreasing"] * 4
    assert frame["observations"].to_list() == [1] * 4
    assert metadata["training_labels_used"] is False
    assert metadata["fit_groups"] == [
        {
            "group": ("a", "ES", "March"),
            "training_observations": 8,
            "cutpoints": [1.0, 3.0, 5.0],
            "training_min": 0.0,
            "training_max": 7.0,
            "reason": None,
        }
    ]


def test_training_fit_independent_of_test_values_and_all_labels() -> None:
    original = sample()
    changed = tuple(
        replace(r, forward_return=1e100, signal=r.signal if i < 8 else 1e100)
        for i, r in enumerate(original)
    )
    assert (
        evaluate_quantiles(original, CONFIG, OPTIONS)[1]
        == evaluate_quantiles(changed, CONFIG, OPTIONS)[1]
    )
    assert evaluate_quantiles(
        tuple(reversed(original)), CONFIG, OPTIONS
    ) == evaluate_quantiles(original, CONFIG, OPTIONS)


def test_ties_boundary_equality_and_out_of_range() -> None:
    training = tuple(row(i, float(i // 4)) for i in range(8))
    test = tuple(
        row(8 + i, score, 0.01) for i, score in enumerate([-1.0, 0.0, 1.0, 2.0])
    )
    table, _ = evaluate_quantiles(training + test, CONFIG, OPTIONS)
    frame = table.dataframe()
    assert frame["effective_bins"].to_list() == [2, 2]
    assert frame["observations"].to_list() == [2, 2]
    assert frame["out_of_range"].to_list() == [1, 1]
    assert frame["monotonicity"].to_list() == ["flat", "flat"]


@pytest.mark.parametrize(
    "reason,training",
    [
        ("insufficient-training", ()),
        ("insufficient-training", tuple(row(i, float(i)) for i in range(4))),
        ("constant-training-scores", tuple(row(i, 1.0) for i in range(8))),
    ],
)
def test_unavailable_fit_never_refits_test(
    reason: str, training: tuple[Prediction, ...]
) -> None:
    frame = evaluate_quantiles(training + sample()[8:], CONFIG, OPTIONS)[0].dataframe()
    assert frame["bin"].to_list() == [0]
    assert frame["effective_bins"].to_list() == [0]
    assert frame["mean_return"].to_list() == [None]
    assert frame["reason"].to_list() == [reason]


def test_sparse_missing_immature_and_empty_bins() -> None:
    rows = sample()[:8] + (
        row(8, 0.0, 0.01),
        row(9, 2.0, None),
        replace(row(10, 4.0, 100.0), label_available_at=BASE + timedelta(days=40)),
        row(11, 6.0, 0.04),
    )
    frame = evaluate_quantiles(rows, CONFIG, OPTIONS)[0].dataframe()
    assert frame["mean_return"].to_list() == [0.01, None, None, 0.04]
    assert frame["immature_labels"].to_list() == [0, 0, 1, 0]
    assert frame["missing_mature_labels"].to_list() == [0, 1, 0, 0]
    assert frame["spread"].to_list() == pytest.approx([0.03] * 4)
    assert frame["monotonicity"].to_list() == [None] * 4
    empty = evaluate_quantiles(sample()[:8], CONFIG, OPTIONS)[0].dataframe()
    assert empty["reason"].to_list() == ["empty-bin"] * 4
    sparse = evaluate_quantiles(sample(), CONFIG, replace(OPTIONS, minimum_bin=2))[
        0
    ].dataframe()
    assert sparse["mean_return"].to_list() == [None] * 4


@pytest.mark.parametrize(
    "labels,expected",
    [
        ([4.0, 3.0, 2.0, 1.0], "nonincreasing"),
        ([1.0, 3.0, 2.0, 4.0], "nonmonotonic"),
        ([1.0, 1.0, 1.0, 1.0], "flat"),
    ],
)
def test_monotonicity(labels: list[float], expected: str) -> None:
    rows = sample()[:8] + tuple(
        replace(r, forward_return=v) for r, v in zip(sample()[8:], labels, strict=True)
    )
    assert (
        evaluate_quantiles(rows, CONFIG, OPTIONS)[0]
        .dataframe()["monotonicity"]
        .to_list()
        == [expected] * 4
    )


def test_large_finite_values_do_not_export_infinity() -> None:
    rows = sample()[:8] + (row(8, 0.0, -1e308), row(9, 6.0, 1e308), row(10, 6.0, 1e308))
    frame = evaluate_quantiles(rows, CONFIG, OPTIONS)[0].dataframe()
    assert frame["mean_return"].to_list() == [-1e308, None, None, 1e308]
    assert frame["spread"].to_list() == [None] * 4
    assert frame["spread_reason"].to_list() == ["numerical-degeneracy"] * 4


def test_models_keep_separate_training_scales() -> None:
    other = tuple(
        replace(r, model_id="b", instrument_id="NQ", signal=r.signal * 1000 + 500)
        for r in sample()
    )
    single = evaluate_quantiles(sample(), CONFIG, OPTIONS)[0]
    combined = evaluate_quantiles(sample() + other, CONFIG, OPTIONS)[0]
    assert combined.rows[:4] == single.rows
    assert combined.dataframe()["mean_return"].to_list() == [0.01, 0.02, 0.03, 0.04] * 2


def test_cross_sectional_groups_evaluation_by_date_and_training_by_model() -> None:
    original = sample()
    rows = original[:8] + tuple(
        replace(r, instrument_id=f"asset-{i}", decision_time=BASE + timedelta(days=8))
        for i, r in enumerate(original[8:])
    )
    table, metadata = evaluate_quantiles(
        rows, replace(CONFIG, mode="cross_sectional"), OPTIONS
    )
    assert table.columns[:2] == ("model_id", "decision_time")
    assert table.dataframe()["mean_return"].to_list() == [0.01, 0.02, 0.03, 0.04]
    assert len(cast(list[object], metadata["fit_groups"])) == 1
    assert (
        evaluate_quantiles(
            original[:8], replace(CONFIG, mode="cross_sectional"), OPTIONS
        )[0].rows
        == ()
    )


@pytest.mark.parametrize(
    "bins,training,minimum",
    [
        (1, 20, 1),
        (11, 20, 1),
        (True, 20, 1),
        (5, 4, 1),
        (5, True, 1),
        (5, 20, 0),
        (5, 20, True),
    ],
)
def test_invalid_policy(bins: int, training: int, minimum: int) -> None:
    with pytest.raises(ContractError):
        QuantileConfig(OPTIONS.training_end, bins, training, minimum)


def test_cutoff_rejected_if_after_asof_or_timezone_missing() -> None:
    with pytest.raises(ContractError, match="exceeds"):
        evaluate_quantiles(
            sample(), CONFIG, replace(OPTIONS, training_end="2027-01-01T00:00:00Z")
        )
    with pytest.raises(ContractError, match="timezone"):
        QuantileConfig("2026-01-09")


def fixture_section() -> SectionResult:
    return evaluate_section(
        "quantiles",
        (ROOT / "examples/quantile-signals.csv").read_bytes(),
        (ROOT / "examples/quantile-evaluation.json").read_bytes(),
        b"plan",
        b"lock",
        quantiles=QuantileConfig("2026-01-21T00:00:00Z"),
    )


def test_unavailable_section_and_plot_do_not_impute_zero() -> None:
    result = evaluate_section(
        "quantiles",
        (ROOT / "examples/signals.csv").read_bytes(),
        (ROOT / "examples/evaluation.json").read_bytes(),
        b"plan",
        b"lock",
        quantiles=QuantileConfig("2026-01-01T00:00:00Z"),
    )
    assert result.status == "unavailable"
    axis = result.select().figure().axes[0]
    assert len(axis.patches) == 0
    assert sum(t.get_text() == "unavailable" for t in axis.texts) == 2


def test_full_report_cannot_fabricate_quantiles() -> None:
    report = evaluate(
        (ROOT / "examples/signals.csv").read_bytes(),
        (ROOT / "examples/evaluation.json").read_bytes(),
        b"plan",
        b"lock",
        code_identity={"version": "test"},
        software={},
    )
    with pytest.raises(ContractError, match="no quantile evidence"):
        ReportView(seal_report(report)).section("quantiles")


def test_single_effective_bin_has_no_spread() -> None:
    rows = tuple(row(i, 0.0 if i == 0 else 1.0) for i in range(8)) + (
        row(8, 1.0, 0.01),
    )
    frame = evaluate_quantiles(rows, CONFIG, OPTIONS)[0].dataframe()
    assert frame["effective_bins"].to_list() == [1]
    assert frame["mean_return"].to_list() == [0.01]
    assert frame["spread"].to_list() == [None]
    assert frame["monotonicity"].to_list() == [None]


def test_different_boundaries_cannot_overlay_on_same_bin_numbers() -> None:
    first = fixture_section().select()
    axis = first.figure().axes[0]
    altered = evaluate_section(
        "quantiles",
        (ROOT / "examples/quantile-signals.csv").read_bytes(),
        (ROOT / "examples/quantile-evaluation.json").read_bytes(),
        b"plan",
        b"lock",
        quantiles=QuantileConfig("2026-01-23T00:00:00Z"),
    ).select()
    assert first.section.section_id != altered.section.section_id
    assert (
        first.table()["upper_bound"].to_list()
        != altered.table()["upper_bound"].to_list()
    )
    with pytest.raises(ContractError, match="compatible overlay"):
        altered.plot(ax=axis, options=PlotOptions(overlay=True))


def test_independent_section_plots_and_verified_export(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("unrelated computation invoked")

    monkeypatch.setattr(sections, "evaluate_groups", fail)
    monkeypatch.setattr(sections, "account_weights", fail)
    result = fixture_section()
    assert result.status == "computed"
    assert SectionResult(result.content).data == result.data
    result.diagnostics.clear()
    assert result.diagnostics["training_labels_used"] is False
    panel = result.select(Selection(model_ids=("ES-model",)))
    figure = panel.figure(options=PlotOptions(colors=("#abcdef",)))
    assert [
        cast(Rectangle, p).get_height() for p in figure.axes[0].patches
    ] == pytest.approx(panel.table()["mean_return"].to_list())
    assert len(panel.figure("quantile_counts").axes[0].patches) == 15
    panel.export(tmp_path / "quantiles", kind="quantiles")
    assert verify_bundle(tmp_path / "quantiles")["scope"] == "partial"
    panel.export(tmp_path / "counts", kind="quantile_counts")
    assert verify_bundle(tmp_path / "counts")["scope"] == "partial"


def test_quantile_options_are_required_only_for_quantile_section() -> None:
    for name, options in (("quantiles", None), ("standalone", OPTIONS)):
        with pytest.raises(ContractError, match="options"):
            evaluate_section(
                cast(sections.SectionName, name),
                b"x",
                b"x",
                b"x",
                b"x",
                quantiles=options,
            )


@pytest.mark.parametrize("metric", ["eligible_observations", "model_id"])
def test_manifest_cannot_claim_incompatible_quantile_plot_metric(
    tmp_path: Path, metric: str
) -> None:
    fixture_section().select().export(tmp_path / "bundle", kind="quantiles")
    path = tmp_path / "bundle/manifest.json"
    manifest = json_object(path.read_bytes())
    record = mapping(sequence(manifest["components"])[0])
    mapping(record["options"])["metrics"] = [metric]
    path.write_bytes(canonical(manifest))
    with pytest.raises(ContractError, match="incompatible"):
        verify_bundle(tmp_path / "bundle")


@pytest.mark.parametrize("change", ["schema", "missing", "types"])
def test_corrupted_quantile_policy_rejected_even_with_new_digest(change: str) -> None:
    value = json_object(fixture_section().content)
    value.pop("section_id")
    if change == "schema":
        value["schema_version"] = "red-five-section/v1"
    else:
        details = mapping(value["diagnostics"])
        policy = mapping(details["policy"])
        if change == "missing":
            policy.pop("bins")
        else:
            policy["bins"] = True
    with pytest.raises(ContractError):
        SectionResult(canonical({**value, "section_id": digest(canonical(value))}))
