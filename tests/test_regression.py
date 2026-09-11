from unittest import TestCase

import polars as pl

from red_five.regression import fit_simple_ols


class RegressionTests(TestCase):
    def test_statsmodels_ols_uses_an_explicit_polars_boundary(self) -> None:
        frame = pl.DataFrame({"factor": [1.0, 2.0, 3.0, 4.0], "return": [3, 5, 7, 9]})

        fitted = fit_simple_ols(frame, response="return", predictor="factor")

        self.assertAlmostEqual(fitted.intercept, 1.0)
        self.assertAlmostEqual(fitted.slope, 2.0)
        self.assertAlmostEqual(fitted.r_squared, 1.0)
        self.assertEqual(fitted.observations, 4)
        self.assertEqual(fitted.covariance_type, "HC3")
        self.assertEqual(
            [item.name for item in fitted.coefficients], ["intercept", "factor"]
        )
        self.assertAlmostEqual(fitted.coefficients[1].standard_error, 0.0, places=12)
        self.assertAlmostEqual(fitted.diagnostics.adjusted_r_squared, 1.0)
        self.assertGreaterEqual(fitted.diagnostics.condition_number, 1.0)

    def test_missing_values_fail_closed(self) -> None:
        frame = pl.DataFrame({"factor": [1.0, None, 3.0], "return": [1, 2, 3]})

        with self.assertRaisesRegex(ValueError, "nulls"):
            fit_simple_ols(frame, response="return", predictor="factor")

    def test_constant_predictor_is_rejected(self) -> None:
        frame = pl.DataFrame({"factor": [1.0, 1.0, 1.0], "return": [1, 2, 3]})

        with self.assertRaisesRegex(ValueError, "must vary"):
            fit_simple_ols(frame, response="return", predictor="factor")

    def test_numerical_regression_fixture_detects_drift(self) -> None:
        frame = pl.DataFrame(
            {
                "factor": [1.0, 2.0, 3.0, 4.0, 5.0],
                "return": [2.9, 5.2, 6.8, 9.3, 10.9],
            }
        )

        fitted = fit_simple_ols(frame, response="return", predictor="factor")

        self.assertAlmostEqual(fitted.intercept, 0.99, places=12)
        self.assertAlmostEqual(fitted.slope, 2.01, places=12)
        self.assertAlmostEqual(fitted.r_squared, 0.9953927269143589, places=12)
        self.assertAlmostEqual(
            fitted.coefficients[0].standard_error, 0.2872823044480409, places=10
        )
        self.assertAlmostEqual(
            fitted.coefficients[1].standard_error, 0.09810448407650973, places=10
        )
        self.assertAlmostEqual(
            fitted.diagnostics.durbin_watson, 3.5315508021390367, places=10
        )
        self.assertAlmostEqual(
            fitted.diagnostics.maximum_cooks_distance,
            0.5895721925133552,
            places=10,
        )
