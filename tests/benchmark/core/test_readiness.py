import contextlib
import hashlib
import io
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from benchmark.core.cli import main
from benchmark.core.packets import PromptPacketSpec, build_prompt_packet, directory_digest
from benchmark.core.plans import (
    BuiltPacket,
    ExperimentPlan,
    PlannedPacket,
    write_experiment_plan,
)
from benchmark.core.readiness import (
    build_run_readiness_report,
    render_readiness_markdown,
)
from benchmark.core.schema import CourseSpec


FIXTURES = Path(__file__).parents[2] / "fixtures" / "synthetic"


class RunReadinessTests(unittest.TestCase):
    def test_matching_candidate_and_baseline_are_ready_without_git(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            baseline_path, candidate_path = _write_readiness_fixture(root)

            report = build_run_readiness_report(
                baseline_plan_path=baseline_path,
                candidate_plan_path=candidate_path,
                repo_root=root,
            )
            markdown = render_readiness_markdown(report)

        self.assertEqual(report["status"], "ready")
        self.assertEqual(report["readiness_level"], "packet")
        self.assertEqual(report["model_run_status"], "not_started")
        self.assertIsNone(report["anchors"]["current_git_branch"])
        self.assertIsNone(report["anchors"]["current_git_commit"])
        self.assertEqual(_status(report, "git_worktree_clean"), "warning")
        self.assertEqual(_status(report, "current_git_branch_matches_plan"), "warning")
        self.assertEqual(_status(report, "planned_git_commit_exists"), "warning")
        self.assertEqual(_status(report, "grade_prompt_differs"), "passed")
        self.assertEqual(_status(report, "same_students_and_inputs_per_packet"), "passed")
        self.assertIn("# dsaa3073 hw1 Run Readiness", markdown)
        self.assertIn("Packet-level ready", markdown)
        self.assertIn("not model-run ready", markdown)
        self.assertNotIn("Physics Week 9", markdown)

    def test_same_grade_prompt_blocks_readiness(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            baseline_path, candidate_path = _write_readiness_fixture(
                root,
                candidate_grade_prompt="Baseline grading policy.",
            )

            report = build_run_readiness_report(
                baseline_plan_path=baseline_path,
                candidate_plan_path=candidate_path,
                repo_root=root,
            )

        self.assertEqual(report["status"], "not_ready")
        self.assertEqual(_status(report, "grade_prompt_differs"), "failed")

    def test_changed_rubric_hash_blocks_readiness(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            baseline_path, candidate_path = _write_readiness_fixture(
                root,
                candidate_rubric={
                    "questions": [
                        {
                            "id": "Q1",
                            "max_score": 10,
                            "criteria": "Different rubric text must fail the gate.",
                        }
                    ]
                },
            )

            report = build_run_readiness_report(
                baseline_plan_path=baseline_path,
                candidate_plan_path=candidate_path,
                repo_root=root,
            )

        self.assertEqual(report["status"], "not_ready")
        self.assertEqual(_status(report, "same_rubric_for_grade_packets"), "failed")

    def test_manifest_metadata_mismatch_blocks_readiness(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            baseline_path, candidate_path = _write_readiness_fixture(root)
            candidate = ExperimentPlan.from_json_path(candidate_path)
            manifest_path = root / candidate.built_packets[0].manifest_path
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["metadata"]["split"] = "heldout"
            manifest_path.write_text(
                json.dumps(manifest, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
                newline="\n",
            )

            report = build_run_readiness_report(
                baseline_plan_path=baseline_path,
                candidate_plan_path=candidate_path,
                repo_root=root,
            )

        self.assertEqual(report["status"], "not_ready")
        self.assertEqual(_status(report, "manifest_metadata_matches_plan"), "failed")

    def test_missing_planned_git_commit_blocks_readiness(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            baseline_path, candidate_path = _write_readiness_fixture(root)
            _init_clean_git_repo(root)

            report = build_run_readiness_report(
                baseline_plan_path=baseline_path,
                candidate_plan_path=candidate_path,
                repo_root=root,
            )

        self.assertEqual(report["status"], "not_ready")
        self.assertEqual(_status(report, "git_worktree_clean"), "passed")
        self.assertEqual(_status(report, "current_git_branch_matches_plan"), "passed")
        self.assertEqual(_status(report, "planned_git_commit_exists"), "failed")
        self.assertEqual(
            _status(report, "current_git_head_contains_plan_commit"),
            "failed",
        )

    def test_check_run_readiness_cli_writes_reports(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            baseline_path, candidate_path = _write_readiness_fixture(root)
            output = root / "records" / "readiness.json"
            markdown_output = root / "records" / "readiness.md"
            stdout = io.StringIO()

            with contextlib.redirect_stdout(stdout):
                code = main(
                    [
                        "check-run-readiness",
                        "--baseline-plan",
                        str(baseline_path),
                        "--candidate-plan",
                        str(candidate_path),
                        "--repo-root",
                        str(root),
                        "--output",
                        str(output),
                        "--markdown-output",
                        str(markdown_output),
                    ]
                )
            result = json.loads(stdout.getvalue())
            report = json.loads(output.read_text(encoding="utf-8"))
            markdown = markdown_output.read_text(encoding="utf-8")

        self.assertEqual(code, 0)
        self.assertEqual(result["status"], "ready")
        self.assertEqual(report["report_type"], "run_readiness")
        self.assertIn("No model calls", markdown)


def _write_readiness_fixture(
    root: Path,
    *,
    candidate_grade_prompt: str = "Candidate grading policy.",
    candidate_rubric: dict[str, object] | None = None,
) -> tuple[Path, Path]:
    (root / "records").mkdir()
    course = CourseSpec.from_json_path(FIXTURES / "course_dsaa3073_hw1.json")
    input_root = _write_inputs(root)
    baseline = _build_plan(
        root=root,
        course=course,
        input_root=input_root,
        label="baseline",
        experiment_id="synthetic-baseline",
        skill_version_id="skill_baseline_v1",
        skill_hash="b" * 64,
        grade_template_id="grade_standard_v1",
        grade_prompt="Baseline grading policy.",
    )
    candidate = _build_plan(
        root=root,
        course=course,
        input_root=input_root,
        label="candidate",
        experiment_id="synthetic-candidate",
        skill_version_id="skill_candidate_v2",
        skill_hash="c" * 64,
        grade_template_id="grade_candidate_v2",
        grade_prompt=candidate_grade_prompt,
        grade_rubric=candidate_rubric,
    )
    baseline_path = root / "records" / "baseline-plan.json"
    candidate_path = root / "records" / "candidate-plan.json"
    write_experiment_plan(baseline, baseline_path)
    write_experiment_plan(candidate, candidate_path)
    return baseline_path, candidate_path


def _build_plan(
    *,
    root: Path,
    course: CourseSpec,
    input_root: Path,
    label: str,
    experiment_id: str,
    skill_version_id: str,
    skill_hash: str,
    grade_template_id: str,
    grade_prompt: str,
    grade_rubric: dict[str, object] | None = None,
) -> ExperimentPlan:
    transcribe_template_id = "transcribe_standard_v1"
    transcribe_prompt = "Transcribe only the visible anonymous response."
    planned_packets = (
        PlannedPacket(
            packet_id="T1-dev-r1",
            condition="T1",
            task="transcribe",
            prompt_template_id=transcribe_template_id,
            split="development",
        ),
        PlannedPacket(
            packet_id="G1-dev-r1",
            condition="G1",
            task="grade",
            prompt_template_id=grade_template_id,
            split="development",
        ),
    )
    built_packets = (
        _build_packet(
            root=root,
            course=course,
            input_root=input_root,
            label=label,
            experiment_id=experiment_id,
            skill_version_id=skill_version_id,
            planned_packet=planned_packets[0],
            prompt_text=transcribe_prompt,
        ),
        _build_packet(
            root=root,
            course=course,
            input_root=input_root,
            label=label,
            experiment_id=experiment_id,
            skill_version_id=skill_version_id,
            planned_packet=planned_packets[1],
            prompt_text=grade_prompt,
            rubric=grade_rubric or {
                "questions": [
                    {
                        "id": "Q1",
                        "max_score": 10,
                        "criteria": "Award credit for correct asymptotic reasoning.",
                    }
                ]
            },
        ),
    )
    return ExperimentPlan(
        experiment_id=experiment_id,
        course_id=course.course_id,
        assessment_id=course.assessment_id,
        status="packets_built",
        git_branch="codex/repro-experiment-framework",
        git_commit="abc1234",
        data_inventory_path="experiments/records/synthetic/inventory.json",
        data_snapshot_hash="a" * 64,
        course_spec_path="tests/fixtures/synthetic/course_dsaa3073_hw1.json",
        skill_version_id=skill_version_id,
        skill_source_paths={"agents": ".agents/skills/grade-homework/SKILL.md"},
        skill_hashes={"agents": skill_hash},
        prompt_template_hashes={
            transcribe_template_id: _text_hash(transcribe_prompt),
            grade_template_id: _text_hash(grade_prompt),
        },
        planned_packets=planned_packets,
        built_packets=built_packets,
    )


def _build_packet(
    *,
    root: Path,
    course: CourseSpec,
    input_root: Path,
    label: str,
    experiment_id: str,
    skill_version_id: str,
    planned_packet: PlannedPacket,
    prompt_text: str,
    rubric: dict[str, object] | None = None,
) -> BuiltPacket:
    output_root = root / "Data" / "packets" / label
    result = build_prompt_packet(
        PromptPacketSpec(
            course=course,
            packet_id=planned_packet.packet_id,
            condition=planned_packet.condition,
            task=planned_packet.task,
            prompt_text=prompt_text,
            student_ids=("S001",),
            input_root=input_root,
            output_root=output_root,
            rubric=rubric,
            metadata={
                "experiment_id": experiment_id,
                "skill_version_id": skill_version_id,
                "prompt_template_id": planned_packet.prompt_template_id,
                "split": planned_packet.split,
            },
        )
    )
    packet_path = result.packet_path.relative_to(root).as_posix()
    return BuiltPacket(
        packet_id=planned_packet.packet_id,
        condition=planned_packet.condition,
        task=planned_packet.task,
        split=planned_packet.split,
        packet_path=packet_path,
        prompt_path=f"{packet_path}/prompt.txt",
        manifest_path=f"{packet_path}/manifest.json",
        packet_hash=directory_digest(result.packet_path),
        audit_status="passed",
    )


def _write_inputs(root: Path) -> Path:
    student_dir = root / "inputs" / "S001"
    student_dir.mkdir(parents=True)
    (student_dir / "page-001.txt").write_text(
        "Anonymous visible response.\n",
        encoding="utf-8",
        newline="\n",
    )
    return root / "inputs"


def _init_clean_git_repo(root: Path) -> None:
    (root / ".gitignore").write_text("Data/\n", encoding="utf-8", newline="\n")
    _run_git(root, "init")
    _run_git(root, "checkout", "-b", "codex/repro-experiment-framework")
    _run_git(root, "add", ".")
    _run_git(
        root,
        "-c",
        "user.email=tests@example.invalid",
        "-c",
        "user.name=Readiness Tests",
        "commit",
        "-m",
        "fixture",
    )


def _run_git(root: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args],
        cwd=root,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=True,
    )


def _text_hash(text: str) -> str:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _status(report: dict[str, object], check_id: str) -> str:
    checks = report["checks"]
    assert isinstance(checks, list)
    for check in checks:
        assert isinstance(check, dict)
        if check["id"] == check_id:
            return str(check["status"])
    raise AssertionError(f"missing check: {check_id}")


if __name__ == "__main__":
    unittest.main()
