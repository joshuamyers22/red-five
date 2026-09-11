from __future__ import annotations

import csv
import io
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
from typing import cast

import pytest

from red_five import trials
from red_five.component_export import Component, export_components
from red_five.contracts import ContractError
from red_five.quantiles import QuantileConfig
from red_five.rendering import verify_bundle
from red_five.reporting import canonical
from red_five.sections import SectionResult
from red_five.signal_io import json_object
from red_five.temporal import FoldSpec, audit_folds, evaluate_fold_section
from red_five.trials import TrialLedger
from red_five.visualization import mapping, sequence

ROOT = Path(__file__).resolve().parents[1]
SIGNALS = (ROOT / "examples/quantile-signals.csv").read_bytes()
CONFIG = (ROOT / "examples/quantile-evaluation.json").read_bytes()
FOLD = FoldSpec(
    "first", "2026-01-01T00:00:00Z", "2026-01-21T00:00:00Z", "2026-01-26T00:00:00Z"
)
SECOND = FoldSpec("second", FOLD.train_start, FOLD.test_end, "2026-01-31T00:00:00Z")
QUANTILES = QuantileConfig(FOLD.test_start, 5, 15, 1)


def modify(day: str, **updates: str) -> bytes:
    reader = csv.DictReader(io.StringIO(SIGNALS.decode()))
    assert reader.fieldnames is not None
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=reader.fieldnames, lineterminator="\n")
    writer.writeheader()
    for row in reader:
        if row["decision_time"].startswith(day):
            row.update(updates)
        writer.writerow(row)
    return output.getvalue().encode()


def run(
    ledger: TrialLedger, trial_id: str = "one", signals: bytes = SIGNALS
) -> SectionResult:
    return ledger.run(
        trial_id,
        "synthetic-family",
        "quantiles",
        signals,
        CONFIG,
        b"plan",
        b"lock",
        fold=FOLD,
        quantiles=QUANTILES,
    )


def test_partition_counts_boundaries_and_every_row_accounted_for() -> None:
    audit = audit_folds(SIGNALS, CONFIG, (FOLD, SECOND))
    frame = audit.summary.dataframe()
    assert frame["training"].to_list() == [19, 19, 24, 24]
    assert frame["unavailable_training_label"].to_list() == [1] * 4
    assert frame["test"].to_list() == [5] * 4
    assert len(audit.membership.rows) == 140
    membership = audit.membership.dataframe()
    assert membership.filter(
        (membership["fold_id"] == "first")
        & (membership["decision_time"] == "2026-01-21T00:00:00+00:00")
    )["role"].to_list() == ["test", "test"]
    assert (
        frame.select(
            "training",
            "gap",
            "unavailable_training_label",
            "missing_training_label",
            "test",
            "outside_window",
        )
        .sum_horizontal()
        .to_list()
        == [35] * 4
    )


def test_gap_and_missing_training_labels_have_disjoint_reasons() -> None:
    fold = replace(FOLD, gap_seconds=2 * 86400)
    signals = modify("2026-01-05", forward_return="")
    frame = audit_folds(signals, CONFIG, (fold,)).summary.dataframe()
    assert frame["training"].to_list() == [16, 16]
    assert frame["gap"].to_list() == [2, 2]
    assert frame["unavailable_training_label"].to_list() == [1, 1]
    assert frame["missing_training_label"].to_list() == [1, 1]


@pytest.mark.parametrize(
    "kwargs",
    [
        {"fold_id": ""},
        {"train_start": FOLD.test_start},
        {"test_end": FOLD.test_start},
        {"gap_seconds": -1},
        {"gap_seconds": True},
        {"gap_seconds": 20 * 86400},
        {"test_start": "2026-01-21"},
    ],
)
def test_bad_fold_specs(kwargs: dict[str, object]) -> None:
    with pytest.raises(ContractError):
        replace(FOLD, **kwargs)


@pytest.mark.parametrize(
    "folds",
    [
        (),
        (FOLD, FOLD),
        (SECOND, FOLD),
        (FOLD, replace(SECOND, test_start=FOLD.test_start)),
        (replace(FOLD, test_end="2027-01-01T00:00:00Z"),),
    ],
)
def test_bad_fold_sets(folds: tuple[FoldSpec, ...]) -> None:
    with pytest.raises(ContractError):
        audit_folds(SIGNALS, CONFIG, folds)


def test_quantile_fits_ignore_later_scores_and_purged_labels() -> None:
    original = evaluate_fold_section(
        "quantiles", SIGNALS, CONFIG, b"p", b"l", fold=FOLD, quantiles=QUANTILES
    )
    future = evaluate_fold_section(
        "quantiles",
        modify("2026-01-22", signal="1e50", forward_return="1e50"),
        CONFIG,
        b"p",
        b"l",
        fold=FOLD,
        quantiles=QUANTILES,
    )
    assert original.diagnostics["fit_groups"] == future.diagnostics["fit_groups"]
    purged = evaluate_fold_section(
        "quantiles",
        modify("2026-01-20", signal="1e50", forward_return="1e50"),
        CONFIG,
        b"p",
        b"l",
        fold=FOLD,
        quantiles=QUANTILES,
    )
    assert original.data == purged.data
    assert original.diagnostics["fit_groups"] == purged.diagnostics["fit_groups"]
    assert original.diagnostics["upstream_out_of_sample"] == "unverified"
    assert len(sequence(original.diagnostics["test_keys"])) == 10


def test_test_labels_use_report_maturity_and_fold_metrics_use_test_only() -> None:
    signals = modify(
        "2026-01-22", label_available_at="2026-03-01T00:00:00Z", forward_return="999"
    )
    section = evaluate_fold_section(
        "standalone", signals, CONFIG, b"p", b"l", fold=FOLD
    )
    frame = section.data.dataframe()
    assert frame["observations"].to_list() == [5, 5]
    assert frame["eligible_observations"].to_list() == [4, 4]
    assert frame["immature_labels"].to_list() == [1, 1]
    assert frame["rank_ic"].to_list() == pytest.approx([1.0, -1.0])


def test_cross_sectional_date_groups_and_empty_windows() -> None:
    config = json_object(CONFIG)
    config["mode"] = "cross_sectional"
    audit = audit_folds(SIGNALS, canonical(config), (FOLD,))
    assert "instrument_id" not in audit.summary.columns
    coverage = evaluate_fold_section(
        "coverage", SIGNALS, canonical(config), b"p", b"l", fold=FOLD
    )
    assert len(coverage.data.rows) == 10
    empty = replace(
        FOLD, test_start="2026-02-06T00:00:00Z", test_end="2026-02-07T00:00:00Z"
    )
    assert (
        evaluate_fold_section(
            "standalone", SIGNALS, CONFIG, b"p", b"l", fold=empty
        ).status
        == "unavailable"
    )


def test_fold_options_and_inputs_fail_closed() -> None:
    for content in (b"", b"x" * (16 * 1024 * 1024 + 1)):
        with pytest.raises(ContractError):
            audit_folds(content, CONFIG, (FOLD,))
    for name, options in (
        ("standalone", QUANTILES),
        ("quantiles", None),
        ("quantiles", replace(QUANTILES, training_end=SECOND.test_start)),
    ):
        with pytest.raises(ContractError):
            evaluate_fold_section(
                cast(trials.FoldSection, name),
                SIGNALS,
                CONFIG,
                b"p",
                b"l",
                fold=FOLD,
                quantiles=options,
            )


def test_registration_precedes_computation_and_result_is_retained(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ledger = TrialLedger(tmp_path / "trials.sqlite")
    assert ledger.events() == () and not ledger.path.exists()
    original = trials.evaluate_fold_section

    def checked(*args: object, **kwargs: object) -> SectionResult:
        assert ledger.events()[0]["kind"] == "registered"
        return original(
            "quantiles",
            SIGNALS,
            CONFIG,
            b"plan",
            b"lock",
            fold=FOLD,
            quantiles=QUANTILES,
        )

    monkeypatch.setattr(trials, "evaluate_fold_section", checked)
    result = run(ledger)
    events = ledger.events()
    assert [e["kind"] for e in events] == ["registered", "computed"]
    saved = mapping(mapping(events[-1]["payload"])["section"])
    assert SectionResult(canonical(saved)).content == result.content
    events[0].clear()
    assert ledger.events()[0]["kind"] == "registered"
    assert ledger.table().dataframe()["historical_search_completeness"].to_list() == [
        "unknown"
    ]
    with pytest.raises(ContractError, match="already registered"):
        run(ledger)
    assert len(ledger.events()) == 2


def test_failure_and_unavailable_trials_are_retained(tmp_path: Path) -> None:
    ledger = TrialLedger(tmp_path / "trials.sqlite")
    with pytest.raises(ContractError):
        run(ledger, signals=b"private sensitive error text")
    payload = mapping(ledger.events()[-1]["payload"])
    assert payload == {"error_type": "ContractError"}
    assert "private sensitive" not in str(ledger.events())
    ledger.run(
        "two",
        "family",
        "quantiles",
        SIGNALS,
        CONFIG,
        b"p",
        b"l",
        fold=FOLD,
        quantiles=replace(QUANTILES, minimum_training=100),
    )
    assert ledger.table().dataframe()["status"].to_list() == ["failed", "unavailable"]


def test_interrupt_keeps_unfinished_registration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ledger = TrialLedger(tmp_path / "trials.sqlite")

    def interrupt(*args: object, **kwargs: object) -> SectionResult:
        raise KeyboardInterrupt

    monkeypatch.setattr(trials, "evaluate_fold_section", interrupt)
    with pytest.raises(KeyboardInterrupt):
        run(ledger)
    assert ledger.table().dataframe()["status"].to_list() == ["registered"]
    with pytest.raises(ContractError, match="already registered"):
        run(ledger)


def test_unrelated_result_cannot_complete_registered_request(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ledger = TrialLedger(tmp_path / "trials.sqlite")
    wrong = evaluate_fold_section("coverage", SIGNALS, CONFIG, b"p", b"l", fold=SECOND)

    def unrelated(*args: object, **kwargs: object) -> SectionResult:
        return wrong

    monkeypatch.setattr(trials, "evaluate_fold_section", unrelated)
    with pytest.raises(ContractError, match="registered request"):
        run(ledger)
    assert [e["kind"] for e in ledger.events()] == ["registered"]


def test_concurrent_duplicate_trial_has_one_registration(tmp_path: Path) -> None:
    ledger = TrialLedger(tmp_path / "trials.sqlite")

    def attempt(_: int) -> str:
        try:
            run(ledger)
            return "ok"
        except ContractError:
            return "duplicate"

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(attempt, range(2))) == ["duplicate", "ok"]
    assert len(ledger.events()) == 2


def test_event_capacity_rejects_new_trial_without_changing_history(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(trials, "MAX_EVENTS", 2)
    ledger = TrialLedger(tmp_path / "trials.sqlite")
    run(ledger)
    before = ledger.events()
    with pytest.raises(ContractError, match="capacity"):
        run(ledger, "new")
    assert ledger.events() == before


def test_completion_size_failure_does_not_return_unlogged_result(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(trials, "MAX_BYTES", 4000)
    ledger = TrialLedger(tmp_path / "trials.sqlite")
    with pytest.raises(ContractError, match="exceeds"):
        run(ledger)
    assert ledger.table().dataframe()["status"].to_list() == ["registered"]


@pytest.mark.parametrize("attack", ["edit", "delete-first", "oversize", "version"])
def test_journal_corruption_rejected(tmp_path: Path, attack: str) -> None:
    ledger = TrialLedger(tmp_path / "trials.sqlite")
    run(ledger)
    with sqlite3.connect(ledger.path) as conn:
        if attack == "edit":
            conn.execute("UPDATE events SET event_sha256='bad' WHERE sequence=1")
        elif attack == "delete-first":
            conn.execute("DELETE FROM events WHERE sequence=1")
        elif attack == "oversize":
            conn.execute(
                "UPDATE events SET content=zeroblob(?) WHERE sequence=1",
                (16 * 1024 * 1024 + 1,),
            )
        else:
            conn.execute("PRAGMA user_version=99")
    with pytest.raises(ContractError):
        ledger.events()


def test_symlinks_rejected_and_fold_components_export(tmp_path: Path) -> None:
    ledger = TrialLedger(tmp_path / "trials.sqlite")
    result = run(ledger)
    assert "fold first; test" in result.select().caption
    assert "upstream OOS unverified" in result.select().caption
    link = tmp_path / "linked.sqlite"
    link.symlink_to(ledger.path)
    with pytest.raises(ContractError, match="symlinks"):
        TrialLedger(link).events()
    export_components([Component(result.select(), "quantiles")], tmp_path / "bundle")
    assert verify_bundle(tmp_path / "bundle")["scope"] == "partial"
