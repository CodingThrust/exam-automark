import contextlib
import csv
import io
import json
import tempfile
import unittest
from pathlib import Path

from benchmark.core.cli import main
from benchmark.core.manifests import ExperimentRecord, write_record


FIXTURES = Path(__file__).parents[2] / "fixtures" / "synthetic"


class CoreCliTests(unittest.TestCase):
    @staticmethod
    def _inputs(root: Path) -> Path:
        input_root = root / "inputs"
        student_dir = input_root / "S001"
        student_dir.mkdir(parents=True)
        (student_dir / "page-001.txt").write_text(
            "visible anonymous work\n", encoding="utf-8"
        )
        return input_root

    def test_build_packet_command_writes_prompt_and_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            stdout = io.StringIO()

            with contextlib.redirect_stdout(stdout):
                code = main(
                    [
                        "build-packet",
                        "--course",
                        str(FIXTURES / "course_dsaa3073_hw1.json"),
                        "--packet-id",
                        "T1-dev-r1",
                        "--condition",
                        "T1",
                        "--task",
                        "transcribe",
                        "--prompt",
                        str(FIXTURES / "transcribe_prompt.txt"),
                        "--student-id",
                        "S001",
                        "--input-root",
                        str(self._inputs(root)),
                        "--output-root",
                        str(root / "packets"),
                    ]
                )

            result = json.loads(stdout.getvalue())
            packet = root / "packets" / "T1-dev-r1"
            manifest = json.loads((packet / "manifest.json").read_text(encoding="utf-8"))
            has_prompt = (packet / "prompt.txt").exists()
            has_schema = (packet / "output.schema.json").exists()

        self.assertEqual(code, 0)
        self.assertEqual(result["packet_id"], "T1-dev-r1")
        self.assertEqual(manifest["prompt_hash"], result["manifest"]["prompt_hash"])
        self.assertTrue(has_prompt)
        self.assertTrue(has_schema)

    def test_build_grade_packet_requires_rubric_argument(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            stderr = io.StringIO()

            with contextlib.redirect_stderr(stderr):
                code = main(
                    [
                        "build-packet",
                        "--course",
                        str(FIXTURES / "course_dsaa3073_hw1.json"),
                        "--packet-id",
                        "G2-dev-r1",
                        "--condition",
                        "G2",
                        "--task",
                        "grade",
                        "--prompt",
                        str(FIXTURES / "grade_prompt.txt"),
                        "--student-id",
                        "S001",
                        "--input-root",
                        str(self._inputs(root)),
                        "--output-root",
                        str(root / "packets"),
                    ]
                )

        self.assertNotEqual(code, 0)
        self.assertIn("--rubric is required", stderr.getvalue())

    def test_audit_packet_command_reports_forbidden_terms(self):
        with tempfile.TemporaryDirectory() as tmp:
            packet = Path(tmp) / "packet"
            packet.mkdir()
            (packet / "leak.txt").write_text("primary_scores", encoding="utf-8")
            stdout = io.StringIO()

            with contextlib.redirect_stdout(stdout):
                code = main(["audit-packet", "--packet", str(packet)])

        self.assertEqual(code, 1)
        self.assertIn("primary_scores", stdout.getvalue())

    def test_validate_rubric_command_reports_ready_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            course_path = root / "course.json"
            rubric_path = root / "rubric.json"
            output_path = root / "rubric-readiness.json"
            course_path.write_text(
                json.dumps(
                    {
                        "course_id": "DSAA3071",
                        "assessment_id": "week5",
                        "questions": [{"id": "Q1", "max_score": 5, "score_step": 1}],
                    }
                ),
                encoding="utf-8",
            )
            rubric_path.write_text(
                json.dumps(
                    {
                        "rubric_format": "concept_keyterm_v1",
                        "questions": [
                            {
                                "question_id": "Q1",
                                "max_score": 5,
                                "scoring_elements": [
                                    {
                                        "element_id": "idea",
                                        "levels": {
                                            "mentioned_only": 1,
                                            "partial_understanding": 2,
                                            "demonstrated": 5,
                                        },
                                    }
                                ],
                                "score_bands": {
                                    "full": {"minimum": 5, "maximum": 5},
                                    "substantially_correct": {"minimum": 3, "maximum": 4},
                                    "partially_correct": {"minimum": 2, "maximum": 2},
                                    "minimal_relevant": {"minimum": 1, "maximum": 1},
                                    "no_credit": {"minimum": 0, "maximum": 0},
                                },
                                "material_errors": [{"id": "none", "cap": 5}],
                                "full_credit_rule": "Demonstrate the idea.",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            stdout = io.StringIO()

            with contextlib.redirect_stdout(stdout):
                code = main(
                    [
                        "validate-rubric",
                        "--course",
                        str(course_path),
                        "--rubric",
                        str(rubric_path),
                        "--output",
                        str(output_path),
                    ]
                )
            result = json.loads(stdout.getvalue())
            report = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertEqual(code, 0)
        self.assertEqual(result["status"], "ready")
        self.assertEqual(report["course_id"], "DSAA3071")
        self.assertEqual(report["failed_checks"], [])

    def test_render_note_command_writes_typst_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            record_path = root / "experiment.json"
            note_path = root / "note.typ"
            write_record(
                ExperimentRecord(
                    experiment_id="2026-07-11-synthetic",
                    course_id="dsaa3073",
                    assessment_id="hw1",
                    git_branch="codex/repro-experiment-framework",
                    git_commit="abc1234",
                    data_snapshot_hash="a" * 64,
                    prompt_packet_hashes={"G2": "b" * 64},
                    conditions=("G2",),
                    metrics_path=str(FIXTURES / "metrics_dsaa3073_hw1.json"),
                    note_path=str(note_path),
                    notes=("synthetic fixture only",),
                ),
                record_path,
            )
            stdout = io.StringIO()

            with contextlib.redirect_stdout(stdout):
                code = main(
                    [
                        "render-note",
                        "--record",
                        str(record_path),
                        "--metrics",
                        str(FIXTURES / "metrics_dsaa3073_hw1.json"),
                        "--output",
                        str(note_path),
                        "--title",
                        "Synthetic Report",
                    ]
                )
            result = json.loads(stdout.getvalue())
            text = note_path.read_text(encoding="utf-8")

        self.assertEqual(code, 0)
        self.assertEqual(result["note_path"], str(note_path))
        self.assertIn("Synthetic Report", text)
        self.assertIn("Results At A Glance", text)
        self.assertIn("Condition Details", text)

    def test_inventory_data_command_writes_privacy_preserving_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            course_root = root / "Data" / "linearalgebra"
            submissions = course_root / "submissions"
            submissions.mkdir(parents=True)
            (submissions / "student_real_name_page1.jpg").write_text(
                "visible work",
                encoding="utf-8",
            )
            output = root / "inventory.json"
            stdout = io.StringIO()

            with contextlib.redirect_stdout(stdout):
                code = main(
                    [
                        "inventory-data",
                        "--data-root",
                        str(root / "Data"),
                        "--course",
                        "linearalgebra",
                        "--output",
                        str(output),
                    ]
                )
            result = json.loads(stdout.getvalue())
            inventory_text = output.read_text(encoding="utf-8")

        self.assertEqual(code, 0)
        self.assertEqual(result["course_id"], "linearalgebra")
        self.assertNotIn("student_real_name", inventory_text)
        self.assertIn("snapshot_hash", result)

    def test_snapshot_skill_command_writes_baseline_hashes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            agent = root / "agent.md"
            claude = root / "claude.md"
            agent.write_bytes(b"skill text\n")
            claude.write_bytes(b"skill text\r\n")
            output = root / "snapshot.json"
            stdout = io.StringIO()

            with contextlib.redirect_stdout(stdout):
                code = main(
                    [
                        "snapshot-skill",
                        "--skill-version-id",
                        "skill_baseline_v1",
                        "--source",
                        f"agents={agent}",
                        "--source",
                        f"claude={claude}",
                        "--output",
                        str(output),
                    ]
                )
            result = json.loads(stdout.getvalue())
            snapshot = json.loads(output.read_text(encoding="utf-8"))

        self.assertEqual(code, 0)
        self.assertTrue(result["mirror_synchronized"])
        self.assertEqual(snapshot["skill_version_id"], "skill_baseline_v1")
        self.assertEqual(len(set(snapshot["skill_hashes"].values())), 1)

    def test_plan_experiment_command_writes_planned_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            course_root = root / "Data" / "dsaa3073"
            course_root.mkdir(parents=True)
            (course_root / "exam.pdf").write_bytes(b"exam")
            inventory_path = root / "inventory.json"
            plan_path = root / "plan.json"
            with contextlib.redirect_stdout(io.StringIO()):
                main(
                    [
                        "inventory-data",
                        "--data-root",
                        str(root / "Data"),
                        "--course",
                        "dsaa3073",
                        "--output",
                        str(inventory_path),
                    ]
                )
            stdout = io.StringIO()

            with contextlib.redirect_stdout(stdout):
                code = main(
                    [
                        "plan-experiment",
                        "--experiment-id",
                        "dsaa3073-hw1-planned",
                        "--git-branch",
                        "codex/repro-experiment-framework",
                        "--git-commit",
                        "abc1234",
                        "--inventory",
                        str(inventory_path),
                        "--course-spec",
                        str(FIXTURES / "course_dsaa3073_hw1.json"),
                        "--skill-snapshot",
                        "experiments/skill_versions/skill_baseline_v1.json",
                        "--transcribe-prompt",
                        str(FIXTURES / "transcribe_prompt.txt"),
                        "--grade-prompt",
                        str(FIXTURES / "grade_prompt.txt"),
                        "--note",
                        "synthetic plan only",
                        "--output",
                        str(plan_path),
                    ]
                )
            result = json.loads(stdout.getvalue())
            plan = json.loads(plan_path.read_text(encoding="utf-8"))

        self.assertEqual(code, 0)
        self.assertEqual(result["status"], "planned")
        self.assertEqual(plan["experiment_id"], "dsaa3073-hw1-planned")
        self.assertEqual(plan["skill_version_id"], "skill_baseline_v1")
        self.assertEqual(len(plan["planned_packets"]), 4)
        self.assertIn("grade_standard_v1", plan["prompt_template_hashes"])

    def test_plan_experiment_command_accepts_candidate_template_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            course_root = root / "Data" / "dsaa3073"
            course_root.mkdir(parents=True)
            (course_root / "exam.pdf").write_bytes(b"exam")
            inventory_path = root / "inventory.json"
            plan_path = root / "plan.json"
            with contextlib.redirect_stdout(io.StringIO()):
                main(
                    [
                        "inventory-data",
                        "--data-root",
                        str(root / "Data"),
                        "--course",
                        "dsaa3073",
                        "--output",
                        str(inventory_path),
                    ]
                )
            stdout = io.StringIO()

            with contextlib.redirect_stdout(stdout):
                code = main(
                    [
                        "plan-experiment",
                        "--experiment-id",
                        "dsaa3073-hw1-candidate",
                        "--git-branch",
                        "codex/repro-experiment-framework",
                        "--git-commit",
                        "abc1234",
                        "--inventory",
                        str(inventory_path),
                        "--course-spec",
                        str(FIXTURES / "course_dsaa3073_hw1.json"),
                        "--skill-snapshot",
                        "experiments/skill_versions/skill_candidate_v2.json",
                        "--transcribe-prompt",
                        str(FIXTURES / "transcribe_prompt.txt"),
                        "--grade-prompt",
                        str(FIXTURES / "grade_prompt.txt"),
                        "--grade-template-id",
                        "grade_candidate_v2",
                        "--output",
                        str(plan_path),
                    ]
                )
            plan = json.loads(plan_path.read_text(encoding="utf-8"))

        self.assertEqual(code, 0)
        self.assertEqual(plan["skill_version_id"], "skill_candidate_v2")
        self.assertIn("grade_candidate_v2", plan["prompt_template_hashes"])
        self.assertEqual(
            plan["planned_packets"][2]["prompt_template_id"],
            "grade_candidate_v2",
        )

    def test_record_built_packet_command_updates_plan(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            packet_root = root / "packets"
            with contextlib.redirect_stdout(io.StringIO()):
                main(
                    [
                        "build-packet",
                        "--course",
                        str(FIXTURES / "course_dsaa3073_hw1.json"),
                        "--packet-id",
                        "T1-dev-r1",
                        "--condition",
                        "T1",
                        "--task",
                        "transcribe",
                        "--prompt",
                        str(FIXTURES / "transcribe_prompt.txt"),
                        "--student-id",
                        "S001",
                        "--input-root",
                        str(self._inputs(root)),
                        "--output-root",
                        str(packet_root),
                    ]
                )
            plan_path = root / "plan.json"
            plan_path.write_text(
                json.dumps(
                    {
                        "assessment_id": "hw1",
                        "course_id": "dsaa3073",
                        "course_spec_path": "fixtures/course_dsaa3073_hw1.json",
                        "data_inventory_path": "inventory.json",
                        "data_snapshot_hash": "a" * 64,
                        "experiment_id": "dsaa3073-hw1-planned",
                        "git_branch": "codex/repro-experiment-framework",
                        "git_commit": "abc1234",
                        "notes": ["synthetic only"],
                        "planned_packets": [
                            {
                                "condition": "T1",
                                "packet_id": "T1-dev-r1",
                                "prompt_template_id": "transcribe_standard_v1",
                                "split": "development",
                                "task": "transcribe",
                            }
                        ],
                        "prompt_template_hashes": {
                            "transcribe_standard_v1": "b" * 64
                        },
                        "schema_version": 1,
                        "skill_hashes": {
                            "agents": "c" * 64
                        },
                        "skill_source_paths": {
                            "agents": ".agents/skills/grade-homework/SKILL.md"
                        },
                        "skill_version_id": "skill_baseline_v1",
                        "status": "planned",
                    }
                ),
                encoding="utf-8",
            )
            stdout = io.StringIO()

            with contextlib.redirect_stdout(stdout):
                code = main(
                    [
                        "record-built-packet",
                        "--plan",
                        str(plan_path),
                        "--packet",
                        str(packet_root / "T1-dev-r1"),
                    ]
                )
            result = json.loads(stdout.getvalue())
            plan = json.loads(plan_path.read_text(encoding="utf-8"))

        self.assertEqual(code, 0)
        self.assertEqual(result["audit_status"], "passed")
        self.assertEqual(result["packet_id"], "T1-dev-r1")
        self.assertEqual(plan["status"], "packets_built")
        self.assertEqual(plan["built_packets"][0]["audit_status"], "passed")
        self.assertEqual(plan["built_packets"][0]["packet_hash"], result["packet_hash"])

    def test_validate_gold_command_writes_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            gold_path = root / "primary_scores.csv"
            report_path = root / "gold-readiness.json"
            with gold_path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=("student_id", "question_id", "score"),
                )
                writer.writeheader()
                for question_id, score in (("Q1", "10"), ("Q2a", "3"), ("Q2b", "2")):
                    writer.writerow(
                        {
                            "student_id": "S001",
                            "question_id": question_id,
                            "score": score,
                        }
                    )
            stdout = io.StringIO()

            with contextlib.redirect_stdout(stdout):
                code = main(
                    [
                        "validate-gold",
                        "--course",
                        str(FIXTURES / "course_dsaa3073_hw1.json"),
                        "--gold",
                        str(gold_path),
                        "--student-id",
                        "S001",
                        "--output",
                        str(report_path),
                    ]
                )
            result = json.loads(stdout.getvalue())
            report = json.loads(report_path.read_text(encoding="utf-8"))

        self.assertEqual(code, 0)
        self.assertEqual(result["status"], "ready")
        self.assertEqual(report["filled_score_rows"], 3)

    def test_validate_transcripts_command_writes_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            transcript_root = root / "transcripts"
            transcript_root.mkdir()
            transcript_path = transcript_root / "S001.json"
            report_path = root / "transcript-readiness.json"
            transcript_path.write_text(
                json.dumps(
                    {
                        "student_id": "S001",
                        "answers": [
                            {
                                "question_id": question_id,
                                "text": "visible answer",
                                "unclear": False,
                            }
                            for question_id in ("Q1", "Q2a", "Q2b")
                        ],
                    },
                    indent=2,
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
                newline="\n",
            )
            stdout = io.StringIO()

            with contextlib.redirect_stdout(stdout):
                code = main(
                    [
                        "validate-transcripts",
                        "--course",
                        str(FIXTURES / "course_dsaa3073_hw1.json"),
                        "--transcript-source",
                        str(transcript_root),
                        "--student-id",
                        "S001",
                        "--output",
                        str(report_path),
                    ]
                )
            result = json.loads(stdout.getvalue())
            report = json.loads(report_path.read_text(encoding="utf-8"))

        self.assertEqual(code, 0)
        self.assertEqual(result["status"], "ready")
        self.assertEqual(report["valid_transcript_count"], 1)


if __name__ == "__main__":
    unittest.main()
