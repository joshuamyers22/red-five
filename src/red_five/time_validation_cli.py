"""Command-line adapter for leakage-aware time validation evidence."""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

from .evidence import (
    AnalysisDeclaration,
    load_regression_csv,
    sha256_file,
    write_artifact,
)
from .validation import WalkForwardConfig
from .validation_evidence import build_time_validation_evidence


def main() -> int:
    parser = argparse.ArgumentParser(prog="red-five-validate")
    parser.add_argument("input", type=Path)
    parser.add_argument("--response", required=True)
    parser.add_argument("--predictor", required=True)
    parser.add_argument("--prediction-time", required=True)
    parser.add_argument("--feature-available-at", required=True)
    parser.add_argument("--target-available-at", required=True)
    parser.add_argument("--initial-test-index", required=True, type=int)
    parser.add_argument("--test-size", required=True, type=int)
    parser.add_argument("--step-size", required=True, type=int)
    parser.add_argument("--analysis-id", required=True)
    parser.add_argument("--analysis-plan", required=True, type=Path)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--evaluated-at-utc", required=True)
    parser.add_argument("--sample-filters", required=True)
    parser.add_argument("--validation-design", required=True)
    parser.add_argument("--leakage-controls", required=True)
    parser.add_argument(
        "--covariance-type", choices=("nonrobust", "HC3"), default="HC3"
    )
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    try:
        evaluated_at = datetime.fromisoformat(
            args.evaluated_at_utc.replace("Z", "+00:00")
        )
    except ValueError as error:
        parser.error(f"invalid --evaluated-at-utc: {error}")
    declaration = AnalysisDeclaration(
        analysis_id=args.analysis_id,
        code_revision=args.revision,
        evaluated_at_utc=evaluated_at,
        sample_filters=args.sample_filters,
        validation_design=args.validation_design,
        leakage_controls=args.leakage_controls,
    )
    config = WalkForwardConfig(
        initial_test_index=args.initial_test_index,
        test_size=args.test_size,
        step_size=args.step_size,
    )
    frame, input_digest = load_regression_csv(args.input)
    evidence = build_time_validation_evidence(
        frame,
        declaration=declaration,
        input_path=str(args.input),
        input_sha256=input_digest,
        analysis_plan_path=str(args.analysis_plan),
        analysis_plan_sha256=sha256_file(args.analysis_plan),
        response=args.response,
        predictor=args.predictor,
        prediction_time=args.prediction_time,
        feature_available_at=args.feature_available_at,
        target_available_at=args.target_available_at,
        config=config,
        covariance_type=args.covariance_type,
    )
    output_digest = write_artifact(args.output, evidence)
    print(f"evidence={args.output} sha256={output_digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
