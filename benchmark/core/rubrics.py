from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from .schema import CourseSpec, QuestionSpec


REQUIRED_LEVELS = (
    "mentioned_only",
    "partial_understanding",
    "demonstrated",
)
REQUIRED_BANDS = (
    "full",
    "substantially_correct",
    "partially_correct",
    "minimal_relevant",
    "no_credit",
)
FORBIDDEN_RUBRIC_KEYS = {
    "student_id",
    "student_ids",
    "gold_score",
    "gold_scores",
    "primary_scores",
    "example_student_answer",
}
_CONCEPT_QUESTION_TYPES = {"short_answer", "proof", "essay"}


def validate_concept_rubric(rubric: dict[str, Any], course: CourseSpec) -> list[str]:
    """Return stable findings for the optional concept-keyterm rubric format."""
    if rubric.get("rubric_format") != "concept_keyterm_v1":
        return []

    findings: list[str] = []
    findings.extend(_forbidden_key_findings(rubric))

    questions = rubric.get("questions")
    if not isinstance(questions, list):
        findings.append("rubric questions must be a list")
        return sorted(set(findings))

    course_questions = course.question_map
    rubric_question_ids: list[str] = []
    element_ids: list[str] = []
    for index, rubric_question in enumerate(questions):
        if not isinstance(rubric_question, dict):
            findings.append(f"rubric question at index {index} must be an object")
            continue

        question_id = _question_id(rubric_question)
        if question_id is None:
            findings.append(f"rubric question at index {index} must define id")
            continue
        rubric_question_ids.append(question_id)
        course_question = course_questions.get(question_id)
        if course_question is None:
            continue

        maximum = rubric_question.get("max_score")
        if not _same_number(maximum, course_question.max_score):
            findings.append(
                f"{question_id} max_score must match course maximum {_score_label(course_question.max_score)}"
            )

        if _is_concept_question(rubric_question):
            findings.extend(
                _validate_concept_question(
                    rubric_question,
                    question_id,
                    course_question,
                    element_ids,
                )
            )

    duplicate_questions = _duplicates(rubric_question_ids)
    for question_id in duplicate_questions:
        findings.append(f"duplicate rubric question ID: {question_id}")
    for element_id in _duplicates(element_ids):
        findings.append(f"duplicate scoring element ID: {element_id}")

    rubric_question_id_set = set(rubric_question_ids)
    missing = sorted(set(course.question_ids) - rubric_question_id_set)
    extra = sorted(rubric_question_id_set - set(course.question_ids))
    if missing:
        findings.append("missing rubric question IDs: " + ", ".join(missing))
    if extra:
        findings.append("extra rubric question IDs: " + ", ".join(extra))
    return sorted(set(findings))


def require_valid_rubric(rubric: dict[str, Any], course: CourseSpec) -> None:
    """Raise one error containing every validation finding."""
    findings = validate_concept_rubric(rubric, course)
    if findings:
        raise ValueError("invalid concept-keyterm rubric: " + "; ".join(findings))


def _validate_concept_question(
    rubric_question: dict[str, Any],
    question_id: str,
    course_question: QuestionSpec,
    element_ids: list[str],
) -> list[str]:
    findings: list[str] = []
    scoring_elements = rubric_question.get("scoring_elements")
    if not isinstance(scoring_elements, list) or not scoring_elements:
        findings.append(f"{question_id} scoring_elements must be a non-empty list")
        scoring_elements = []

    demonstrated_total = 0.0
    for index, element in enumerate(scoring_elements):
        if not isinstance(element, dict):
            findings.append(f"{question_id} scoring element at index {index} must be an object")
            continue
        element_id = element.get("id", element.get("element_id"))
        if not isinstance(element_id, str) or not element_id:
            findings.append(f"{question_id} scoring element at index {index} must define id")
        else:
            element_ids.append(element_id)

        levels = element.get("levels")
        if not isinstance(levels, dict) or set(levels) != set(REQUIRED_LEVELS):
            findings.append(
                f"{question_id} levels must define exactly: {', '.join(REQUIRED_LEVELS)}"
            )
            continue

        level_values = [levels[level] for level in REQUIRED_LEVELS]
        if not all(_is_integer(value) for value in level_values) or not (
            level_values[0] < level_values[1] < level_values[2]
        ):
            findings.append(f"{question_id} level credits must be strictly ascending integers")
        for level, value in zip(REQUIRED_LEVELS, level_values, strict=True):
            if not _allows_score(course_question, value):
                findings.append(
                    f"{question_id} {level} credit must use the {_score_label(course_question.score_step)} score step"
                )
        if _is_number(levels["demonstrated"]):
            demonstrated_total += float(levels["demonstrated"])

    if demonstrated_total > course_question.max_score:
        findings.append(
            f"{question_id} demonstrated credits total {demonstrated_total} exceeds maximum {_score_label(course_question.max_score)}"
        )

    findings.extend(_validate_score_bands(rubric_question, question_id, course_question))
    findings.extend(_validate_material_errors(rubric_question, question_id, course_question))
    if not isinstance(rubric_question.get("full_credit_rule"), str) or not rubric_question[
        "full_credit_rule"
    ].strip():
        findings.append(f"{question_id} full_credit_rule must be non-empty text")
    return findings


def _validate_score_bands(
    rubric_question: dict[str, Any],
    question_id: str,
    course_question: QuestionSpec,
) -> list[str]:
    findings: list[str] = []
    bands = rubric_question.get("score_bands")
    if not isinstance(bands, dict) or set(bands) != set(REQUIRED_BANDS):
        findings.append(
            f"{question_id} score_bands must define exactly: {', '.join(REQUIRED_BANDS)}"
        )
    if not isinstance(bands, dict):
        return findings

    for band in REQUIRED_BANDS:
        bounds = bands.get(band)
        if not isinstance(bounds, dict):
            continue
        minimum = bounds.get("minimum")
        maximum = bounds.get("maximum")
        if not _allows_score(course_question, minimum) or not _allows_score(
            course_question, maximum
        ):
            findings.append(
                f"{question_id} {band} band bounds must be within 0..{_score_label(course_question.max_score)} and use the {_score_label(course_question.score_step)} score step"
            )
        if _is_number(minimum) and _is_number(maximum) and minimum > maximum:
            findings.append(f"{question_id} {band} band minimum must not exceed maximum")
    return findings


def _validate_material_errors(
    rubric_question: dict[str, Any],
    question_id: str,
    course_question: QuestionSpec,
) -> list[str]:
    material_errors = rubric_question.get("material_errors")
    if not isinstance(material_errors, list):
        return [f"{question_id} material_errors must be a list"]

    findings: list[str] = []
    for material_error in material_errors:
        if not isinstance(material_error, dict) or "cap" not in material_error:
            continue
        if not _allows_score(course_question, material_error["cap"]):
            findings.append(
                f"{question_id} material error cap must be within 0..{_score_label(course_question.max_score)} and use the {_score_label(course_question.score_step)} score step"
            )
    return findings


def _forbidden_key_findings(value: Any) -> list[str]:
    keys = sorted(set(_walk_keys(value)) & FORBIDDEN_RUBRIC_KEYS)
    return [f"forbidden rubric key: {key}" for key in keys]


def _walk_keys(value: Any) -> Iterable[str]:
    if isinstance(value, dict):
        for key, nested in value.items():
            if isinstance(key, str):
                yield key
            yield from _walk_keys(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from _walk_keys(nested)


def _question_id(rubric_question: dict[str, Any]) -> str | None:
    value = rubric_question.get("id", rubric_question.get("question_id"))
    return value if isinstance(value, str) and value else None


def _is_concept_question(rubric_question: dict[str, Any]) -> bool:
    return rubric_question.get("type") in _CONCEPT_QUESTION_TYPES or any(
        key in rubric_question
        for key in ("scoring_elements", "score_bands", "material_errors", "full_credit_rule")
    )


def _allows_score(question: QuestionSpec, value: Any) -> bool:
    return _is_number(value) and question.allows_score(float(value))


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _is_integer(value: Any) -> bool:
    return _is_number(value) and float(value).is_integer()


def _same_number(value: Any, expected: float) -> bool:
    return _is_number(value) and float(value) == expected


def _duplicates(values: list[str]) -> list[str]:
    return sorted({value for value in values if values.count(value) > 1})


def _score_label(value: float) -> str:
    return f"{float(value):.1f}"
