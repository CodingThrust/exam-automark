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

    def test_valid_course_content_drift_fails_same_course(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            b0, r1, c3 = _write_packets(root)
            _write_json(
                c3 / "course.json",
                {
                    "assessment_id": "week5",
                    "course_id": "synthetic",
                    "questions": [
                        {"id": "Q1", "max_score": 1, "score_step": 1}
                    ],
                    "revision": 2,
                },
            )
            _mutate_manifest(c3, course_hash=_sha256_file(c3 / "course.json"))

            report = _check(b0, r1, c3)

        self.assertEqual(report["status"], "not_ready")
        self.assertIn("same_course", report["failed_checks"])
        self.assertNotIn("packet_audits_pass", report["failed_checks"])

    def test_text_source_drift_is_not_ready(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            b0, r1, c3 = _write_packets(
                root,
                r1_input_text="different synthetic input",
            )
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

    def test_packet_input_mode_must_match_shared_text_only_mode(self):
        for packet_mode in (None, "multimodal"):
            with self.subTest(packet_mode=packet_mode), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                b0, r1, c3 = _write_packets(root)
                _set_packet_input_mode(r1, packet_mode)

                report = _check(b0, r1, c3)

            self.assertEqual(report["status"], "not_ready")
            self.assertIn("packet_audits_pass", report["failed_checks"])
            self.assertIn(
                "metadata.input_mode must equal shared input_mode text-only",
                _detail(report, "packet_audits_pass"),
            )

    def test_pdf_inputs_fail_even_when_all_declared_hashes_are_updated(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            b0, r1, c3 = _write_packets(root)
            for packet in (b0, r1, c3):
                _replace_student_input(
                    packet,
                    "S001",
                    "submission.pdf",
                    b"%PDF-1.7 synthetic",
                )

            report = _check(b0, r1, c3)

        self.assertEqual(report["status"], "not_ready")
        self.assertIn("packet_audits_pass", report["failed_checks"])
        self.assertIn(
            "text-only input cannot be image/PDF: S001/submission.pdf",
            _detail(report, "packet_audits_pass"),
        )

    def test_binary_inputs_fail_even_when_all_declared_hashes_are_updated(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            b0, r1, c3 = _write_packets(root)
            for packet in (b0, r1, c3):
                _replace_student_input(
                    packet,
                    "S001",
                    "payload.bin",
                    b"\x00\xff\x10\x80",
                )

            report = _check(b0, r1, c3)

        self.assertEqual(report["status"], "not_ready")
        self.assertIn(
            "unsupported text-only input file: S001/payload.bin",
            _detail(report, "packet_audits_pass"),
        )

    def test_binary_content_with_text_suffix_fails_without_crashing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            b0, r1, c3 = _write_packets(root)
            for packet in (b0, r1, c3):
                _replace_student_input(
                    packet,
                    "S001",
                    "payload.txt",
                    b"\x80\x81\xff",
                )

            report = _check(b0, r1, c3)

        self.assertEqual(report["status"], "not_ready")
        self.assertIn(
            "text-only input is not UTF-8: S001/payload.txt",
            _detail(report, "packet_audits_pass"),
        )

    def test_deleted_prompt_is_an_integrity_finding_not_an_exception(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            b0, r1, c3 = _write_packets(root)
            (c3 / "prompt.txt").unlink()

            report = _check(b0, r1, c3)

        self.assertEqual(report["status"], "not_ready")
        self.assertIn("packet_audits_pass", report["failed_checks"])
        self.assertIn(
            "missing required file: prompt.txt",
            _detail(report, "packet_audits_pass"),
        )

    def test_tampered_prompt_fails_packet_integrity(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            b0, r1, c3 = _write_packets(root)
            (r1 / "prompt.txt").write_text(
                "Tampered after manifest creation.\n",
                encoding="utf-8",
                newline="\n",
            )

            report = _check(b0, r1, c3)

        self.assertEqual(report["status"], "not_ready")
        self.assertIn("packet_audits_pass", report["failed_checks"])
        self.assertIn(
            "prompt_hash does not match prompt.txt",
            _detail(report, "packet_audits_pass"),
        )

    def test_tampered_course_file_fails_another_artifact_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            b0, r1, c3 = _write_packets(root)
            _write_json(c3 / "course.json", {"course_id": "tampered"})

            report = _check(b0, r1, c3)

        self.assertEqual(report["status"], "not_ready")
        self.assertIn(
            "course_hash does not match course.json",
            _detail(report, "packet_audits_pass"),
        )

    def test_blank_prompt_fails_even_when_manifest_hash_is_updated(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            b0, r1, c3 = _write_packets(root)
            for packet in (b0, r1):
                _replace_hashed_artifact(
                    packet,
                    "prompt.txt",
                    "prompt_hash",
                    b"  \n\t",
                )

            report = _check(b0, r1, c3)

        self.assertEqual(report["status"], "not_ready")
        self.assertIn("packet_audits_pass", report["failed_checks"])
        self.assertIn(
            "prompt.txt must contain non-whitespace UTF-8 text",
            _detail(report, "packet_audits_pass"),
        )

    def test_non_utf8_prompt_fails_deterministically_with_updated_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            b0, r1, c3 = _write_packets(root)
            for packet in (b0, r1):
                _replace_hashed_artifact(
                    packet,
                    "prompt.txt",
                    "prompt_hash",
                    b"\xff\xfe",
                )

            report = _check(b0, r1, c3)

        self.assertEqual(report["status"], "not_ready")
        self.assertIn(
            "prompt.txt must contain non-whitespace UTF-8 text",
            _detail(report, "packet_audits_pass"),
        )

    def test_json_artifacts_require_utf8_json_objects_with_updated_hashes(self):
        cases = (
            ("course.json", "course_hash", b"{not-json"),
            ("rubric.json", "rubric_hash", b"\xff\xfe"),
            ("output.schema.json", "output_schema_hash", b"[]\n"),
        )
        for filename, hash_field, payload in cases:
            with self.subTest(filename=filename), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                b0, r1, c3 = _write_packets(root)
                for packet in (b0, r1, c3):
                    _replace_hashed_artifact(packet, filename, hash_field, payload)

                report = _check(b0, r1, c3)

            self.assertEqual(report["status"], "not_ready")
            self.assertIn("packet_audits_pass", report["failed_checks"])
            self.assertIn(
                f"{filename} must contain a UTF-8 JSON object",
                _detail(report, "packet_audits_pass"),
            )

    def test_invalid_course_spec_fails_with_updated_matching_hashes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            b0, r1, c3 = _write_packets(root)
            payload = json.dumps(
                {
                    "assessment_id": "week5",
                    "course_id": "synthetic",
                    "questions": [],
                },
                sort_keys=True,
            ).encode("utf-8")
            for packet in (b0, r1, c3):
                _replace_hashed_artifact(
                    packet,
                    "course.json",
                    "course_hash",
                    payload,
                )

            report = _check(b0, r1, c3)

        self.assertEqual(report["status"], "not_ready")
        self.assertIn(
            "course.json must satisfy CourseSpec",
            _detail(report, "packet_audits_pass"),
        )

    def test_manifest_course_id_must_match_each_packet_course_spec(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            b0, r1, c3 = _write_packets(root)
            for packet in (b0, r1, c3):
                _mutate_manifest(packet, course_id="consistently-wrong-course")

            report = _check(b0, r1, c3)

        self.assertEqual(report["status"], "not_ready")
        self.assertNotIn("same_course", report["failed_checks"])
        self.assertIn("packet_audits_pass", report["failed_checks"])
        self.assertIn(
            "manifest.course_id must equal course.json course_id",
            _detail(report, "packet_audits_pass"),
        )

    def test_manifest_assessment_id_must_match_each_packet_course_spec(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            b0, r1, c3 = _write_packets(root)
            for packet in (b0, r1, c3):
                _mutate_manifest(
                    packet,
                    assessment_id="consistently-wrong-assessment",
                )

            report = _check(b0, r1, c3)

        self.assertEqual(report["status"], "not_ready")
        self.assertNotIn("same_assessment", report["failed_checks"])
        self.assertIn("packet_audits_pass", report["failed_checks"])
        self.assertIn(
            "manifest.assessment_id must equal course.json assessment_id",
            _detail(report, "packet_audits_pass"),
        )

    def test_manifest_student_ids_must_match_course_anonymous_id_pattern(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            b0, r1, c3 = _write_packets(root, students=("Alice", "Bob"))

            report = _check(b0, r1, c3)

        detail = _detail(report, "packet_audits_pass")
        self.assertEqual(report["status"], "not_ready")
        self.assertNotIn("same_students", report["failed_checks"])
        self.assertIn("packet_audits_pass", report["failed_checks"])
        self.assertIn(
            "student_ids must match course anonymous_id_pattern",
            detail,
        )
        self.assertNotIn("Alice", detail)
        self.assertNotIn("Bob", detail)

    def test_invalid_concept_rubric_fails_with_updated_matching_hashes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            b0, r1, c3 = _write_packets(root)
            payload = json.dumps(
                {"questions": [], "rubric_format": "concept_keyterm_v1"},
                sort_keys=True,
            ).encode("utf-8")
            for packet in (r1, c3):
                _replace_hashed_artifact(
                    packet,
                    "rubric.json",
                    "rubric_hash",
                    payload,
                )

            report = _check(b0, r1, c3)

        self.assertEqual(report["status"], "not_ready")
        self.assertIn(
            "rubric.json concept-rubric finding: missing rubric question IDs: Q1",
            _detail(report, "packet_audits_pass"),
        )

    def test_packet_conditions_must_match_b0_r1_c3_roles(self):
        cases = (
            ({"B0": "b0"}, ("condition must equal packet role B0",)),
            ({"C3": "R1"}, ("condition must equal packet role C3",)),
            (
                {"B0": "R1", "R1": "B0"},
                (
                    "condition must equal packet role B0",
                    "condition must equal packet role R1",
                ),
            ),
        )
        for mutations, expected_findings in cases:
            with self.subTest(mutations=mutations), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                b0, r1, c3 = _write_packets(root)
                packets = {"B0": b0, "R1": r1, "C3": c3}
                for role, condition in mutations.items():
                    _mutate_manifest(packets[role], condition=condition)

                report = _check(b0, r1, c3)

            detail = _detail(report, "packet_audits_pass")
            self.assertEqual(report["status"], "not_ready")
            self.assertIn("packet_audits_pass", report["failed_checks"])
            for finding in expected_findings:
                self.assertIn(finding, detail)

    def test_malformed_student_ids_string_fails_packet_integrity(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            b0, r1, c3 = _write_packets(root)
            _mutate_manifest(r1, student_ids="S001,S002")

            report = _check(b0, r1, c3)

        self.assertEqual(report["status"], "not_ready")
        self.assertIn("packet_audits_pass", report["failed_checks"])
        self.assertIn(
            "student_ids must be a non-empty list of unique non-empty strings",
            _detail(report, "packet_audits_pass"),
        )

    def test_invalid_declared_hash_fails_packet_integrity(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            b0, r1, c3 = _write_packets(root)
            _mutate_manifest(b0, course_hash="not-a-sha256")

            report = _check(b0, r1, c3)

        self.assertEqual(report["status"], "not_ready")
        self.assertIn(
            "course_hash must be a 64-hex SHA-256 value",
            _detail(report, "packet_audits_pass"),
        )

    def test_missing_and_extra_student_input_directories_fail_integrity(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            b0, r1, c3 = _write_packets(root)
            (r1 / "inputs" / "S001" / "transcript.json").unlink()
            (r1 / "inputs" / "S001").rmdir()
            extra = r1 / "inputs" / "S999"
            extra.mkdir()
            _write_json(extra / "transcript.json", {"student_id": "S999"})

            report = _check(b0, r1, c3)

        detail = _detail(report, "packet_audits_pass")
        self.assertEqual(report["status"], "not_ready")
        self.assertIn("missing student input directory: S001", detail)
        self.assertIn("unexpected student input directory: S999", detail)

    def test_empty_declared_student_input_directory_fails_integrity(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            b0, r1, c3 = _write_packets(root)
            (r1 / "inputs" / "S001" / "transcript.json").unlink()
            manifest_path = r1 / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["input_hashes"]["S001"] = _directory_digest(
                r1 / "inputs" / "S001"
            )
            manifest["metadata"]["text_source_hash"] = _directory_digest(
                r1 / "inputs"
            )
            _write_json(manifest_path, manifest)

            report = _check(b0, r1, c3)

        self.assertEqual(report["status"], "not_ready")
        self.assertIn(
            "student input directory contains no files: S001",
            _detail(report, "packet_audits_pass"),
        )

    def test_uppercase_sha256_declarations_are_accepted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            b0, r1, c3 = _write_packets(root)
            for packet in (b0, r1, c3):
                _uppercase_manifest_hashes(packet)

            report = _check(b0, r1, c3)

        self.assertEqual(report["status"], "ready")
        self.assertEqual(report["failed_checks"], [])

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
    r1_input_text: str = "synthetic input",
    c3_schema: dict[str, str] | None = None,
    students: tuple[str, ...] = ("S001", "S002"),
    c3_students: tuple[str, ...] | None = None,
    c3_skill_hash: str = "b" * 64,
) -> tuple[Path, Path, Path]:
    b0 = _write_packet(
        root / "B0",
        condition="B0",
        prompt="Baseline grading policy.",
        rubric={"version": "v0"},
        skill_hash="a" * 64,
        students=students,
    )
    r1 = _write_packet(
        root / "R1",
        condition="R1",
        prompt=r1_prompt,
        rubric=r1_rubric or {"version": "v1"},
        skill_hash="a" * 64,
        input_text=r1_input_text,
        students=students,
    )
    c3 = _write_packet(
        root / "C3",
        condition="C3",
        prompt="Candidate v3 grading policy.",
        rubric={"version": "v1"},
        skill_hash=c3_skill_hash,
        schema=c3_schema,
        students=students if c3_students is None else c3_students,
    )
    return b0, r1, c3


def _write_packet(
    root: Path,
    *,
    condition: str,
    prompt: str,
    rubric: dict[str, str],
    skill_hash: str,
    input_text: str = "synthetic input",
    schema: dict[str, str] | None = None,
    students: tuple[str, ...] = ("S001", "S002"),
) -> Path:
    root.mkdir(parents=True)
    output_schema = schema or {"type": "object"}
    _write_json(
        root / "course.json",
        {
            "assessment_id": "week5",
            "course_id": "synthetic",
            "questions": [{"id": "Q1", "max_score": 1, "score_step": 1}],
        },
    )
    _write_json(root / "output.schema.json", output_schema)
    _write_json(root / "rubric.json", rubric)
    (root / "prompt.txt").write_text(prompt + "\n", encoding="utf-8", newline="\n")
    input_hashes = {}
    for student_id in students:
        student_input = root / "inputs" / student_id
        student_input.mkdir(parents=True)
        _write_json(
            student_input / "transcript.json",
            {"student_id": student_id, "text": input_text},
        )
        input_hashes[student_id] = _directory_digest(student_input)
    manifest = {
        "schema_version": 1,
        "packet_id": f"{condition}-synthetic-r1",
        "assessment_id": "week5",
        "condition": condition,
        "course_id": "synthetic",
        "metadata": {
            "data_snapshot_hash": "d" * 64,
            "input_mode": "text-only",
            "skill_hash": skill_hash,
            "skill_version_id": "baseline" if skill_hash == "a" * 64 else "candidate-v3",
            "split": "development",
            "text_source_hash": _directory_digest(root / "inputs"),
        },
        "course_hash": _sha256_file(root / "course.json"),
        "input_hashes": input_hashes,
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


def _directory_digest(path: Path) -> str:
    digest = hashlib.sha256()
    for file_path in sorted(item for item in path.rglob("*") if item.is_file()):
        digest.update(file_path.relative_to(path).as_posix().encode("utf-8"))
        digest.update(file_path.read_bytes())
    return digest.hexdigest()


def _mutate_manifest(packet: Path, **updates: object) -> None:
    path = packet / "manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest.update(updates)
    _write_json(path, manifest)


def _replace_hashed_artifact(
    packet: Path,
    filename: str,
    hash_field: str,
    payload: bytes,
) -> None:
    artifact = packet / filename
    artifact.write_bytes(payload)
    _mutate_manifest(packet, **{hash_field: _sha256_file(artifact)})


def _set_packet_input_mode(packet: Path, value: str | None) -> None:
    path = packet / "manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if value is None:
        manifest["metadata"].pop("input_mode")
    else:
        manifest["metadata"]["input_mode"] = value
    _write_json(path, manifest)


def _replace_student_input(
    packet: Path,
    student_id: str,
    filename: str,
    payload: bytes,
) -> None:
    student_input = packet / "inputs" / student_id
    for path in student_input.rglob("*"):
        if path.is_file():
            path.unlink()
    (student_input / filename).write_bytes(payload)
    manifest_path = packet / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["input_hashes"][student_id] = _directory_digest(student_input)
    manifest["metadata"]["text_source_hash"] = _directory_digest(packet / "inputs")
    _write_json(manifest_path, manifest)


def _uppercase_manifest_hashes(packet: Path) -> None:
    path = packet / "manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    for key in ("prompt_hash", "course_hash", "rubric_hash", "output_schema_hash"):
        manifest[key] = manifest[key].upper()
    manifest["input_hashes"] = {
        student_id: value.upper()
        for student_id, value in manifest["input_hashes"].items()
    }
    for key in ("data_snapshot_hash", "skill_hash", "text_source_hash"):
        manifest["metadata"][key] = manifest["metadata"][key].upper()
    _write_json(path, manifest)


def _detail(report: dict[str, object], check_id: str) -> str:
    checks = report["checks"]
    assert isinstance(checks, list)
    for check in checks:
        assert isinstance(check, dict)
        if check["id"] == check_id:
            return str(check["detail"])
    raise AssertionError(f"missing check: {check_id}")


if __name__ == "__main__":
    unittest.main()
