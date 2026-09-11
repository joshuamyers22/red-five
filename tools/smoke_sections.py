"""Exercise section APIs using the interpreter's installed package, not src paths."""

from __future__ import annotations

import argparse
from pathlib import Path

from red_five.component_export import Component, export_components
from red_five.composition import PlotOptions, Selection
from red_five.rendering import verify_bundle
from red_five.sections import evaluate_section


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
    export_components(
        [Component(panel, "correlations", PlotOptions(title="Wheel smoke"))],
        args.output,
    )
    assert verify_bundle(args.output)["scope"] == "partial"
    assert panel.table().height == 1
    print("Installed section API and partial bundle verified")


if __name__ == "__main__":
    main()
