import hashlib
import json
import tempfile
import unittest
from pathlib import Path

class ThreeConditionAblationTests(unittest.TestCase):
    def test_matching_controlled_packets_are_ready(self):
        from benchmark.core.comparisons import (
            COMMON_CHECKS,
            check_three_condition_ablation,
            render_three_condition_ablation_markdown,
        )

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            b0, r1, c3 = _write_packets(root)

            report = check_three_condition_ablation(
                b0,
                r1,
                c3,
                provider="synthetic-provider",
                model="synthetic-model-v1",
                input_mode="text-only",
                repetition=1,
            )
            markdown = render_three_condition_ablation_markdown(report)

        self.assertEqual(report["status"], "ready")
        self.assertEqual(tuple(check["id"] for check in report["checks"]), COMMON_CHECKS)
        self.assertEqual(report["failed_checks"], [])
        self.assertEqual(report["shared_run_settings"]["repetition"], 1)
        self.assertIn("B0/R1", markdown)
        self.assertIn("No model calls", markdown)

    def test_student_order_drift_is_not_ready(self):
        from benchmark.core.comparisons import check_three_condition_ablation

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            b0, r1, c3 = _write_packets(root, c3_students=("S002", "S001"))
            report = _check(b0, r1, c3)

        self.assertEqual(report["status"], "not_ready")
        self.assertIn("same_students", report["failed_checks"])

    def test_text_source_drift_is_not_ready(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            b0, r1, c3 = _write_packets(root, r1_text_source_hash="c" * 64)
            report = _check(b0, r1, c3)

        self.assertEqual(report["status"], "not_ready")
        self.assertIn("same_text_source", report["failed_checks"])

    def test_output_schema_drift_is_not_ready(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            b0, r1, c3 = _write_packets(root, c3_schema={"type": "array"})
            report = _check(b0, r1, c3)

        self.assertEqual(report["status"], "not_ready")
        self.assertIn("same_output_schema", report["failed_checks"])

    def test_undeclared_b0_r1_prompt_relationship_is_not_ready(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            b0, r1, c3 = _write_packets(root, r1_prompt="Unexpected prompt drift.")
            report = _check(b0, r1, c3)

        self.assertEqual(report["status"], "not_ready")
        self.assertIn("b0_r1_prompt_and_skill_match", report["failed_checks"])

    def test_undeclared_b0_r1_rubric_relationship_is_not_ready(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            b0, r1, c3 = _write_packets(root, r1_rubric={"version": "v0"})
            report = _check(b0, r1, c3)

        self.assertEqual(report["status"], "not_ready")
        self.assertIn("b0_r1_rubric_differs", report["failed_checks"])

    def test_undeclared_r1_c3_relationship_is_not_ready(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            b0, r1, c3 = _write_packets(root, c3_skill_hash="a" * 64)
            report = _check(b0, r1, c3)

        self.assertEqual(report["status"], "not_ready")
        self.assertIn("r1_c3_prompt_and_skill_differ", report["failed_checks"])

    def test_packet_audit_finding_is_not_ready(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            b0, r1, c3 = _write_packets(root)
            (c3 / "metrics.txt").write_text("synthetic", encoding="utf-8")
            report = _check(b0, r1, c3)

        self.assertEqual(report["status"], "not_ready")
        self.assertIn("packet_audits_pass", report["failed_checks"])

    def test_non_text_input_mode_is_rejected_before_outputs(self):
        from benchmark.core.comparisons import check_three_condition_ablation

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            b0, r1, c3 = _write_packets(root)
            with self.assertRaisesRegex(ValueError, "input_mode"):
                check_three_condition_ablation(
                    b0,
                    r1,
                    c3,
                    provider="synthetic-provider",
                    model="synthetic-model-v1",
                    input_mode="multimodal",
                    repetition=1,
                )

    def test_repetition_less_than_one_is_rejected(self):
        from benchmark.core.comparisons import check_three_condition_ablation

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            b0, r1, c3 = _write_packets(root)
            with self.assertRaisesRegex(ValueError, "repetition"):
                check_three_condition_ablation(
                    b0,
                    r1,
                    c3,
                    provider="synthetic-provider",
                    model="synthetic-model-v1",
                    input_mode="text-only",
                    repetition=0,
                )

def _check(b0: Path, r1: Path, c3: Path) -> dict[str, object]:
    from benchmark.core.comparisons import check_three_condition_ablation

    return check_three_condition_ablation(
        b0,
        r1,
        c3,
        provider="synthetic-provider",
        model="synthetic-model-v1",
        input_mode="text-only",
        repetition=1,
    )


def _write_packets(
    root: Path,
    *,
    r1_prompt: str = "Baseline grading policy.",
    r1_rubric: dict[str, str] | None = None,
    r1_text_source_hash: str = "b" * 64,
    c3_schema: dict[str, str] | None = None,
    c3_students: tuple[str, ...] = ("S001", "S002"),
    c3_skill_hash: str = "b" * 64,
) -> tuple[Path, Path, Path]:
    b0 = _write_packet(
        root / "B0",
        condition="B0",
        prompt="Baseline grading policy.",
        rubric={"version": "v0"},
        skill_hash="a" * 64,
    )
    r1 = _write_packet(
        root / "R1",
        condition="R1",
        prompt=r1_prompt,
        rubric=r1_rubric or {"version": "v1"},
        skill_hash="a" * 64,
        text_source_hash=r1_text_source_hash,
    )
    c3 = _write_packet(
        root / "C3",
        condition="C3",
        prompt="Candidate v3 grading policy.",
        rubric={"version": "v1"},
        skill_hash=c3_skill_hash,
        schema=c3_schema,
        students=c3_students,
    )
    return b0, r1, c3


def _write_packet(
    root: Path,
    *,
    condition: str,
    prompt: str,
    rubric: dict[str, str],
    skill_hash: str,
    text_source_hash: str = "b" * 64,
    schema: dict[str, str] | None = None,
    students: tuple[str, ...] = ("S001", "S002"),
) -> Path:
    root.mkdir(parents=True)
    output_schema = schema or {"type": "object"}
    _write_json(root / "course.json", {"course_id": "synthetic", "assessment_id": "week5"})
    _write_json(root / "output.schema.json", output_schema)
    _write_json(root / "rubric.json", rubric)
    (root / "prompt.txt").write_text(prompt + "\n", encoding="utf-8", newline="\n")
    manifest = {
        "assessment_id": "week5",
        "condition": condition,
        "course_id": "synthetic",
        "metadata": {
            "data_snapshot_hash": "d" * 64,
            "skill_hash": skill_hash,
            "skill_version_id": "baseline" if skill_hash == "a" * 64 else "candidate-v3",
            "split": "development",
            "text_source_hash": text_source_hash,
        },
        "output_schema_hash": _sha256_file(root / "output.schema.json"),
        "prompt_hash": _sha256_file(root / "prompt.txt"),
        "rubric_hash": _sha256_file(root / "rubric.json"),
        "student_ids": list(students),
        "task": "grade",
    }
    _write_json(root / "manifest.json", manifest)
    return root


def _write_json(path: Path, payload: object) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


if __name__ == "__main__":
    unittest.main()
