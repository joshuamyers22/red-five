"""Exercise section APIs using the interpreter's installed package, not src paths."""

from __future__ import annotations

import argparse
from pathlib import Path

from red_five.component_export import Component, export_components
from red_five.composition import PlotOptions, Selection
from red_five.quantiles import QuantileConfig
from red_five.rendering import verify_bundle
from red_five.sections import evaluate_section
from red_five.temporal import FoldSpec, audit_folds
from red_five.trials import TrialLedger


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("project", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    root = args.project
    result = evaluate_section(
        "standalone",
        (root / "examples/signals.csv").read_bytes(),
        (root / "examples/evaluation.json").read_bytes(),
        (root / "STATISTICAL_ANALYSIS_PLAN.md").read_bytes(),
        (root / "uv.lock").read_bytes(),
    )
    panel = result.select(Selection(model_ids=("ES-model",)))
    quantiles = evaluate_section(
        "quantiles",
        (root / "examples/quantile-signals.csv").read_bytes(),
        (root / "examples/quantile-evaluation.json").read_bytes(),
        (root / "STATISTICAL_ANALYSIS_PLAN.md").read_bytes(),
        (root / "uv.lock").read_bytes(),
        quantiles=QuantileConfig("2026-01-21T00:00:00Z"),
    ).select(Selection(model_ids=("ES-model",)))
    export_components(
        [
            Component(panel, "correlations", PlotOptions(title="Wheel smoke")),
            Component(quantiles, "quantiles"),
            Component(quantiles, "quantile_counts"),
        ],
        args.output,
    )
    assert verify_bundle(args.output)["scope"] == "partial"
    assert panel.table().height == 1
    assert quantiles.table().height == 5
    fold = FoldSpec(
        "wheel", "2026-01-01T00:00:00Z", "2026-01-21T00:00:00Z", "2026-01-26T00:00:00Z"
    )
    signals = (root / "examples/quantile-signals.csv").read_bytes()
    config = (root / "examples/quantile-evaluation.json").read_bytes()
    assert len(audit_folds(signals, config, (fold,)).membership.rows) == 70
    ledger = TrialLedger(args.output.with_name(args.output.name + "-trials.sqlite"))
    result = ledger.run(
        "wheel-trial",
        "synthetic",
        "quantiles",
        signals,
        config,
        (root / "STATISTICAL_ANALYSIS_PLAN.md").read_bytes(),
        (root / "uv.lock").read_bytes(),
        fold=fold,
        quantiles=QuantileConfig(fold.test_start, 5, 15, 1),
    )
    assert result.status == "computed"
    assert ledger.table().dataframe()["status"].to_list() == ["computed"]
    print("Installed section API and partial bundle verified")


if __name__ == "__main__":
    main()
