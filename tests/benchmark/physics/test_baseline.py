import unittest

from benchmark.physics.baseline import row_to_score_records


class BaselineTests(unittest.TestCase):
    def test_imports_twelve_scores_without_recomputing_them(self):
        row = {
            "student": "alice",
            "Q1a": "2",
            "Q1b": "2",
            "Q1c": "3",
            "Q1d": "3",
            "Q2a": "7",
            "Q2b": "3",
            "Q3a": "1.5",
            "Q3b": "1.5",
            "Q3c": "1.5",
            "Q3d": "1.5",
            "Q3e": "2",
            "Q3f": "2",
        }
        records = row_to_score_records(row, "S001")
        self.assertEqual(len(records), 12)
        self.assertEqual(sum(record.score for record in records), 30.0)


if __name__ == "__main__":
    unittest.main()
