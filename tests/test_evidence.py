import hashlib
import json
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from unittest import TestCase

import polars as pl

from red_five.evidence import (
    SCHEMA_VERSION,
    AnalysisDeclaration,
    SoftwareVersions,
    build_regression_evidence,
    load_regression_csv,
    write_evidence,
)


class EvidenceTests(TestCase):
    def setUp(self) -> None:
        self.frame = pl.DataFrame(
            {
                "factor": [1.0, 2.0, 3.0, 4.0, 5.0],
                "return": [2.9, 5.2, 6.8, 9.3, 10.9],
            }
        )
        self.declaration = AnalysisDeclaration(
            analysis_id="factor-return-v1",
            code_revision="0123456789abcdef",
            evaluated_at_utc=datetime(2026, 9, 4, 12, 30, tzinfo=UTC),
            sample_filters="none; complete synthetic fixture",
            validation_design="illustrative in-sample inference only",
            leakage_controls="synthetic fixture; no future-derived features",
        )
        self.software = SoftwareVersions(
            python="3.12.0",
            numpy="2.5.2",
            polars="1.44.1",
            statsmodels="0.15.0",
        )

    def test_evidence_is_complete_and_deterministic(self) -> None:
        evidence = build_regression_evidence(
            self.frame,
            declaration=self.declaration,
            input_path="data/regression-example.csv",
            input_sha256="a" * 64,
            analysis_plan_path="analysis/factor-return.md",
            analysis_plan_sha256="b" * 64,
            response="return",
            predictor="factor",
            software=self.software,
        )

        first = evidence.to_json_bytes()
        second = evidence.to_json_bytes()
        artifact = json.loads(first)

        self.assertEqual(first, second)
        self.assertEqual(artifact["schema_version"], SCHEMA_VERSION)
        self.assertEqual(
            artifact["specification"]["ordered_design_matrix"],
            ["intercept", "factor"],
        )
        self.assertEqual(artifact["analysis"]["analysis_plan"]["sha256"], "b" * 64)
        self.assertEqual(
            artifact["software"],
            {
                "numpy": "2.5.2",
                "polars": "1.44.1",
                "python": "3.12.0",
                "statsmodels": "0.15.0",
            },
        )
        self.assertIn("standard_error", artifact["results"]["coefficients"][0])
        self.assertIn("maximum_cooks_distance", artifact["results"]["diagnostics"])

    def test_write_is_atomic_and_returns_content_hash(self) -> None:
        evidence = build_regression_evidence(
            self.frame,
            declaration=self.declaration,
            input_path="input.csv",
            input_sha256="a" * 64,
            analysis_plan_path="plan.md",
            analysis_plan_sha256="b" * 64,
            response="return",
            predictor="factor",
            software=self.software,
        )
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "nested" / "evidence.json"

            digest = write_evidence(output, evidence)

            self.assertEqual(digest, hashlib.sha256(output.read_bytes()).hexdigest())
            self.assertEqual(list(output.parent.iterdir()), [output])

    def test_csv_loading_preserves_text_and_hashes_exact_bytes(self) -> None:
        content = b"factor,return\n01.0,2.9\n"
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "sample.csv"
            source.write_bytes(content)

            frame, digest = load_regression_csv(source)

            self.assertEqual(frame.dtypes, [pl.String, pl.String])
            self.assertEqual(frame.row(0), ("01.0", "2.9"))
            self.assertEqual(digest, hashlib.sha256(content).hexdigest())

    def test_malformed_provenance_digest_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "lowercase SHA-256"):
            build_regression_evidence(
                self.frame,
                declaration=self.declaration,
                input_path="input.csv",
                input_sha256="NOT-A-DIGEST",
                analysis_plan_path="plan.md",
                analysis_plan_sha256="b" * 64,
                response="return",
                predictor="factor",
                software=self.software,
            )

    def test_blank_review_declarations_fail_closed(self) -> None:
        with self.assertRaisesRegex(ValueError, "cannot be blank"):
            AnalysisDeclaration(
                analysis_id="factor-return-v1",
                code_revision="",
                evaluated_at_utc=datetime(2026, 9, 4, tzinfo=UTC),
                sample_filters="none",
                validation_design="in-sample",
                leakage_controls="synthetic",
            )

    def test_naive_evaluation_time_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "use UTC"):
            AnalysisDeclaration(
                analysis_id="factor-return-v1",
                code_revision="0123456789abcdef",
                evaluated_at_utc=datetime(2026, 9, 4),
                sample_filters="none",
                validation_design="in-sample",
                leakage_controls="synthetic",
            )
