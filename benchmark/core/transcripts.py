import json
from pathlib import Path
from typing import Any, Sequence

from .schema import CourseSpec


def validate_transcript_source(
    course: CourseSpec,
    transcript_source: Path,
    student_ids: Sequence[str],
) -> dict[str, Any]:
    if not student_ids:
        raise ValueError("student_ids must not be empty")
    expected_students = tuple(student_ids)
    for student_id in expected_students:
        course.validate_student_id(student_id)

    missing_students = []
    invalid_transcripts = []
    valid_count = 0
    for student_id in expected_students:
        source = _find_transcript_source(transcript_source, student_id)
        if source is None:
            missing_students.append(student_id)
            continue
        error = _validate_transcript_file(source, student_id, course)
        if error is None:
            valid_count += 1
        else:
            invalid_transcripts.append(
                {
                    "student_id": student_id,
                    "path": source.as_posix(),
                    "error": error,
                }
            )

    checks = [
        _check(
            "all_expected_transcripts_present",
            not missing_students,
            "all expected transcript files are present"
            if not missing_students
            else f"{len(missing_students)} transcript files missing",
        ),
        _check(
            "transcripts_match_course_schema",
            not invalid_transcripts,
            "all transcript files match the course transcript schema"
            if not invalid_transcripts
            else f"{len(invalid_transcripts)} transcript files invalid",
        ),
    ]
    failed_checks = [check["id"] for check in checks if check["status"] == "failed"]
    return {
        "schema_version": 1,
        "report_type": "transcript_readiness",
        "status": "not_ready" if failed_checks else "ready",
        "course_id": course.course_id,
        "assessment_id": course.assessment_id,
        "transcript_source": transcript_source.as_posix(),
        "expected_student_count": len(expected_students),
        "expected_question_count": len(course.question_ids),
        "valid_transcript_count": valid_count,
        "missing_students": missing_students,
        "invalid_transcripts": invalid_transcripts,
        "checks": checks,
        "failed_checks": failed_checks,
    }


def write_transcript_report(report: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _find_transcript_source(root: Path, student_id: str) -> Path | None:
    candidates = (
        root / f"{student_id}.json",
        root / student_id / "transcript.json",
        root / student_id / f"{student_id}.json",
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def _validate_transcript_file(
    path: Path,
    student_id: str,
    course: CourseSpec,
) -> str | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as error:
        return f"invalid JSON: {error}"
    if not isinstance(payload, dict):
        return "transcript must be a JSON object"
    if payload.get("student_id") != student_id:
        return f"student_id mismatch: expected {student_id}"
    answers = payload.get("answers")
    if not isinstance(answers, list):
        return "answers must be a list"
    question_ids = []
    for answer in answers:
        if not isinstance(answer, dict):
            return "each answer must be an object"
        question_id = answer.get("question_id")
        if not isinstance(question_id, str):
            return "answer question_id must be text"
        if not isinstance(answer.get("text"), str):
            return f"{question_id} text must be text"
        if not isinstance(answer.get("unclear"), bool):
            return f"{question_id} unclear must be boolean"
        question_ids.append(question_id)
    if set(question_ids) != set(course.question_ids) or len(question_ids) != len(
        set(question_ids)
    ):
        return "answer question_ids must match the course spec exactly once"
    return None


def _check(check_id: str, passed: bool, detail: str) -> dict[str, str]:
    return {
        "id": check_id,
        "status": "passed" if passed else "failed",
        "detail": detail,
    }
