import unittest

from benchmark.physics.metrics import evaluate_scores, paired_student_bootstrap


class MetricsTests(unittest.TestCase):
    def test_exact_agreement_mae_and_bias(self):
        gold = {("S001", "Q1a"): 2.0, ("S002", "Q1a"): 1.0}
        predicted = {("S001", "Q1a"): 2.0, ("S002", "Q1a"): 2.0}
        result = evaluate_scores(gold, predicted)
        self.assertEqual(result["exact_agreement"], 0.5)
        self.assertEqual(result["subquestion_mae"], 0.5)
        self.assertEqual(result["mean_signed_error"], 0.5)

    def test_missing_prediction_is_an_error_not_zero(self):
        gold = {("S001", "Q1a"): 2.0}
        with self.assertRaisesRegex(ValueError, "missing predictions"):
            evaluate_scores(gold, {})

    def test_reports_total_question_macro_and_confidence_metrics(self):
        gold = {
            ("S001", "Q1a"): 2.0,
            ("S001", "Q1b"): 2.0,
            ("S002", "Q1a"): 1.0,
            ("S002", "Q1b"): 2.0,
        }
        predicted = {
            ("S001", "Q1a"): 2.0,
            ("S001", "Q1b"): 2.0,
            ("S002", "Q1a"): 2.0,
            ("S002", "Q1b"): 0.0,
        }
        confidence = {
            ("S001", "Q1a"): "high",
            ("S001", "Q1b"): "high",
            ("S002", "Q1a"): "low",
            ("S002", "Q1b"): "low",
        }

        result = evaluate_scores(gold, predicted, confidence)

        self.assertEqual(result["total_score_mae"], 0.5)
        self.assertEqual(result["within_1_point_rate"], 1.0)
        self.assertEqual(result["severe_error_rate"], 0.0)
        self.assertEqual(result["per_question_accuracy"], {"Q1a": 0.5, "Q1b": 0.5})
        self.assertEqual(result["macro_accuracy"], 0.5)
        self.assertEqual(result["confidence_accuracy"], {"high": 1.0, "low": 0.0})

    def test_paired_bootstrap_is_deterministic_and_positive_for_improvement(self):
        gold = {
            ("S001", "Q1a"): 2.0,
            ("S002", "Q1a"): 1.0,
        }
        baseline = {
            ("S001", "Q1a"): 0.0,
            ("S002", "Q1a"): 0.0,
        }
        candidate = dict(gold)

        first = paired_student_bootstrap(gold, baseline, candidate, samples=500)
        second = paired_student_bootstrap(gold, baseline, candidate, samples=500)

        self.assertEqual(first, second)
        self.assertGreater(first["lower"], 0.0)


if __name__ == "__main__":
    unittest.main()
