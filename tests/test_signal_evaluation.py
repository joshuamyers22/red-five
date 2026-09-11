from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from decimal import Decimal
from pathlib import Path
from typing import cast

import pytest

from red_five import signal_io
from red_five.cli import main
from red_five.contracts import ContractError, EvaluationConfig, decimal, timestamp
from red_five.economics import account_weights
from red_five.evaluation import evaluate
from red_five.reporting import canonical, publish, seal_report, verify_report
from red_five.signal_io import json_object, parse_predictions, parse_weights, read_bytes
from red_five.standalone import correlations, evaluate_groups

ROOT = Path(__file__).resolve().parents[1]
SIGNALS = (ROOT / "examples/signals.csv").read_bytes()
CONFIG = (ROOT / "examples/evaluation.json").read_bytes()
WEIGHTS = (ROOT / "examples/weights.csv").read_bytes()


def config(**changes: object) -> EvaluationConfig:
    return EvaluationConfig.parse({**json_object(CONFIG), **changes})


def report(*, weights: bytes | None = WEIGHTS) -> dict[str, object]:
    return evaluate(
        SIGNALS,
        CONFIG,
        b"development-only plan",
        b"test-lock",
        code_identity={"revision": "test-revision"},
        software={"runtime": "test-runtime"},
        weight_bytes=weights,
    )


def test_modes_do_not_pool_time_series_models() -> None:
    rows = parse_predictions(SIGNALS, config())
    groups = evaluate_groups(rows, config())
    assert len(groups) == 2
    assert [g["eligible_observations"] for g in groups] == [5, 5]
    assert groups[0]["rank_ic"] == pytest.approx(1)
    # A cross-sectional model has one score across several instruments at a time.
    cross = tuple(replace(r, model_id="common-model") for r in rows)
    by_date = evaluate_groups(cross, config(mode="cross_sectional"))
    assert len(by_date) == 5
    assert all(g["reason"] == "too-few-observations" for g in by_date)


def test_one_cross_section_matches_hand_calculation() -> None:
    first = parse_predictions(SIGNALS, config())[0]
    rows = tuple(
        replace(
            first,
            model_id="shared",
            instrument_id=str(i),
            signal=float(i),
            forward_return=float(y),
        )
        for i, y in enumerate([3, 1, 2])
    )
    result = evaluate_groups(rows, config(mode="cross_sectional"))[0]
    assert result["pearson_ic"] == pytest.approx(-0.5)
    assert result["rank_ic"] == pytest.approx(-0.5)


def test_future_labels_do_not_influence_metrics() -> None:
    cfg = config(as_of="2026-01-09T16:00:00Z")
    rows = parse_predictions(SIGNALS, cfg)
    before = evaluate_groups(rows, cfg)
    modified = tuple(
        replace(r, forward_return=999) if r.label_available_at > cfg.as_of else r
        for r in rows
    )
    assert evaluate_groups(modified, cfg) == before
    assert all(g["immature_labels"] == 1 for g in before)


def test_missing_mature_labels_are_counted_not_zero_filled() -> None:
    rows = list(parse_predictions(SIGNALS, config()))
    rows[0] = replace(rows[0], forward_return=None)
    group = evaluate_groups(tuple(rows), config())[0]
    assert group["missing_mature_labels"] == 1
    assert group["eligible_observations"] == 4


@pytest.mark.parametrize(
    "old,new,match",
    [
        (b"13:59:00Z", b"14:01:00Z", "unavailable"),
        (b",-2,-0.02", b",NaN,-0.02", "finite"),
        (b",-2,-0.02", b",-2,inf", "finite"),
        (b",-2,-0.02", b",,-0.02", "finite"),
        (b"signal_available_at", b"arrival_time", "columns"),
        (b"NQ-model", b"ES-model", "one instrument"),
        (b"2026-01-06T15:00:00Z", b"2026-01-05T14:00:00Z", "timing"),
    ],
)
def test_invalid_signal_boundaries(old: bytes, new: bytes, match: str) -> None:
    with pytest.raises(ContractError, match=match):
        parse_predictions(
            SIGNALS.replace(old, new, 1 if old != b"NQ-model" else -1), config()
        )


def test_duplicate_prediction_and_future_decision_rejected() -> None:
    duplicate = SIGNALS + SIGNALS.splitlines()[1] + b"\n"
    with pytest.raises(ContractError, match="duplicate"):
        parse_predictions(duplicate, config())
    with pytest.raises(ContractError, match="cutoff"):
        parse_predictions(SIGNALS, config(as_of="2026-01-05T00:00:00Z"))


@pytest.mark.parametrize(
    "changes",
    [
        {"mode": "pooled"},
        {"return_kind": "unknown"},
        {"minimum_observations": True},
        {"minimum_observations": 2},
        {"as_of": "2026-01-12"},
        {"as_of": "not-a-time"},
        {"calendar": ""},
        {"study_id": " padded "},
        {"unexpected": True},
        {"schema_version": "v2"},
    ],
)
def test_config_contract(changes: dict[str, object]) -> None:
    with pytest.raises(ContractError):
        config(**changes)


def test_timezone_normalization() -> None:
    assert timestamp("2026-01-05T09:00:00-05:00", "t") == timestamp(
        "2026-01-05T14:00:00Z", "t"
    )


def test_ties_negative_correlation_and_extreme_finite_values() -> None:
    tied = correlations([1, 1, 3, 4], [2, 2, 6, 8], 3)
    assert tied.rank_ic == pytest.approx(1)
    inverse = correlations([1e308, 0, -1e308], [-1e308, 0, 1e308], 3)
    assert inverse.pearson_ic == pytest.approx(-1)
    assert correlations([1, 1, 1], [1, 2, 3], 3).reason == "constant-score-or-target"
    with pytest.raises(ContractError):
        correlations([1, 2, 3], [1], 3)
    with pytest.raises(ContractError):
        correlations([1, 2, float("nan")], [1, 2, 3], 3)


def test_costs_reconcile_both_sides_and_borrow() -> None:
    rows = parse_weights(WEIGHTS, config())
    periods = cast(list[dict[str, object]], account_weights(rows)["periods"])
    assert Decimal(str(periods[0]["gross_return"])) == Decimal("0.015")
    assert Decimal(str(periods[0]["trading_cost_return"])) == Decimal("0.0006")
    assert Decimal(str(periods[0]["holding_cost_return"])) == Decimal("0.00002")
    assert Decimal(str(periods[0]["net_return"])) == Decimal("0.01438")
    # Exit costs use supplied drifted weights, despite zero target holdings.
    assert Decimal(str(periods[1]["net_return"])) == Decimal("-0.000603")
    stationary = replace(rows[0], pre_trade_weight=rows[0].target_weight)
    held = cast(list[dict[str, object]], account_weights((stationary,))["periods"])
    assert Decimal(str(held[0]["trading_cost_return"])) == 0
    stressed = tuple(replace(r, trade_cost_bps=r.trade_cost_bps * 2) for r in rows)
    more = cast(list[dict[str, object]], account_weights(stressed)["periods"])
    assert Decimal(str(more[0]["net_return"])) < Decimal(str(periods[0]["net_return"]))


@pytest.mark.parametrize(
    "content,cfg,match",
    [
        (WEIGHTS, config(weighting_policy_id=None), "policy"),
        (WEIGHTS, config(as_of="2026-01-06T15:00:00Z"), "immature"),
        (WEIGHTS.replace(b",6,0\n", b",-6,0\n"), config(), "nonnegative"),
        (WEIGHTS.replace(b"13:59:00Z", b"14:01:00Z"), config(), "availability"),
        (WEIGHTS + WEIGHTS.splitlines()[1] + b"\n", config(), "duplicate"),
    ],
)
def test_weight_boundary(content: bytes, cfg: EvaluationConfig, match: str) -> None:
    with pytest.raises(ContractError, match=match):
        parse_weights(content, cfg)


@pytest.mark.parametrize(
    "value", ["nan", "inf", "1e13", "0.0000000000000000001", "bad"]
)
def test_decimal_contract(value: str) -> None:
    with pytest.raises(ContractError):
        decimal(value, "test")


def test_report_is_descriptive_and_binds_input_versions() -> None:
    first = report()
    assert first["verdict"] is None
    assert first["status"] == "insufficient-evidence"
    assert seal_report(first) == seal_report(report())
    no_weights = report(weights=None)
    assert cast(dict[str, object], no_weights["economics"])["status"] == "unavailable"
    assert first["run_id"] != no_weights["run_id"]
    with pytest.raises(ContractError, match="not represented"):
        report(weights=WEIGHTS.replace(b",ES,", b",OTHER,"))


def test_immutable_publication_and_integrity(tmp_path: Path) -> None:
    path = tmp_path / "report.json"
    content = seal_report(report())

    def write_same(_: int) -> None:
        publish(path, content)

    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(write_same, range(2)))
    assert path.read_bytes() == content
    assert verify_report(content)["verdict"] is None
    with pytest.raises(ContractError, match="different evidence"):
        publish(path, seal_report(report(weights=None)))
    assert path.read_bytes() == content
    with pytest.raises(ContractError, match="digest"):
        verify_report(content.replace(b"insufficient-evidence", b"accept"))
    altered = report()
    altered["run_id"] = "not-a-run"
    with pytest.raises(ContractError, match="identity"):
        verify_report(seal_report(altered))
    link = tmp_path / "link.json"
    link.symlink_to(path)
    with pytest.raises(ContractError, match="symlink"):
        publish(link, content)


def test_json_and_empty_inputs_fail(tmp_path: Path) -> None:
    for content in (b"[]", b"{", b'{"a":1,"a":2}'):
        with pytest.raises(ContractError):
            json_object(content)
    path = tmp_path / "empty"
    path.write_bytes(b"")
    with pytest.raises(ContractError, match="empty"):
        read_bytes(path)
    with pytest.raises(ContractError, match="observations"):
        parse_predictions(SIGNALS.splitlines()[0] + b"\n", config())


def test_resource_limits_and_inconsistent_intervals(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(signal_io, "MAX_BYTES", 10)
    path = tmp_path / "too-large.csv"
    path.write_bytes(b"x" * 11)
    with pytest.raises(ContractError, match="limit"):
        read_bytes(path)
    monkeypatch.setattr(signal_io, "MAX_ROWS", 2)
    with pytest.raises(ContractError, match="row limit"):
        parse_predictions(SIGNALS, config())
    monkeypatch.setattr(signal_io, "MAX_ROWS", 100_000)
    changed = WEIGHTS.replace(b"2026-01-05T15:00:00Z", b"2026-01-05T15:01:00Z", 1)
    with pytest.raises(ContractError, match="share a return interval"):
        parse_weights(changed, config())


def test_cli_end_to_end_and_safe_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    output = tmp_path / "report.json"
    args = [
        "eval",
        str(ROOT / "examples/signals.csv"),
        "--config",
        str(ROOT / "examples/evaluation.json"),
        "--analysis-plan",
        str(ROOT / "STATISTICAL_ANALYSIS_PLAN.md"),
        "--lock",
        str(ROOT / "uv.lock"),
        "--weights",
        str(ROOT / "examples/weights.csv"),
        "--output",
        str(output),
    ]
    assert main(args) == 0
    assert main(["verify", str(output)]) == 0
    capsys.readouterr()
    assert main(["verify", str(tmp_path / "private-secret-filename")]) == 2
    error = json_object(capsys.readouterr().err.encode())
    assert error["error_code"] == "IO_FAILED"
    assert "private-secret-filename" not in json.dumps(error)
    invalid = tmp_path / "invalid.json"
    invalid.write_bytes(canonical({"bad": "schema"}))
    assert main(["verify", str(invalid)]) == 2
    assert (
        json_object(capsys.readouterr().err.encode())["error_code"] == "INPUT_INVALID"
    )
