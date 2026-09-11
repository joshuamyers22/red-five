import json
from datetime import UTC, datetime
from unittest import TestCase

from test_validation import validation_frame

from red_five.evidence import AnalysisDeclaration, SoftwareVersions
from red_five.validation import WalkForwardConfig
from red_five.validation_evidence import (
    SCHEMA_VERSION,
    build_time_validation_evidence,
)


class TimeValidationEvidenceTests(TestCase):
    def test_artifact_records_executed_checks_folds_and_baseline(self) -> None:
        declaration = AnalysisDeclaration(
            analysis_id="factor-walk-forward-v1",
            code_revision="0123456789abcdef",
            evaluated_at_utc=datetime(2026, 9, 4, 12, 30, tzinfo=UTC),
            sample_filters="complete synthetic fixture",
            validation_design="expanding ordered windows",
            leakage_controls="availability timestamps and label purging",
        )
        evidence = build_time_validation_evidence(
            validation_frame(),
            declaration=declaration,
            input_path="data/walk-forward-example.csv",
            input_sha256="a" * 64,
            analysis_plan_path="analysis/factor.md",
            analysis_plan_sha256="b" * 64,
            response="return",
            predictor="factor",
            prediction_time="prediction_time",
            feature_available_at="feature_available_at",
            target_available_at="target_available_at",
            config=WalkForwardConfig(initial_test_index=5, test_size=2, step_size=2),
            software=SoftwareVersions(
                python="3.12.0",
                numpy="2.5.2",
                polars="1.44.1",
                statsmodels="0.15.0",
            ),
        )

        first = evidence.to_json_bytes()
        artifact = json.loads(first)

        self.assertEqual(first, evidence.to_json_bytes())
        self.assertEqual(artifact["schema_version"], SCHEMA_VERSION)
        self.assertEqual(artifact["baseline"]["kind"], "training_response_mean")
        self.assertEqual(len(artifact["validation"]["folds"]), 3)
        self.assertEqual(
            artifact["validation"]["folds"][0]["purged_training_candidates"], 2
        )
        self.assertEqual(len(artifact["validation"]["folds"][0]["predictions"]), 2)
        self.assertIn(
            "features_available_by_prediction_time",
            artifact["validation"]["executed_leakage_checks"],
        )
        self.assertGreater(
            artifact["validation"]["aggregate_metrics"]["relative_mean_square_skill"],
            0.9,
        )
