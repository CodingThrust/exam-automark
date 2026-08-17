from __future__ import annotations

from collections.abc import Iterable
from decimal import Decimal
import re
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
BAND_COVERAGE_ORDER = tuple(reversed(REQUIRED_BANDS))
FORBIDDEN_RUBRIC_KEYS = {
    "student_id",
    "student_ids",
    "gold_score",
    "gold_scores",
    "primary_scores",
    "example_student_answer",
}
_CONCEPT_QUESTION_TYPES = {"short_answer", "proof", "essay"}
EXECUTION_CONTRACT_FORMAT = "execution_contract_v1"
EXECUTION_QUESTION_TYPES = {
    "algorithm",
    "calculation",
    "calculation_short_answer",
    "conceptual",
    "diagram",
    "essay",
    "objective_selection",
    "open_response",
    "proof",
    "representation",
    "short_answer",
    "true_false",
}
EXECUTION_GLOBAL_RULES = {
    "score_declared_criteria_only": True,
    "irrelevant_extra_content": "ignore_unless_directly_contradicts_declared_criterion",
    "alternative_valid_methods": "accept_when_declared_criteria_are_met",
    "deduction_locality": "first_material_error_no_double_count",
    "criterion_evidence": "explicit_per_criterion",
}
ANSWER_FORM_RULES = {
    "simplification": {
        "required",
        "not_required",
        "equivalent_form_accepted",
    },
    "explanation": {"required", "not_required"},
    "working": {"required", "not_required", "answer_only_cap"},
}
AMBIGUOUS_RUBRIC_LANGUAGE = re.compile(
    r"\b(?:as appropriate|generally|may|normally|reasonable|should|typically|usually)\b",
    re.IGNORECASE,
)


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
    findings = validate_rubric(rubric, course)
    if findings:
        rubric_label = (
            "execution-contract"
            if rubric.get("rubric_format") == EXECUTION_CONTRACT_FORMAT
            else "concept-keyterm"
        )
        raise ValueError(f"invalid {rubric_label} rubric: " + "; ".join(findings))


def validate_rubric(rubric: dict[str, Any], course: CourseSpec) -> list[str]:
    """Validate an opted-in rubric format while keeping legacy rubrics valid."""

    if rubric.get("rubric_format") == EXECUTION_CONTRACT_FORMAT:
        return validate_execution_contract_rubric(rubric, course)
    return validate_concept_rubric(rubric, course)


def validate_execution_contract_rubric(
    rubric: dict[str, Any], course: CourseSpec
) -> list[str]:
    """Validate a detailed leaf-level rubric for repeatable cross-agent scoring."""

    findings = _forbidden_key_findings(rubric)
    global_rules = rubric.get("global_scoring_rules")
    if global_rules != EXECUTION_GLOBAL_RULES:
        findings.append(
            "execution rubric global_scoring_rules must exactly declare the shared scoring rules"
        )
    questions = rubric.get("questions")
    if not isinstance(questions, list):
        return sorted(set(findings + ["execution rubric questions must be a list"]))

    question_ids: list[str] = []
    criterion_ids: list[str] = []
    question_map = course.question_map
    for index, question in enumerate(questions):
        if not isinstance(question, dict):
            findings.append(f"execution rubric question at index {index} must be an object")
            continue
        question_id = _question_id(question)
        if question_id is None:
            findings.append(f"execution rubric question at index {index} must define id")
            continue
        question_ids.append(question_id)
        course_question = question_map.get(question_id)
        if course_question is None:
            continue
        if not _same_number(question.get("max_score"), course_question.max_score):
            findings.append(
                f"{question_id} max_score must match course maximum {_score_label(course_question.max_score)}"
            )
        if question.get("question_type") not in EXECUTION_QUESTION_TYPES:
            findings.append(f"{question_id} question_type must be an execution contract type")
        findings.extend(
            _validate_answer_form_requirements(question, question_id, course_question)
        )
        findings.extend(
            _validate_execution_criteria(
                question, question_id, course_question, criterion_ids
            )
        )

    for question_id in _duplicates(question_ids):
        findings.append(f"duplicate rubric question ID: {question_id}")
    for criterion_id in _duplicates(criterion_ids):
        findings.append(f"duplicate execution criterion ID: {criterion_id}")
    missing = sorted(set(course.question_ids) - set(question_ids))
    extra = sorted(set(question_ids) - set(course.question_ids))
    if missing:
        findings.append("missing rubric question IDs: " + ", ".join(missing))
    if extra:
        findings.append("extra rubric question IDs: " + ", ".join(extra))
    return sorted(set(findings))


def execution_criterion_ids(
    rubric: dict[str, Any], question_id: str
) -> set[str] | None:
    """Return an opted-in leaf's permitted trace criterion IDs, if available."""

    if rubric.get("rubric_format") != EXECUTION_CONTRACT_FORMAT:
        return None
    questions = rubric.get("questions")
    if not isinstance(questions, list):
        return None
    for question in questions:
        if not isinstance(question, dict) or _question_id(question) != question_id:
            continue
        criteria = question.get("criteria")
        if not isinstance(criteria, list):
            return None
        return {
            criterion["id"]
            for criterion in criteria
            if isinstance(criterion, dict) and isinstance(criterion.get("id"), str)
        }
    return None


def execution_criterion_points(
    rubric: dict[str, Any], question_id: str
) -> dict[str, float] | None:
    """Return an opted-in leaf's criterion-to-points map, if available."""

    if rubric.get("rubric_format") != EXECUTION_CONTRACT_FORMAT:
        return None
    questions = rubric.get("questions")
    if not isinstance(questions, list):
        return None
    for question in questions:
        if not isinstance(question, dict) or _question_id(question) != question_id:
            continue
        criteria = question.get("criteria")
        if not isinstance(criteria, list):
            return None
        return {
            criterion["id"]: float(criterion["points"])
            for criterion in criteria
            if isinstance(criterion, dict)
            and isinstance(criterion.get("id"), str)
            and _is_number(criterion.get("points"))
        }
    return None


def _validate_answer_form_requirements(
    question: dict[str, Any], question_id: str, course_question: QuestionSpec
) -> list[str]:
    requirements = question.get("answer_form_requirements")
    expected_keys = set(ANSWER_FORM_RULES)
    if not isinstance(requirements, dict) or set(requirements) != expected_keys:
        return [
            f"{question_id} answer_form_requirements must define exactly: "
            "simplification, explanation, working"
        ]
    findings: list[str] = []
    for field, allowed_values in ANSWER_FORM_RULES.items():
        if requirements[field] not in allowed_values:
            findings.append(f"{question_id} {field} requirement is invalid")
    answer_only_cap = question.get("answer_only_cap")
    if requirements["working"] == "answer_only_cap":
        if not _allows_score(course_question, answer_only_cap) or _same_number(
            answer_only_cap, course_question.max_score
        ):
            findings.append(
                f"{question_id} answer_only_cap must be below the maximum and use the score step"
            )
    elif answer_only_cap is not None:
        findings.append(
            f"{question_id} answer_only_cap is allowed only when working uses answer_only_cap"
        )
    return findings


def _validate_execution_criteria(
    question: dict[str, Any],
    question_id: str,
    course_question: QuestionSpec,
    criterion_ids: list[str],
) -> list[str]:
    criteria = question.get("criteria")
    if not isinstance(criteria, list) or not criteria:
        return [f"{question_id} criteria must be a non-empty list"]
    findings: list[str] = []
    points_total = 0.0
    required = {"id", "points", "award_condition", "withhold_condition"}
    for index, criterion in enumerate(criteria):
        label = f"{question_id} criteria[{index}]"
        if not isinstance(criterion, dict) or set(criterion) != required:
            findings.append(f"{label} must contain exactly id, points, award_condition, withhold_condition")
            continue
        criterion_id = criterion["id"]
        if not isinstance(criterion_id, str) or not criterion_id.strip():
            findings.append(f"{label} id must be non-blank text")
        else:
            criterion_ids.append(criterion_id)
        points = criterion["points"]
        if not _allows_score(course_question, points) or not _is_number(points) or points <= 0:
            findings.append(f"{label} points must be positive and use the score step")
        else:
            points_total += float(points)
        for field in ("award_condition", "withhold_condition"):
            value = criterion[field]
            if not isinstance(value, str) or not value.strip():
                findings.append(f"{label} {field} must be non-blank text")
            elif AMBIGUOUS_RUBRIC_LANGUAGE.search(value):
                findings.append(f"{label} {field} must avoid unresolved discretionary language")
    if abs(points_total - course_question.max_score) > 1e-9:
        findings.append(
            f"{question_id} criterion points must total {_score_label(course_question.max_score)}"
        )
    return findings


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

    valid_bounds: dict[str, tuple[float, float]] = {}
    for band in REQUIRED_BANDS:
        if band not in bands:
            continue
        bounds = bands[band]
        if not isinstance(bounds, dict):
            findings.append(f"{question_id} {band} band must be an object")
            continue
        minimum = bounds.get("minimum")
        maximum = bounds.get("maximum")
        boundaries_valid = _allows_score(
            course_question, minimum
        ) and _allows_score(course_question, maximum)
        if not boundaries_valid:
            findings.append(
                f"{question_id} {band} band bounds must be within 0..{_score_label(course_question.max_score)} and use the {_score_label(course_question.score_step)} score step"
            )
        if _is_number(minimum) and _is_number(maximum) and minimum > maximum:
            findings.append(f"{question_id} {band} band minimum must not exceed maximum")
        elif boundaries_valid:
            valid_bounds[band] = (float(minimum), float(maximum))

    no_credit = bands.get("no_credit")
    if isinstance(no_credit, dict) and _is_number(no_credit.get("minimum")):
        if not _same_number(no_credit["minimum"], 0.0):
            findings.append(f"{question_id} no_credit band minimum must be 0.0")
    full = bands.get("full")
    if isinstance(full, dict) and _is_number(full.get("maximum")):
        if not _same_number(full["maximum"], course_question.max_score):
            findings.append(
                f"{question_id} full band maximum must be {_score_label(course_question.max_score)}"
            )

    for lower_band, upper_band in zip(
        BAND_COVERAGE_ORDER[:-1],
        BAND_COVERAGE_ORDER[1:],
        strict=True,
    ):
        if lower_band not in valid_bounds or upper_band not in valid_bounds:
            continue
        expected_minimum = _as_decimal(valid_bounds[lower_band][1]) + _as_decimal(
            course_question.score_step
        )
        actual_minimum = _as_decimal(valid_bounds[upper_band][0])
        if actual_minimum != expected_minimum:
            findings.append(
                f"{question_id} {lower_band} -> {upper_band} bands must be ordered, non-overlapping, and contiguous by the {_score_label(course_question.score_step)} score step"
            )
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
    for index, material_error in enumerate(material_errors):
        label = f"{question_id} material_errors[{index}]"
        if not isinstance(material_error, dict):
            findings.append(f"{label} must be an object")
            continue
        if "cap" not in material_error:
            findings.append(f"{label} must define cap")
            continue
        cap = material_error["cap"]
        if not _is_number(cap):
            findings.append(f"{label} cap must be numeric")
            continue
        if not course_question.allows_score(float(cap)):
            findings.append(
                f"{label} cap must be within 0..{_score_label(course_question.max_score)} and use the {_score_label(course_question.score_step)} score step"
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


def _as_decimal(value: float) -> Decimal:
    return Decimal(str(value))
