"""Command-line adapter for reproducible regression evidence."""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

from .evidence import (
    AnalysisDeclaration,
    build_regression_evidence,
    load_regression_csv,
    sha256_file,
    write_evidence,
)


def main() -> int:
    parser = argparse.ArgumentParser(prog="red-five-regression")
    parser.add_argument("input", type=Path)
    parser.add_argument("--response", required=True)
    parser.add_argument("--predictor", required=True)
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
    frame, input_digest = load_regression_csv(args.input)
    evidence = build_regression_evidence(
        frame,
        declaration=declaration,
        input_path=str(args.input),
        input_sha256=input_digest,
        analysis_plan_path=str(args.analysis_plan),
        analysis_plan_sha256=sha256_file(args.analysis_plan),
        response=args.response,
        predictor=args.predictor,
        covariance_type=args.covariance_type,
    )
    output_digest = write_evidence(args.output, evidence)
    print(f"evidence={args.output} sha256={output_digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
