import csv
import tempfile
import unittest
from pathlib import Path

from benchmark.physics.gold import create_score_template, validate_adjudication


class GoldTests(unittest.TestCase):
    def test_template_has_312_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "scores.csv"
            create_score_template([f"S{i:03d}" for i in range(1, 27)], output)
            with output.open(newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), 312)

    def test_disagreement_requires_adjudicated_score_and_reason(self):
        row = {
            "primary_score": "1.5",
            "reviewer_score": "1.0",
            "adjudicated_score": "",
            "reason": "",
        }
        with self.assertRaisesRegex(ValueError, "adjudication"):
            validate_adjudication(row)


if __name__ == "__main__":
    unittest.main()
