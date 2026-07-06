import unittest

from benchmark.physics.manifest import assign_split


class ManifestTests(unittest.TestCase):
    def test_split_is_deterministic_and_disjoint(self):
        rows = [
            {
                "student_id": f"S{i:03d}",
                "clarity": ("clear", "medium", "difficult")[i % 3],
                "format": ("pdf", "jpg", "docx")[i % 3],
                "score_band": ("low", "medium", "high")[i % 3],
            }
            for i in range(1, 27)
        ]
        first = assign_split(rows, dev_size=8, seed=20260701)
        second = assign_split(rows, dev_size=8, seed=20260701)
        self.assertEqual(first, second)
        self.assertEqual(sum(row["split"] == "dev" for row in first), 8)
        self.assertEqual(sum(row["split"] == "test" for row in first), 18)


if __name__ == "__main__":
    unittest.main()
