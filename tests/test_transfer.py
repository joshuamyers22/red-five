from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
from typing import cast

import numpy as np
import pytest

from red_five.cli import main
from red_five.contracts import ContractError
from red_five.reporting import canonical, publish, seal_report, verify_report
from red_five.signal_io import digest, json_object
from red_five.transfer import (
    AlignmentInput,
    AlignmentPolicy,
    TransferError,
    calculate_alignment,
)
from red_five.transfer_io import evaluate_alignment

ROOT = Path(__file__).resolve().parents[1]
BASE = AlignmentInput(
    ("a", "b"), ("a", "b"), (1.0, 2.0), (1.0, 0.5), ((1.0, 0.0), (0.0, 4.0))
)


def report(
    forecast: dict[str, object] | None = None,
    covariance: dict[str, object] | None = None,
    config: dict[str, object] | None = None,
    plan: bytes = b"synthetic development plan",
) -> dict[str, object]:
    data: list[bytes] = []
    for name, changes in (
        ("forecast", forecast),
        ("covariance", covariance),
        ("config", config),
    ):
        obj = json_object((ROOT / f"examples/transfer-{name}.json").read_bytes())
        obj.update(changes or {})
        data.append(canonical(obj))
    return evaluate_alignment(
        data[0],
        data[1],
        data[2],
        plan,
        b"locked",
        code_identity={"package_version": "test", "source_sha256": "a" * 64},
        software={"numpy": "test", "python": "test"},
    )


def test_diagonal_sign_scale_and_orthogonal() -> None:
    result = calculate_alignment(BASE)
    assert result.ex_ante_transfer_alignment == pytest.approx(1)
    assert result.optimal_model_sharpe == pytest.approx(np.sqrt(2))
    assert result.portfolio_risk == pytest.approx(np.sqrt(2))
    assert result.expected_return_dot_weight == pytest.approx(2)
    for scale in (1e-100, 3.0, 1e100, -3.0):
        scaled = calculate_alignment(
            replace(
                BASE,
                implemented_weights=tuple(x * scale for x in BASE.implemented_weights),
            )
        )
        assert scaled.ex_ante_transfer_alignment == pytest.approx(np.sign(scale))
    orthogonal = calculate_alignment(replace(BASE, implemented_weights=(2.0, -1.0)))
    assert orthogonal.ex_ante_transfer_alignment == pytest.approx(0, abs=1e-14)


def test_correlated_hand_fixture_and_pearson_counterexample() -> None:
    # Sigma=[[2,1],[1,2]], alpha=[1,0], w=[1,0]: opt=sqrt(2/3), risk=sqrt(2).
    result = calculate_alignment(
        replace(
            BASE,
            expected_excess_returns=(1.0, 0.0),
            implemented_weights=(1.0, 0.0),
            covariance=((2.0, 1.0), (1.0, 2.0)),
        )
    )
    assert result.ex_ante_transfer_alignment == pytest.approx(np.sqrt(3) / 2)
    assert result.model_sharpe == pytest.approx(1 / np.sqrt(2))
    assert result.optimal_model_sharpe == pytest.approx(np.sqrt(2 / 3))
    diagonal = replace(
        BASE,
        expected_excess_returns=(1.0, 2.0),
        implemented_weights=(2.0, 1.0),
        covariance=((1.0, 0.0), (0.0, 1.0)),
    )
    result = calculate_alignment(diagonal, AlignmentPolicy(diagonal_diagnostic=True))
    assert result.ex_ante_transfer_alignment == pytest.approx(0.8)
    assert result.pearson_diagnostic == pytest.approx(-1)
    assert result.cosine_minus_pearson == pytest.approx(1.8)
    assert result.risk_adjusted_alpha_mean == pytest.approx(1.5)
    assert result.risk_weight_mean == pytest.approx(1.5)


def test_random_spd_permutation_identity_and_no_mutation() -> None:
    rng = np.random.default_rng(190)
    for n in (2, 3, 8):
        for _ in range(8):
            m = rng.normal(size=(n, n))
            sigma = m @ m.T + np.eye(n)
            alpha, weights = rng.normal(size=n), rng.normal(size=n)
            ids = tuple(str(x) for x in range(n))
            snapshot = AlignmentInput(
                ids,
                ids,
                tuple(map(float, alpha)),
                tuple(map(float, weights)),
                tuple(tuple(map(float, row)) for row in sigma),
            )
            before = repr(snapshot)
            result = calculate_alignment(snapshot)
            expected = float(
                alpha
                @ weights
                / np.sqrt(alpha @ np.linalg.solve(sigma, alpha))
                / np.sqrt(weights @ sigma @ weights)
            )
            assert result.ex_ante_transfer_alignment == pytest.approx(
                expected, abs=1e-12
            )
            assert repr(snapshot) == before
            permutation = [int(x) for x in rng.permutation(n)]
            pid = tuple(ids[i] for i in permutation)
            permuted = AlignmentInput(
                pid,
                pid,
                tuple(float(alpha[i]) for i in permutation),
                tuple(float(weights[i]) for i in permutation),
                tuple(
                    tuple(float(sigma[i, j]) for j in permutation) for i in permutation
                ),
            )
            assert calculate_alignment(
                permuted
            ).ex_ante_transfer_alignment == pytest.approx(expected)


@pytest.mark.parametrize(
    ("changes", "reason"),
    [
        ({"asset_ids": ("a", "a")}, "ASSET_SET_MISMATCH"),
        ({"covariance_asset_ids": ("b", "a")}, "ASSET_SET_MISMATCH"),
        ({"asset_ids": ()}, "INVALID_DIMENSIONS"),
        ({"implemented_weights": (1.0,)}, "INVALID_DIMENSIONS"),
        ({"covariance": ((1.0,), (0.0, 4.0))}, "INVALID_DIMENSIONS"),
        ({"expected_excess_returns": (float("nan"), 1.0)}, "NONFINITE_INPUT"),
        ({"implemented_weights": (float("inf"), 1.0)}, "NONFINITE_INPUT"),
        ({"implemented_weights": (True, 1.0)}, "NONFINITE_INPUT"),
        ({"covariance": ((1.0, 0.0), (0.0, -1.0))}, "COVARIANCE_NOT_PD"),
        ({"covariance": ((1.0, 1.0), (1.0, 1.0))}, "COVARIANCE_NOT_PD"),
        ({"covariance": ((0.0, 0.0), (0.0, 0.0))}, "COVARIANCE_NOT_PD"),
        ({"covariance": ((1.0, 0.2), (0.1, 1.0))}, "COVARIANCE_ASYMMETRIC"),
        (
            {"covariance": ((1.0, 1e-15), (0.0, 1.0))},
            "COVARIANCE_NOT_EXACTLY_SYMMETRIC",
        ),
        ({"expected_excess_returns": (0.0, 0.0)}, "ZERO_ALPHA_NORM"),
        ({"implemented_weights": (0.0, 0.0)}, "ZERO_PORTFOLIO_RISK"),
    ],
)
def test_reject_bad_core(changes: dict[str, object], reason: str) -> None:
    with pytest.raises(TransferError, match="TRANSFER_" + reason):
        calculate_alignment(replace(BASE, **changes))  # pyright: ignore[reportArgumentType]


def test_conditioning_and_diagnostic_limits() -> None:
    result = calculate_alignment(replace(BASE, covariance=((1.0, 0.0), (0.0, 1e-11))))
    assert result.status == "numerically_unreliable"
    assert result.ex_ante_transfer_alignment is None
    assert (
        calculate_alignment(
            BASE, AlignmentPolicy(diagonal_diagnostic=True)
        ).pearson_diagnostic
        is None
    )
    with pytest.raises(TransferError, match="DIAGNOSTIC_REQUIRES_DIAGONAL"):
        calculate_alignment(
            replace(BASE, covariance=((1.0, 0.5), (0.5, 1.0))),
            AlignmentPolicy(diagonal_diagnostic=True),
        )
    for value in (float("nan"), 0.0, 1e13):
        with pytest.raises(TransferError, match="INVALID_CONFIG"):
            AlignmentPolicy(max_condition_number=value)


@pytest.mark.parametrize(
    ("part", "changes", "reason"),
    [
        ("forecast", {"return_unit": "percent"}, "UNIT_MISMATCH"),
        ("forecast", {"as_of": "2030-01-01T00:00:00Z"}, "AS_OF_MISMATCH"),
        ("forecast", {"as_of": "2026-09-20"}, "INVALID_SCHEMA"),
        ("forecast", {"asset_ids": ["B", "A"]}, "ASSET_SET_MISMATCH"),
        ("covariance", {"risk_model_id": "other"}, "MODEL_OR_HORIZON_MISMATCH"),
        ("covariance", {"horizon": "one-year"}, "MODEL_OR_HORIZON_MISMATCH"),
        ("covariance", {"extra": 0}, "INVALID_SCHEMA"),
        ("covariance", {"matrix": []}, "INVALID_DIMENSIONS"),
        ("config", {"enabled": False}, "DISABLED"),
        ("config", {"enabled": 1}, "DISABLED"),
        ("config", {"diagonal_diagnostic": 1}, "INVALID_CONFIG"),
        ("forecast", {"expected_excess_returns": ["0.1", 0.2]}, "NONFINITE_INPUT"),
    ],
)
def test_adapter_contracts(part: str, changes: dict[str, object], reason: str) -> None:
    with pytest.raises(TransferError, match="TRANSFER_" + reason):
        report(
            forecast=changes if part == "forecast" else None,
            covariance=changes if part == "covariance" else None,
            config=changes if part == "config" else None,
        )


def test_report_provenance_and_failure_evidence() -> None:
    first = report()
    assert first == report()
    assert first["live_eligible"] is False
    assert first["run_id"] != report(plan=b"changed plan")["run_id"]
    assert first["run_id"] != report(config={"analysis_id": "other"})["run_id"]
    assert (
        first["run_id"]
        != report(forecast={"implemented_weights": [0.4, 0.3]})["run_id"]
    )
    assert verify_report(seal_report(first)) == first
    bad = report(covariance={"matrix": [[1.0, 0.0], [0.0, 1e-11]]})
    assert verify_report(seal_report(bad)) == bad
    invalid_reports: list[dict[str, object]] = [
        {"live_eligible": True},
        {"schema_version": "unknown"},
        {"interpretation": []},
        {"run_id": "bad"},
    ]
    for changes in invalid_reports:
        with pytest.raises(ContractError):
            verify_report(seal_report({**first, **changes}))
    changed = json_object(seal_report(first))
    changed["verdict"] = "approved"
    with pytest.raises(ContractError):
        verify_report(canonical(changed))
    result = cast(dict[str, object], first["alignment"])
    for changes in (
        {"ex_ante_transfer_alignment": 2.0},
        {"model_sharpe": 9.0},
        {"portfolio_risk": -1.0},
        {"status": "approved"},
        {"condition_number": 0},
        {"asset_count": 0},
    ):
        with pytest.raises(ContractError):
            verify_report(seal_report({**first, "alignment": {**result, **changes}}))


def test_publication_retry_conflict_race_and_symlink(tmp_path: Path) -> None:
    content = seal_report(report())
    output = tmp_path / "report.json"

    def write(_: int) -> None:
        publish(output, content)

    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(write, range(8)))
    assert output.read_bytes() == content
    with pytest.raises(ContractError, match="different evidence"):
        publish(output, seal_report(report(plan=b"another plan")))
    alias = tmp_path / "alias"
    alias.symlink_to(output)
    with pytest.raises(ContractError, match="symlink"):
        publish(alias, content)
    assert not list(tmp_path.glob("tmp*"))


def test_cli(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    output = tmp_path / "report.json"
    args = [
        "transfer",
        "alignment",
        "--forecast",
        str(ROOT / "examples/transfer-forecast.json"),
        "--covariance",
        str(ROOT / "examples/transfer-covariance.json"),
        "--config",
        str(ROOT / "examples/transfer-config.json"),
        "--analysis-plan",
        str(ROOT / "docs/TRANSFER_COEFFICIENT_ANALYSIS_PLAN.md"),
        "--lock",
        str(ROOT / "uv.lock"),
        "--output",
        str(output),
    ]
    assert main(args) == 0
    assert main(args) == 0
    assert main(["transfer", "verify", str(output)]) == 0
    assert main(["verify", str(output)]) == 0
    before = output.read_bytes()
    assert digest(before)
    missing = tmp_path / "private-input-name.json"
    args[3] = str(missing)
    assert main(args) == 2
    assert str(missing) not in capsys.readouterr().err
    assert output.read_bytes() == before
