import json
import tempfile
import unittest
from pathlib import Path

from benchmark.core.inventory import build_data_inventory, write_data_inventory


class DataInventoryTests(unittest.TestCase):
    def test_inventory_omits_raw_submission_filenames(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            course_root = root / "Data" / "linearalgebra"
            submissions = course_root / "submissions"
            submissions.mkdir(parents=True)
            (submissions / "student_name_12345_page1.jpg").write_text(
                "visible work",
                encoding="utf-8",
            )
            (course_root / "quiz.pdf").write_bytes(b"quiz")

            inventory = build_data_inventory(root / "Data", "linearalgebra")
            serialized = json.dumps(inventory, sort_keys=True)

        self.assertEqual(inventory["course_id"], "linearalgebra")
        self.assertEqual(inventory["counts"]["submission_files"], 1)
        self.assertEqual(inventory["extension_counts"][".jpg"], 1)
        self.assertEqual(inventory["extension_counts"][".pdf"], 1)
        self.assertNotIn("student_name_12345", serialized)
        self.assertFalse(inventory["privacy_policy"]["raw_filenames_recorded"])

    def test_write_inventory_is_stable_for_same_tree(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            course_root = root / "Data" / "DSAA3701"
            course_root.mkdir(parents=True)
            (course_root / "exam.pdf").write_bytes(b"exam")
            first = root / "first.json"
            second = root / "second.json"

            inv_a = write_data_inventory(root / "Data", "DSAA3701", first)
            inv_b = write_data_inventory(root / "Data", "DSAA3701", second)
            first_exists = first.exists()
            second_exists = second.exists()

        self.assertEqual(inv_a["snapshot_hash"], inv_b["snapshot_hash"])
        self.assertTrue(first_exists)
        self.assertTrue(second_exists)

    def test_checked_in_inventories_follow_privacy_policy(self):
        inventory_paths = [
            Path("experiments/data_inventory/physics.json"),
            Path("experiments/data_inventory/DSAA3073.json"),
            Path("experiments/data_inventory/DSAA3701.json"),
            Path("experiments/data_inventory/linearalgebra.json"),
        ]

        inventories = [
            json.loads(path.read_text(encoding="utf-8")) for path in inventory_paths
        ]

        self.assertTrue(
            all(
                inventory["privacy_policy"]["raw_filenames_recorded"] is False
                for inventory in inventories
            )
        )
        self.assertTrue(all("snapshot_hash" in inventory for inventory in inventories))
        self.assertTrue(all("extension_counts" in inventory for inventory in inventories))


if __name__ == "__main__":
    unittest.main()
