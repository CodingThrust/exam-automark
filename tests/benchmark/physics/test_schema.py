import unittest

from benchmark.physics.schema import ScoreRecord, validate_score_records


class ScoreSchemaTests(unittest.TestCase):
    def test_accepts_all_twelve_quarter_point_scores(self):
        records = [
            ScoreRecord("S001", "Q1a", 2.0, "high", "correct"),
            ScoreRecord("S001", "Q1b", 2.0, "high", "correct"),
            ScoreRecord("S001", "Q1c", 3.0, "high", "correct"),
            ScoreRecord("S001", "Q1d", 3.0, "high", "correct"),
            ScoreRecord("S001", "Q2a", 7.0, "high", "correct"),
            ScoreRecord("S001", "Q2b", 3.0, "high", "correct"),
            ScoreRecord("S001", "Q3a", 1.5, "high", "correct"),
            ScoreRecord("S001", "Q3b", 1.5, "high", "correct"),
            ScoreRecord("S001", "Q3c", 1.5, "high", "correct"),
            ScoreRecord("S001", "Q3d", 1.5, "high", "correct"),
            ScoreRecord("S001", "Q3e", 2.0, "high", "correct"),
            ScoreRecord("S001", "Q3f", 2.0, "high", "correct"),
        ]

        self.assertEqual(validate_score_records(records), 30.0)

    def test_rejects_out_of_range_score(self):
        with self.assertRaisesRegex(ValueError, "Q3a score"):
            ScoreRecord("S001", "Q3a", 2.0, "high", "invalid")

    def test_rejects_non_quarter_increment(self):
        with self.assertRaisesRegex(ValueError, "quarter-point"):
            ScoreRecord("S001", "Q2a", 6.1, "high", "invalid")


if __name__ == "__main__":
    unittest.main()
