from unittest import TestCase

import polars as pl

from red_five.validation import (
    WalkForwardConfig,
    WalkForwardResult,
    validate_walk_forward,
)


def validation_frame() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "prediction_time": [
                "2026-01-01T15:00:00Z",
                "2026-01-02T15:00:00Z",
                "2026-01-03T15:00:00Z",
                "2026-01-04T15:00:00Z",
                "2026-01-05T15:00:00Z",
                "2026-01-06T15:00:00Z",
                "2026-01-07T15:00:00Z",
                "2026-01-08T15:00:00Z",
                "2026-01-09T15:00:00Z",
                "2026-01-10T15:00:00Z",
            ],
            "feature_available_at": [
                f"2026-01-{day:02d}T14:59:00Z" for day in range(1, 11)
            ],
            "target_available_at": [
                f"2026-01-{day:02d}T15:00:00Z" for day in range(3, 13)
            ],
            "factor": [float(value) for value in range(1, 11)],
            "return": [2.9, 5.2, 6.8, 9.3, 10.9, 13.2, 14.8, 17.3, 18.9, 21.2],
        }
    )


def validate(
    frame: pl.DataFrame,
    config: WalkForwardConfig | None = None,
) -> WalkForwardResult:
    return validate_walk_forward(
        frame,
        response="return",
        predictor="factor",
        prediction_time="prediction_time",
        feature_available_at="feature_available_at",
        target_available_at="target_available_at",
        config=config
        or WalkForwardConfig(initial_test_index=5, test_size=2, step_size=2),
    )


class WalkForwardTests(TestCase):
    def test_expanding_folds_purge_unavailable_training_labels(self) -> None:
        result = validate(validation_frame())

        self.assertEqual(len(result.folds), 3)
        self.assertEqual(result.evaluated_observations, 5)
        self.assertEqual(result.skipped_evaluation_observations, 0)
        self.assertEqual(result.folds[0].training_observations, 3)
        self.assertEqual(result.folds[0].purged_training_candidates, 2)
        self.assertEqual(result.folds[1].training_observations, 5)
        self.assertEqual(result.folds[2].test_observations, 1)
        self.assertEqual(len(result.folds[0].predictions), 2)
        self.assertEqual(result.folds[0].predictions[0].actual, 13.2)
        self.assertGreater(result.metrics.relative_mean_square_skill or 0.0, 0.9)
        self.assertAlmostEqual(
            result.metrics.model_root_mean_square_error,
            0.2577856164262851,
            places=10,
        )
        self.assertAlmostEqual(
            result.metrics.baseline_root_mean_square_error,
            10.580989130277787,
            places=10,
        )
        self.assertAlmostEqual(
            result.metrics.relative_mean_square_skill or 0.0,
            0.9994064397261213,
            places=10,
        )
        self.assertIn(
            "training_labels_available_strictly_before_test_window",
            result.leakage_checks,
        )

    def test_prediction_order_must_be_strict(self) -> None:
        frame = validation_frame().with_columns(
            pl.when(pl.int_range(pl.len()) == 5)
            .then(pl.lit("2026-01-05T15:00:00Z"))
            .otherwise(pl.col("prediction_time"))
            .alias("prediction_time"),
            pl.when(pl.int_range(pl.len()) == 5)
            .then(pl.lit("2026-01-05T14:59:00Z"))
            .otherwise(pl.col("feature_available_at"))
            .alias("feature_available_at"),
        )

        with self.assertRaisesRegex(ValueError, "strictly increasing"):
            validate(frame)

    def test_future_feature_is_rejected(self) -> None:
        frame = validation_frame().with_columns(
            pl.when(pl.int_range(pl.len()) == 0)
            .then(pl.lit("2026-01-01T15:01:00Z"))
            .otherwise(pl.col("feature_available_at"))
            .alias("feature_available_at")
        )

        with self.assertRaisesRegex(ValueError, "feature is unavailable"):
            validate(frame)

    def test_target_must_follow_prediction(self) -> None:
        frame = validation_frame().with_columns(
            pl.when(pl.int_range(pl.len()) == 0)
            .then(pl.lit("2026-01-01T15:00:00Z"))
            .otherwise(pl.col("target_available_at"))
            .alias("target_available_at")
        )

        with self.assertRaisesRegex(ValueError, "target must become available after"):
            validate(frame)

    def test_overlapping_test_windows_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "overlapping"):
            WalkForwardConfig(initial_test_index=5, test_size=3, step_size=2)

    def test_gaps_between_test_windows_are_counted(self) -> None:
        result = validate(
            validation_frame(),
            WalkForwardConfig(initial_test_index=5, test_size=1, step_size=2),
        )

        self.assertEqual(result.evaluated_observations, 3)
        self.assertEqual(result.skipped_evaluation_observations, 2)

    def test_fold_fails_if_too_few_labels_are_available(self) -> None:
        frame = validation_frame().with_columns(
            pl.lit("2026-12-31T15:00:00Z").alias("target_available_at")
        )

        with self.assertRaisesRegex(ValueError, "fewer than three"):
            validate(frame)
