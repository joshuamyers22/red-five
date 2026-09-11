"""Verify that retained template entry points produce inspectable artifacts."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from red_five import analysis_cli, dataset_cli, time_validation_cli
from red_five.signal_io import json_object

ROOT = Path(__file__).resolve().parents[1]


def test_dataset_publish_and_verify_cli(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "red-five-dataset",
            "publish",
            str(ROOT / "data/example.csv"),
            str(tmp_path),
            "--dataset-version",
            "fixture-v1",
            "--source-id",
            "synthetic",
            "--revision",
            "test-revision",
            "--created-at-utc",
            "2026-01-02T00:00:00Z",
        ],
    )
    assert dataset_cli.main() == 0
    monkeypatch.setattr(
        sys, "argv", ["red-five-dataset", "verify", str(tmp_path / "fixture-v1")]
    )
    assert dataset_cli.main() == 0


@pytest.mark.parametrize("temporal", [False, True])
def test_reference_analysis_cli(
    temporal: bool,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output = tmp_path / "evidence.json"
    filename = "walk-forward-example.csv" if temporal else "regression-example.csv"
    argv = [
        "red-five-validate" if temporal else "red-five-regression",
        str(ROOT / "data" / filename),
        "--response",
        "return",
        "--predictor",
        "factor",
        "--analysis-id",
        "synthetic-smoke",
        "--analysis-plan",
        str(ROOT / "STATISTICAL_ANALYSIS_PLAN.md"),
        "--revision",
        "test-revision",
        "--evaluated-at-utc",
        "2026-01-15T00:00:00Z",
        "--sample-filters",
        "synthetic",
        "--validation-design",
        "fixture-only",
        "--leakage-controls",
        "synthetic",
        "--output",
        str(output),
    ]
    if temporal:
        argv.extend(
            [
                "--prediction-time",
                "prediction_time",
                "--feature-available-at",
                "feature_available_at",
                "--target-available-at",
                "target_available_at",
                "--initial-test-index",
                "5",
                "--test-size",
                "2",
                "--step-size",
                "2",
            ]
        )
    monkeypatch.setattr(sys, "argv", argv)
    assert (time_validation_cli.main() if temporal else analysis_cli.main()) == 0
    evidence = json_object(output.read_bytes())
    assert evidence["schema_version"]
    assert b"test-revision" in output.read_bytes()
