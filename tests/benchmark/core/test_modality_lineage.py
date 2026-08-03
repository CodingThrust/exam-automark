from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from benchmark.core.modality_lineage import (
    ModalityLineageError,
    validate_modality_lineage,
    write_lineage_report,
)
from benchmark.core.packets import directory_digest


REPO_ROOT = Path(__file__).parents[3]


class ModalityLineageTests(unittest.TestCase):
    def test_accepts_matched_routes_and_writes_deterministic_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = _make_matched_route(Path(tmp))

            report = _validate(paths)
            report_path = Path(tmp) / "records" / "lineage.json"
            first = write_lineage_report(report_path, report)
            second = write_lineage_report(report_path, report)

        self.assertEqual(report["status"], "ready")
        self.assertEqual(report["student_count"], 2)
        self.assertEqual(report["direct_condition"], "M1")
        self.assertEqual(report["transcript_first_condition"], "G1")
        self.assertEqual(first, "written")
        self.assertEqual(second, "reused")
        self.assertEqual(len(report["checks"]), 5)

    def test_rejects_duplicate_anonymous_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = _make_matched_route(Path(tmp))
            manifest_path = paths["direct_packet"] / "manifest.json"
            manifest = _read_json(manifest_path)
            manifest["student_ids"] = ["S001", "S001"]
            _write_json(manifest_path, manifest)

            with self.assertRaisesRegex(ModalityLineageError, "contains duplicates"):
                _validate(paths)

    def test_rejects_scope_or_snapshot_drift(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = _make_matched_route(Path(tmp))
            manifest_path = paths["text_packet"] / "manifest.json"
            manifest = _read_json(manifest_path)
            manifest["metadata"]["scope_id"] = "different-scope"
            _write_json(manifest_path, manifest)

            with self.assertRaisesRegex(ModalityLineageError, "scope_id values differ"):
                _validate(paths)

            manifest = _read_json(manifest_path)
            manifest["metadata"]["scope_id"] = "q1-q4-q9-q10"
            manifest["metadata"].pop("input_snapshot_manifest_sha256")
            _write_json(manifest_path, manifest)

            with self.assertRaisesRegex(
                ModalityLineageError, "requires input_snapshot_manifest_sha256"
            ):
                _validate(paths)

    def test_rejects_image_route_drift_even_when_t1_manifest_is_refreshed(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = _make_matched_route(Path(tmp))
            tampered = paths["transcription_packet"] / "inputs" / "S001" / "page.png"
            tampered.write_bytes(b"different-approved-looking-image")
            transcription_manifest = _read_json(
                paths["transcription_packet"] / "manifest.json"
            )
            transcription_manifest["input_hashes"]["S001"] = directory_digest(
                tampered.parent
            )
            _write_json(paths["transcription_packet"] / "manifest.json", transcription_manifest)

            with self.assertRaisesRegex(ModalityLineageError, "image input hashes differ"):
                _validate(paths)

    def test_rejects_missing_run_provenance_and_source_hash_drift(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = _make_matched_route(Path(tmp))
            text_manifest_path = paths["text_packet"] / "manifest.json"
            text_manifest = _read_json(text_manifest_path)
            text_manifest["metadata"].pop("source_run_id")
            _write_json(text_manifest_path, text_manifest)

            with self.assertRaisesRegex(ModalityLineageError, "source_run_id"):
                _validate(paths)

            text_manifest = _read_json(text_manifest_path)
            text_manifest["metadata"]["source_run_id"] = "kimi-transcription"
            _write_json(text_manifest_path, text_manifest)
            (paths["run_output"] / "outputs" / "S002.json").write_text(
                '{"student_id":"S002","answers":[]}', encoding="utf-8"
            )

            with self.assertRaisesRegex(ModalityLineageError, "source hash does not match"):
                _validate(paths)

    def test_rejects_transcription_engine_or_model_drift(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = _make_matched_route(Path(tmp))
            text_manifest_path = paths["text_packet"] / "manifest.json"
            text_manifest = _read_json(text_manifest_path)
            text_manifest["metadata"]["transcription_engine"] = "claude"
            _write_json(text_manifest_path, text_manifest)

            with self.assertRaisesRegex(
                ModalityLineageError, "transcription_engine does not match"
            ):
                _validate(paths)

    def test_standalone_script_writes_safe_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = _make_matched_route(root)
            report_path = root / "lineage-report.json"
            completed = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    str(REPO_ROOT / "scripts" / "validate_modality_lineage.py"),
                    "--direct-multimodal-packet",
                    str(paths["direct_packet"]),
                    "--transcription-packet",
                    str(paths["transcription_packet"]),
                    "--transcript-first-packet",
                    str(paths["text_packet"]),
                    "--transcription-run-output",
                    str(paths["run_output"]),
                    "--transcription-run-id",
                    "kimi-transcription",
                    "--output",
                    str(report_path),
                ],
                cwd=REPO_ROOT,
                capture_output=True,
                check=False,
                text=True,
            )

            report = json.loads(completed.stdout)
            written = _read_json(report_path)

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(report["status"], "ready")
        self.assertEqual(report["report_write_status"], "written")
        self.assertEqual(written["record_type"], "direct_multimodal_transcript_lineage")


def _validate(paths: dict[str, Path]) -> dict[str, object]:
    return validate_modality_lineage(
        direct_multimodal_packet=paths["direct_packet"],
        transcription_packet=paths["transcription_packet"],
        transcript_first_packet=paths["text_packet"],
        transcription_run_output=paths["run_output"],
        transcription_run_id="kimi-transcription",
    )


def _make_matched_route(root: Path) -> dict[str, Path]:
    student_ids = ("S001", "S002")
    course_bytes = b'{"assessment_id":"synthetic","course_id":"course"}\n'
    grade_prompt_bytes = b"Grade the scoped answers.\n"
    transcript_grade_prompt_bytes = b"Grade the scoped transcript answers.\n"
    transcription_prompt_bytes = b"Transcribe the scoped answers.\n"
    rubric_bytes = b'{"rubric_version":"synthetic-v1"}\n'
    snapshot_hash = "a" * 64

    direct = root / "packets" / "M1"
    transcription = root / "packets" / "T1"
    for packet in (direct, transcription):
        for student_id in student_ids:
            input_dir = packet / "inputs" / student_id
            input_dir.mkdir(parents=True, exist_ok=True)
            (input_dir / "page.png").write_bytes(
                f"same-image:{student_id}".encode("ascii")
            )
        (packet / "outputs").mkdir()
        (packet / "course.json").write_bytes(course_bytes)

    (direct / "prompt.txt").write_bytes(grade_prompt_bytes)
    (direct / "rubric.json").write_bytes(rubric_bytes)
    (transcription / "prompt.txt").write_bytes(transcription_prompt_bytes)

    common_metadata = {
        "scope_id": "q1-q4-q9-q10",
        "input_snapshot_manifest_sha256": snapshot_hash,
        "split": "development",
    }
    _write_packet_manifest(
        direct,
        packet_id="M1-dev",
        condition="M1",
        task="grade",
        student_ids=student_ids,
        metadata={**common_metadata, "input_route": "direct_multimodal"},
        rubric_hash=_sha256(direct / "rubric.json"),
    )
    _write_packet_manifest(
        transcription,
        packet_id="T1-dev",
        condition="T1",
        task="transcribe",
        student_ids=student_ids,
        metadata={**common_metadata, "input_route": "transcription"},
        rubric_hash=None,
    )

    run_output = root / "runs" / "kimi-transcription"
    outputs = run_output / "outputs"
    outputs.mkdir(parents=True)
    source_hashes: dict[str, str] = {}
    for student_id in student_ids:
        source = outputs / f"{student_id}.json"
        source.write_text(
            json.dumps({"student_id": student_id, "answers": []}) + "\n",
            encoding="utf-8",
        )
        source_hashes[student_id] = _sha256(source)

    text = root / "packets" / "G1"
    for student_id in student_ids:
        input_dir = text / "inputs" / student_id
        input_dir.mkdir(parents=True, exist_ok=True)
        (input_dir / "transcript.json").write_bytes(
            (outputs / f"{student_id}.json").read_bytes()
        )
    (text / "outputs").mkdir()
    (text / "course.json").write_bytes(course_bytes)
    (text / "prompt.txt").write_bytes(transcript_grade_prompt_bytes)
    (text / "rubric.json").write_bytes(rubric_bytes)
    _write_packet_manifest(
        text,
        packet_id="G1-dev",
        condition="G1",
        task="grade",
        student_ids=student_ids,
        metadata={
            **common_metadata,
            "input_mode": "text-only",
            "source_run_id": "kimi-transcription",
            "source_transcription_packet_hash": directory_digest(transcription),
            "text_source_hash": directory_digest(text / "inputs"),
            "text_source_input_hashes": source_hashes,
            "text_source_kind": "kimi_fresh_automatic_transcript",
            "text_source_path": outputs.as_posix(),
            "transcription_engine": "kimi",
            "transcription_model": "kimi-test",
        },
        rubric_hash=_sha256(text / "rubric.json"),
    )

    _write_json(
        run_output / "run-metadata.json",
        {
            "schema_version": 1,
            "record_type": "model_packet_run",
            "task": "transcribe",
            "input_mode": "multimodal",
            "course_id": "course",
            "assessment_id": "synthetic",
            "split": "development",
            "student_ids": list(student_ids),
            "packet_hash": directory_digest(transcription),
            "validation_status": "passed",
            "engine": "kimi",
            "model": "kimi-test",
        },
    )
    _write_json(
        run_output / "validation.json",
        {
            "status": "passed",
            "students_expected": 2,
            "students_passed": 2,
        },
    )
    return {
        "direct_packet": direct,
        "transcription_packet": transcription,
        "text_packet": text,
        "run_output": run_output,
    }


def _write_packet_manifest(
    packet: Path,
    *,
    packet_id: str,
    condition: str,
    task: str,
    student_ids: tuple[str, ...],
    metadata: dict[str, object],
    rubric_hash: str | None,
) -> None:
    _write_json(
        packet / "manifest.json",
        {
            "schema_version": 1,
            "packet_id": packet_id,
            "course_id": "course",
            "assessment_id": "synthetic",
            "condition": condition,
            "task": task,
            "student_ids": list(student_ids),
            "prompt_hash": _sha256(packet / "prompt.txt"),
            "course_hash": _sha256(packet / "course.json"),
            "output_schema_hash": "b" * 64,
            "rubric_hash": rubric_hash,
            "input_hashes": {
                student_id: directory_digest(packet / "inputs" / student_id)
                for student_id in student_ids
            },
            "metadata": metadata,
        },
    )


def _read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


if __name__ == "__main__":
    unittest.main()
