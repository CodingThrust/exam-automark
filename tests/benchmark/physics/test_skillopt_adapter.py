import csv
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from benchmark.physics.cli import main
from benchmark.physics.skillopt_adapter import build_skillopt_split


class SkillOptAdapterExportTests(unittest.TestCase):
    def test_exports_skillopt_train_val_test_split(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, dev_packet, test_packet = self._fixture(Path(tmp))
            output_dir = root / "skillopt_split"

            manifest = build_skillopt_split(
                root,
                dev_packet,
                test_packet,
                output_dir,
                train_fraction=0.5,
            )

            self.assertEqual(manifest["record_type"], "physics_skillopt_split_export")
            self.assertEqual(manifest["split"]["train_student_ids"], ["S001", "S002"])
            self.assertEqual(manifest["split"]["val_student_ids"], ["S003", "S004"])
            self.assertEqual(manifest["split"]["test_student_ids"], ["S005", "S006"])
            train_items = self._read_items(output_dir / "train" / "items.json")
            val_items = self._read_items(output_dir / "val" / "items.json")
            test_items = self._read_items(output_dir / "test" / "items.json")
            self.assertEqual(len(train_items), 2)
            self.assertEqual(len(val_items), 2)
            self.assertEqual(len(test_items), 2)
            self.assertEqual(train_items[0]["id"], "G1-dev-r1-S001")
            self.assertEqual(train_items[0]["gold_total"], 3.0)
            self.assertEqual(train_items[0]["prompt_packet"]["packet_id"], "G1-dev-r1")
            self.assertEqual(
                train_items[0]["transcript"]["answers"][0]["text"],
                "synthetic visible work S001 Q1",
            )
            self.assertTrue((output_dir / "manifest.json").exists())

    def test_cli_exports_skillopt_split(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, dev_packet, test_packet = self._fixture(Path(tmp))
            output_dir = root / "skillopt_split"

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                code = main(
                    [
                        "skillopt-export",
                        "--root",
                        str(root),
                        "--dev-packet",
                        str(dev_packet),
                        "--test-packet",
                        str(test_packet),
                        "--output-dir",
                        str(output_dir),
                    ]
                )

            self.assertEqual(code, 0)
            result = json.loads(stdout.getvalue())
            self.assertEqual(result["record_type"], "physics_skillopt_split_export")
            self.assertTrue((output_dir / "val" / "items.json").exists())

    def _fixture(self, root_parent: Path) -> tuple[Path, Path, Path]:
        root = root_parent / "benchmark"
        (root / "gold").mkdir(parents=True)
        self._write_gold(root / "gold" / "primary_scores.csv")
        dev_packet = root / "packets" / "G1-dev-r1"
        test_packet = root / "packets" / "G1-test-r1"
        self._write_packet(dev_packet, "G1-dev-r1", ("S001", "S002", "S003", "S004"))
        self._write_packet(test_packet, "G1-test-r1", ("S005", "S006"))
        return root, dev_packet, test_packet

    def _write_gold(self, path: Path) -> None:
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=("student_id", "question_id", "score"),
            )
            writer.writeheader()
            for student_id in ("S001", "S002", "S003", "S004", "S005", "S006"):
                writer.writerow(
                    {"student_id": student_id, "question_id": "Q1", "score": 1.0}
                )
                writer.writerow(
                    {"student_id": student_id, "question_id": "Q2", "score": 2.0}
                )

    def _write_packet(
        self,
        packet: Path,
        packet_id: str,
        student_ids: tuple[str, ...],
    ) -> None:
        packet.mkdir(parents=True)
        (packet / "inputs").mkdir()
        self._write_json(packet / "course.json", self._course())
        self._write_json(packet / "rubric.json", {"rubric_version": "synthetic_v1"})
        self._write_json(
            packet / "output.schema.json",
            {"type": "object", "required": ["student_id", "scores", "total"]},
        )
        (packet / "prompt.txt").write_text("Grade with the rubric.", encoding="utf-8")
        self._write_json(
            packet / "manifest.json",
            {
                "condition": "G1",
                "input_hashes": {student_id: f"hash-{student_id}" for student_id in student_ids},
                "metadata": {
                    "input_mode": "text-only",
                    "prompt_template_id": "grade_standard_v1",
                    "skill_version_id": "skill_baseline_v1",
                    "source_run_id": "T1-dev-r1",
                },
                "output_schema_hash": "schema-hash",
                "packet_id": packet_id,
                "prompt_hash": "prompt-hash",
                "rubric_hash": "rubric-hash",
                "student_ids": list(student_ids),
                "task": "grade",
            },
        )
        for student_id in student_ids:
            student_dir = packet / "inputs" / student_id
            student_dir.mkdir()
            self._write_json(
                student_dir / "transcript.json",
                {
                    "student_id": student_id,
                    "answers": [
                        {
                            "question_id": "Q1",
                            "text": f"synthetic visible work {student_id} Q1",
                            "unclear": False,
                        },
                        {
                            "question_id": "Q2",
                            "text": f"synthetic visible work {student_id} Q2",
                            "unclear": False,
                        },
                    ],
                },
            )

    def _course(self) -> dict[str, object]:
        return {
            "anonymous_id_pattern": "^S[0-9]{3}$",
            "assessment_id": "week9",
            "course_id": "physics",
            "input_modes": ["transcript", "text"],
            "questions": [
                {"id": "Q1", "max_score": 1.0, "score_step": 0.25},
                {"id": "Q2", "max_score": 2.0, "score_step": 0.25},
            ],
            "score_unit": "points",
        }

    def _read_items(self, path: Path) -> list[dict[str, object]]:
        return json.loads(path.read_text(encoding="utf-8"))

    def _write_json(self, path: Path, payload: object) -> None:
        path.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )


if __name__ == "__main__":
    unittest.main()
