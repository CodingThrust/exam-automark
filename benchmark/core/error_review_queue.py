"""Private, first-pass root-cause review queues for grading error books.

The error-book diagnosis format is deliberately an all-cases, post-review
artifact.  This module is for the earlier and narrower task of selecting a
small, representative set of development-split disagreements for a human to
inspect locally.  Its records remain private and are never suitable for a
public report or for ``diagnoses.private.json``.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from statistics import fmean
from typing import Any, Iterable, Mapping, Sequence

from .error_audit import MECHANISM_DEFINITIONS, PRIMARY_CAUSE_MECHANISMS
from .error_book import DEVELOPMENT_SPLITS, validate_private_output_path


QUEUE_RECORD_TYPE = "root_cause_review_queue_private"
QUEUE_SCHEMA_VERSION = 1
HUMAN_REVIEW_RECORD_TYPE = "human_root_cause_review_private"
HUMAN_REVIEW_SCHEMA_VERSION = 1
_CONDITION_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")
_QUESTION_ID_PATTERN = re.compile(r"^Q[0-9]+(?:[A-Za-z0-9_-]+)?$")
_STUDENT_ID_PATTERN = re.compile(r"^S[0-9]{3,}$")
_PAGE_SUFFIX_PATTERN = re.compile(r"^p[0-9]{2,}$")
_IMAGE_PATH_PATTERN = re.compile(
    r"^anonymized_pages/(S[0-9]{3,})/(S[0-9]{3,})-(p[0-9]{2,})\.png$"
)
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_DIRECT_IMAGE_INPUT_MODES = frozenset(
    {"image", "image-only", "multimodal", "direct-image", "direct-multimodal"}
)
_TEXT_INPUT_MODES = frozenset({"text", "text-only", "transcript", "transcript-only"})

REVIEW_STATUSES = frozenset({"reviewed", "needs_more_evidence"})
MAX_REVIEWER_LENGTH = 120
MAX_RATIONALE_LENGTH = 4_000


@dataclass(frozen=True)
class _Source:
    condition_id: str
    path: Path
    sha256: str
    payload: dict[str, Any]

    @property
    def provenance(self) -> Mapping[str, Any]:
        value = self.payload["provenance"]
        assert isinstance(value, Mapping)
        return value


@dataclass(frozen=True)
class _Candidate:
    anonymous_student_id: str
    question_id: str
    gold_score: float
    cases_by_condition: Mapping[str, Mapping[str, Any] | None]
    source_order: tuple[str, ...]

    @property
    def error_condition_count(self) -> int:
        return sum(case is not None for case in self.cases_by_condition.values())

    @property
    def all_conditions_error(self) -> bool:
        return self.error_condition_count == len(self.source_order)

    @property
    def mean_absolute_error(self) -> float:
        values = [
            float(case["absolute_error"])
            for case in self.cases_by_condition.values()
            if case is not None
        ]
        return round(fmean(values), 6) if values else 0.0

    @property
    def max_absolute_error(self) -> float:
        values = [
            float(case["absolute_error"])
            for case in self.cases_by_condition.values()
            if case is not None
        ]
        return round(max(values), 6) if values else 0.0

    def predicted_score(self, condition_id: str) -> float:
        case = self.cases_by_condition[condition_id]
        return self.gold_score if case is None else float(case["predicted_score"])

    def score_delta(self, first: str, second: str) -> float:
        return round(
            abs(self.predicted_score(first) - self.predicted_score(second)), 6
        )


@dataclass(frozen=True)
class _ComparisonContract:
    """Named comparison axes that were proven from source provenance."""

    route_pair: tuple[str, str] | None
    same_text_provider_pair: tuple[str, str] | None

    def as_dict(self) -> dict[str, Any]:
        return {
            "codex_m1_vs_codex_g1_route_pair": list(self.route_pair)
            if self.route_pair is not None
            else None,
            "codex_g1_vs_deepseek_g1_same_text_pair": list(
                self.same_text_provider_pair
            )
            if self.same_text_provider_pair is not None
            else None,
        }


def load_page_suffix_by_question(course_path: Path) -> dict[str, str]:
    """Read the tracked course layout and map each question to one page suffix."""

    payload = _read_json_object(course_path, "course specification")
    questions = payload.get("questions")
    page_mapping = payload.get("page_mapping")
    if not isinstance(questions, list) or not isinstance(page_mapping, Mapping):
        raise ValueError("course specification must declare questions and page_mapping")

    expected_questions: set[str] = set()
    for question in questions:
        if not isinstance(question, Mapping) or not isinstance(question.get("id"), str):
            raise ValueError("course questions must each have a text id")
        question_id = question["id"]
        if not _QUESTION_ID_PATTERN.fullmatch(question_id) or question_id in expected_questions:
            raise ValueError("course question IDs must be unique Q-number identifiers")
        expected_questions.add(question_id)

    result: dict[str, str] = {}
    for page_suffix, entry in page_mapping.items():
        # Course specifications may document why this mapping is approved in
        # a top-level ``basis`` field.  It is metadata, not a rendered page.
        if page_suffix == "basis":
            if not isinstance(entry, str) or not entry.strip():
                raise ValueError("course page_mapping basis must be non-empty text")
            continue
        if not isinstance(page_suffix, str) or not _PAGE_SUFFIX_PATTERN.fullmatch(page_suffix):
            raise ValueError("course page_mapping keys must use pNN page suffixes")
        if not isinstance(entry, Mapping) or not isinstance(entry.get("question_ids"), list):
            raise ValueError("each course page_mapping entry needs a question_ids list")
        for question_id in entry["question_ids"]:
            if not isinstance(question_id, str) or question_id not in expected_questions:
                raise ValueError("course page_mapping contains an unknown question ID")
            if question_id in result:
                raise ValueError("course page_mapping assigns a question to multiple pages")
            result[question_id] = page_suffix
    if set(result) != expected_questions:
        raise ValueError("course page_mapping must cover every course question exactly once")
    return result


def load_rubric_review_context(
    rubric_path: Path, *, question_ids: Sequence[str]
) -> dict[str, Any]:
    """Load a hash-bound, question-scoped rubric context for local review."""

    selected_questions = _normalize_questions(question_ids)
    payload = _read_json_object(rubric_path, "frozen review rubric")
    course_id = payload.get("course_id")
    assessment_id = payload.get("assessment_id")
    raw_questions = payload.get("questions")
    if (
        not isinstance(course_id, str)
        or not course_id.strip()
        or not isinstance(assessment_id, str)
        or not assessment_id.strip()
        or not isinstance(raw_questions, list)
    ):
        raise ValueError("frozen review rubric lacks course_id, assessment_id, or questions")
    by_question: dict[str, Mapping[str, Any]] = {}
    for question in raw_questions:
        if not isinstance(question, Mapping) or not isinstance(question.get("id"), str):
            raise ValueError("frozen review rubric has a malformed question")
        question_id = question["id"]
        if question_id in by_question:
            raise ValueError("frozen review rubric has duplicate question IDs")
        by_question[question_id] = question

    context_questions: list[dict[str, Any]] = []
    for question_id in selected_questions:
        question = by_question.get(question_id)
        if question is None:
            raise ValueError(f"frozen review rubric lacks requested {question_id}")
        context_questions.append(
            {
                "question_id": question_id,
                "expected": question.get("expected"),
                "full_credit_rule": question.get("full_credit_rule"),
                "rubric": question.get("rubric"),
                "material_errors": question.get("material_errors", []),
                "score_bands": question.get("score_bands"),
                "scoring_elements": question.get("scoring_elements", []),
            }
        )
    return {
        "record_type": "frozen_rubric_review_context",
        "schema_version": 1,
        "course_id": course_id,
        "assessment_id": assessment_id,
        "rubric_sha256": _sha256_file(rubric_path),
        "questions": context_questions,
    }


def build_root_cause_review_queue(
    *,
    sources: Mapping[str, Path],
    question_ids: Sequence[str],
    page_suffix_by_question: Mapping[str, str],
    rubric_context: Mapping[str, Any],
    items_per_question: int = 2,
) -> dict[str, Any]:
    """Build, without writing, a private representative-case review queue.

    ``sources`` name condition-specific private error books.  Every source
    must come from the same development benchmark contract, while input mode
    and provider may differ.  Missing cases mean that condition matched gold:
    private error books record every and only score disagreement.
    """

    selected_questions = _normalize_questions(question_ids)
    if items_per_question < 1 or items_per_question > 8:
        raise ValueError("items_per_question must be between 1 and 8")
    if len(sources) < 2:
        raise ValueError("at least two condition-specific private error books are required")

    source_records = _load_sources(sources)
    common, comparison_contract = _validate_sources(source_records)
    _validate_rubric_review_context(
        rubric_context,
        common=common,
        question_ids=selected_questions,
    )
    page_suffixes = _validate_page_mapping(selected_questions, page_suffix_by_question)
    candidates_by_question = _collect_candidates(source_records, selected_questions)

    provider_focus_question = _provider_focus_question(
        candidates_by_question,
        comparison_contract=comparison_contract,
    )
    items: list[dict[str, Any]] = []
    for question_id in selected_questions:
        candidates = candidates_by_question.get(question_id, ())
        if not candidates:
            raise ValueError(
                f"no score-disagreement cases are available for requested {question_id}"
            )
        selections = _select_for_question(
            candidates,
            source_order=tuple(source.condition_id for source in source_records),
            count=items_per_question,
            comparison_contract=comparison_contract,
            prefer_same_text_provider=(question_id == provider_focus_question),
        )
        if len(selections) < items_per_question:
            raise ValueError(
                f"only {len(selections)} unique disagreement case(s) are available for {question_id}"
            )
        for ordinal, (candidate, reason) in enumerate(selections, start=1):
            item_id = f"ROOT-CAUSE-{question_id}-{ordinal:02d}"
            items.append(
                _queue_item(
                    item_id=item_id,
                    candidate=candidate,
                    page_suffix=page_suffixes[question_id],
                    sources=source_records,
                    selection_reason=reason,
                )
            )

    source_bindings = [_source_binding(source) for source in source_records]
    queue_seed = {
        "questions": list(selected_questions),
        "items_per_question": items_per_question,
        "source_books": source_bindings,
        "items": items,
    }
    queue_id = "RCQ-" + _sha256_json(queue_seed)[:16]
    payload = {
        "record_type": QUEUE_RECORD_TYPE,
        "schema_version": QUEUE_SCHEMA_VERSION,
        "queue_id": queue_id,
        "scope": {
            "split": "development",
            "contains_heldout_or_test_data": False,
            "private_only": True,
            "not_a_final_diagnosis": True,
            "selection_scope": "representative first-pass root-cause review",
            "selection_scope_zh": "代表性首轮根因人工复核，不是全量最终诊断",
        },
        "provenance": {
            **common,
            "source_books": source_bindings,
            "comparison_contract": comparison_contract.as_dict(),
            "selection_question_ids": list(selected_questions),
            "items_per_question": items_per_question,
        },
        "review_guidance": {
            "zh": [
                "先核对原图中的可见证据与人工 gold；不要把模型的关键词或理由直接当事实。",
                "三路都错时，优先区分评分规则/证据判断与 rubric-gold 合同问题；仅文本路线异常时，再重点检查转录表示。",
                "无法在当前证据下判定时，选择“需要更多证据”，不要猜测根因。",
                "本队列只用于决定下一轮 skill 假设；不能代替全量 diagnoses.private.json。",
            ],
            "en": [
                "Inspect visible source-image evidence and human gold before trusting a model rationale.",
                "When all routes fail, separate evidence/rule decisions from rubric-gold contract issues; investigate representation when only text-route results diverge.",
                "Choose needs-more-evidence instead of guessing when the current material is insufficient.",
                "This queue informs a next skill hypothesis only; it is not a complete diagnoses.private.json.",
            ],
        },
        "review_context": dict(rubric_context),
        "review_form": _review_form(),
        "items": items,
    }
    validate_root_cause_review_queue(payload)
    return payload


def write_root_cause_review_queue(
    *,
    output_path: Path,
    queue: Mapping[str, Any],
    private_root: Path,
) -> str:
    """Atomically write a private queue and return its content SHA-256.

    An existing queue is accepted only when it is byte-for-byte represented by
    the same canonical JSON payload.  A divergent existing private queue is
    refused so that in-progress human review is never silently replaced.
    """

    validate_root_cause_review_queue(queue)
    validate_private_output_under_root(output_path, private_root=private_root)
    serialized = _canonical_json(queue)
    if output_path.exists():
        existing = _read_json_object(output_path, "existing root-cause review queue")
        if _canonical_json(existing) != serialized:
            raise ValueError(
                "refusing to replace a divergent existing root-cause review queue; "
                "choose a new versioned private output path"
            )
        return hashlib.sha256(serialized).hexdigest()
    _atomic_write(output_path, serialized)
    return hashlib.sha256(serialized).hexdigest()


def validate_root_cause_review_queue(payload: Mapping[str, Any]) -> None:
    """Reject a malformed queue before a local reviewer may load it."""

    if payload.get("record_type") != QUEUE_RECORD_TYPE:
        raise ValueError("unexpected root-cause review queue record_type")
    if payload.get("schema_version") != QUEUE_SCHEMA_VERSION:
        raise ValueError("unsupported root-cause review queue schema_version")
    queue_id = payload.get("queue_id")
    if not isinstance(queue_id, str) or not queue_id.startswith("RCQ-"):
        raise ValueError("root-cause review queue must have an RCQ queue_id")
    scope = payload.get("scope")
    if not isinstance(scope, Mapping) or scope.get("split") not in DEVELOPMENT_SPLITS:
        raise ValueError("root-cause review queue is limited to an explicit development split")
    if scope.get("contains_heldout_or_test_data") is not False:
        raise ValueError("root-cause review queue must exclude held-out or test data")
    if scope.get("private_only") is not True or scope.get("not_a_final_diagnosis") is not True:
        raise ValueError("root-cause review queue must remain a private non-final artifact")

    provenance = payload.get("provenance")
    if not isinstance(provenance, Mapping):
        raise ValueError("root-cause review queue needs provenance")
    for field in (
        "course_id",
        "assessment_id",
        "gold_sha256",
        "data_snapshot_sha256",
        "prompt_sha256",
        "rubric_sha256",
    ):
        value = provenance.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"root-cause review queue has no shared {field}")
    if not _SHA256_PATTERN.fullmatch(str(provenance["gold_sha256"])):
        raise ValueError("root-cause review queue gold_sha256 is invalid")
    for field in ("data_snapshot_sha256", "prompt_sha256", "rubric_sha256"):
        if not _SHA256_PATTERN.fullmatch(str(provenance[field])):
            raise ValueError(f"root-cause review queue {field} is invalid")
    selected_questions = provenance.get("selection_question_ids")
    if not isinstance(selected_questions, list):
        raise ValueError("root-cause review queue needs selection_question_ids")
    normalized_questions = _normalize_questions(selected_questions)
    review_context = payload.get("review_context")
    if not isinstance(review_context, Mapping):
        raise ValueError("root-cause review queue needs frozen rubric review context")
    _validate_rubric_review_context(
        review_context,
        common={
            field: str(provenance[field])
            for field in ("course_id", "assessment_id", "rubric_sha256")
        },
        question_ids=normalized_questions,
    )

    sources = provenance.get("source_books")
    if not isinstance(sources, list) or len(sources) < 2:
        raise ValueError("root-cause review queue needs at least two source books")
    source_ids: set[str] = set()
    for source in sources:
        if not isinstance(source, Mapping):
            raise ValueError("root-cause review queue source book must be an object")
        condition_id = source.get("condition_id")
        if not isinstance(condition_id, str) or not _CONDITION_ID_PATTERN.fullmatch(condition_id):
            raise ValueError("invalid root-cause review queue condition_id")
        if condition_id in source_ids:
            raise ValueError("duplicate root-cause review queue condition_id")
        source_ids.add(condition_id)
        for field in ("private_error_book_sha256", "run_id"):
            value = source.get(field)
            if not isinstance(value, str) or not value:
                raise ValueError(f"source book lacks {field}")
        if not _SHA256_PATTERN.fullmatch(str(source["private_error_book_sha256"])):
            raise ValueError("source book private_error_book_sha256 is invalid")
    comparison_contract = provenance.get("comparison_contract")
    if not isinstance(comparison_contract, Mapping):
        raise ValueError("root-cause review queue needs a comparison contract")
    _validate_serialized_comparison_contract(comparison_contract, source_ids)

    items = payload.get("items")
    if not isinstance(items, list) or not items:
        raise ValueError("root-cause review queue needs at least one item")
    item_ids: set[str] = set()
    for item in items:
        _validate_queue_item(item, source_ids=source_ids)
        item_id = str(item["queue_item_id"])
        if item_id in item_ids:
            raise ValueError("duplicate root-cause review queue item ID")
        item_ids.add(item_id)


def _validate_serialized_comparison_contract(
    contract: Mapping[str, Any], source_ids: set[str]
) -> None:
    expected = {
        "codex_m1_vs_codex_g1_route_pair": ("codex_m1", "codex_g1"),
        "codex_g1_vs_deepseek_g1_same_text_pair": ("codex_g1", "deepseek_g1"),
    }
    for field, allowed_pair in expected.items():
        value = contract.get(field)
        if value is None:
            continue
        if (
            not isinstance(value, list)
            or tuple(value) != allowed_pair
            or not set(value).issubset(source_ids)
        ):
            raise ValueError(f"root-cause review queue has invalid {field}")


def empty_human_review_document(*, queue_path: Path, queue: Mapping[str, Any]) -> dict[str, Any]:
    """Return the empty, bound private document used by the local reviewer."""

    validate_root_cause_review_queue(queue)
    return {
        "record_type": HUMAN_REVIEW_RECORD_TYPE,
        "schema_version": HUMAN_REVIEW_SCHEMA_VERSION,
        "queue_id": queue["queue_id"],
        "queue_sha256": _sha256_file(queue_path),
        "reviews": [],
    }


def validate_human_review_document(
    *,
    document: Mapping[str, Any],
    queue_path: Path,
    queue: Mapping[str, Any],
) -> None:
    """Validate a private review document against one exact queue file."""

    validate_root_cause_review_queue(queue)
    if document.get("record_type") != HUMAN_REVIEW_RECORD_TYPE:
        raise ValueError("unexpected human root-cause review record_type")
    if document.get("schema_version") != HUMAN_REVIEW_SCHEMA_VERSION:
        raise ValueError("unsupported human root-cause review schema_version")
    if document.get("queue_id") != queue.get("queue_id"):
        raise ValueError("human review document is bound to another queue_id")
    if document.get("queue_sha256") != _sha256_file(queue_path):
        raise ValueError("human review document is bound to another queue file")
    reviews = document.get("reviews")
    if not isinstance(reviews, list):
        raise ValueError("human review document reviews must be a list")
    valid_items = {
        str(item["queue_item_id"])
        for item in queue["items"]
        if isinstance(item, Mapping)
    }
    seen: set[str] = set()
    for review in reviews:
        _validate_human_review(review, valid_item_ids=valid_items)
        item_id = str(review["queue_item_id"])
        if item_id in seen:
            raise ValueError("human review document contains duplicate item reviews")
        seen.add(item_id)


def update_human_review_document(
    *,
    document: Mapping[str, Any],
    queue_path: Path,
    queue: Mapping[str, Any],
    review: Mapping[str, Any],
) -> dict[str, Any]:
    """Replace one item review after validating its queue binding and taxonomy."""

    validate_human_review_document(document=document, queue_path=queue_path, queue=queue)
    valid_items = {
        str(item["queue_item_id"])
        for item in queue["items"]
        if isinstance(item, Mapping)
    }
    _validate_human_review(review, valid_item_ids=valid_items)
    review_id = str(review["queue_item_id"])
    retained = [
        dict(entry)
        for entry in document["reviews"]
        if isinstance(entry, Mapping) and entry.get("queue_item_id") != review_id
    ]
    retained.append(dict(review))
    retained.sort(key=lambda entry: str(entry["queue_item_id"]))
    result = dict(document)
    result["reviews"] = retained
    validate_human_review_document(document=result, queue_path=queue_path, queue=queue)
    return result


def write_human_review_document(
    *, output_path: Path, document: Mapping[str, Any], private_root: Path
) -> str:
    """Atomically write an already-validated private human review document."""

    validate_private_output_under_root(output_path, private_root=private_root)
    serialized = _canonical_json(document)
    _atomic_write(output_path, serialized)
    return hashlib.sha256(serialized).hexdigest()


def validate_private_output_under_root(output_path: Path, *, private_root: Path) -> None:
    """Require a versioned output below an explicit private, ignored data root."""

    root = private_root.resolve()
    if not root.is_dir() or root.is_symlink():
        raise ValueError(f"private output root must be a regular directory: {private_root}")
    output = output_path.resolve()
    try:
        output.relative_to(root)
    except ValueError as error:
        raise ValueError(
            f"private root-cause review output must stay under the designated private root: {root}"
        ) from error
    validate_private_output_path(output)


def _normalize_questions(question_ids: Sequence[str]) -> tuple[str, ...]:
    normalized: list[str] = []
    seen: set[str] = set()
    for value in question_ids:
        question_id = value.strip() if isinstance(value, str) else ""
        if not _QUESTION_ID_PATTERN.fullmatch(question_id):
            raise ValueError("question_ids must be Q-number identifiers")
        if question_id in seen:
            raise ValueError("question_ids must not contain duplicates")
        seen.add(question_id)
        normalized.append(question_id)
    if not normalized:
        raise ValueError("at least one question_id is required")
    return tuple(normalized)


def _load_sources(sources: Mapping[str, Path]) -> tuple[_Source, ...]:
    result: list[_Source] = []
    for raw_condition_id, raw_path in sources.items():
        condition_id = raw_condition_id.strip() if isinstance(raw_condition_id, str) else ""
        if not _CONDITION_ID_PATTERN.fullmatch(condition_id):
            raise ValueError("source condition IDs must use lowercase letters, digits, _ or -")
        path = Path(raw_path).resolve()
        payload = _read_json_object(path, f"{condition_id} private error book")
        result.append(
            _Source(
                condition_id=condition_id,
                path=path,
                sha256=_sha256_file(path),
                payload=payload,
            )
        )
    if len({source.condition_id for source in result}) != len(result):
        raise ValueError("source condition IDs must be unique")
    return tuple(result)


def _validate_sources(
    sources: Sequence[_Source],
) -> tuple[dict[str, str], _ComparisonContract]:
    common: dict[str, str] = {}
    common_population: tuple[int, int] | None = None
    fields = (
        "course_id",
        "assessment_id",
        "gold_sha256",
        "data_snapshot_sha256",
        "prompt_sha256",
        "rubric_sha256",
    )
    for source in sources:
        payload = source.payload
        if payload.get("record_type") != "grading_error_book_private":
            raise ValueError(f"{source.condition_id} is not a private grading error book")
        scope = payload.get("scope")
        technical = payload.get("technical_failures")
        population = payload.get("population")
        provenance = payload.get("provenance")
        cases = payload.get("cases")
        if not isinstance(scope, Mapping) or scope.get("split") not in DEVELOPMENT_SPLITS:
            raise ValueError(f"{source.condition_id} error book is not development split")
        if scope.get("selection_rule") != (
            "all student-question pairs with predicted_score != gold_score"
        ):
            raise ValueError(
                f"{source.condition_id} error book does not prove complete disagreement coverage"
            )
        if not isinstance(technical, Mapping) or technical.get("included_as_grading_cases") is not False:
            raise ValueError(
                f"{source.condition_id} error book does not explicitly exclude technical failures"
            )
        if not isinstance(provenance, Mapping) or not isinstance(cases, list):
            raise ValueError(f"{source.condition_id} error book lacks provenance or cases")
        if not isinstance(population, Mapping):
            raise ValueError(f"{source.condition_id} error book lacks population coverage")
        students = population.get("students")
        total_pairs = population.get("student_question_pairs")
        error_pairs = population.get("error_pairs")
        if (
            type(students) is not int
            or students <= 0
            or type(total_pairs) is not int
            or total_pairs <= 0
            or type(error_pairs) is not int
            or error_pairs < 0
            or error_pairs > total_pairs
            or error_pairs != len(cases)
        ):
            raise ValueError(
                f"{source.condition_id} error book population does not match complete cases"
            )
        current_population = (students, total_pairs)
        if common_population is None:
            common_population = current_population
        elif common_population != current_population:
            raise ValueError(
                "source error books disagree on development population; "
                "do not infer an absent case is exact"
            )
        for field in fields:
            value = provenance.get(field)
            if not isinstance(value, str) or not value:
                raise ValueError(f"{source.condition_id} error book lacks {field}")
            if field.endswith("sha256") and not _SHA256_PATTERN.fullmatch(value):
                raise ValueError(f"{source.condition_id} error book has invalid {field}")
            previous = common.get(field)
            if previous is None:
                common[field] = value
            elif previous != value:
                raise ValueError(
                    f"source error books disagree on {field}; do not combine them into one review queue"
                )
        _validate_private_cases(cases, source.condition_id)
    return common, _comparison_contract(sources)


def _validate_private_cases(cases: Sequence[Any], condition_id: str) -> None:
    case_ids: set[str] = set()
    seen_pairs: set[tuple[str, str]] = set()
    for case in cases:
        if not isinstance(case, Mapping):
            raise ValueError(f"{condition_id} error book has a non-object case")
        case_id = case.get("case_id")
        student_id = case.get("anonymous_student_id")
        question_id = case.get("question_id")
        if not isinstance(case_id, str) or not case_id or case_id in case_ids:
            raise ValueError(f"{condition_id} error book case IDs must be unique")
        if not isinstance(student_id, str) or not _STUDENT_ID_PATTERN.fullmatch(student_id):
            raise ValueError(f"{condition_id} error book has an invalid anonymous student ID")
        if not isinstance(question_id, str) or not _QUESTION_ID_PATTERN.fullmatch(question_id):
            raise ValueError(f"{condition_id} error book has an invalid question ID")
        pair = (student_id, question_id)
        if pair in seen_pairs:
            raise ValueError(f"{condition_id} error book has duplicate student-question case")
        case_ids.add(case_id)
        seen_pairs.add(pair)
        for field in ("gold_score", "predicted_score", "absolute_error"):
            value = case.get(field)
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                raise ValueError(f"{condition_id} case {case_id} has non-numeric {field}")
        if float(case["absolute_error"]) <= 0:
            raise ValueError(f"{condition_id} case {case_id} is not a score disagreement")


def _validate_page_mapping(
    question_ids: Sequence[str], page_suffix_by_question: Mapping[str, str]
) -> dict[str, str]:
    result: dict[str, str] = {}
    for question_id in question_ids:
        page_suffix = page_suffix_by_question.get(question_id)
        if not isinstance(page_suffix, str) or not _PAGE_SUFFIX_PATTERN.fullmatch(page_suffix):
            raise ValueError(f"no valid scoped page suffix is declared for {question_id}")
        result[question_id] = page_suffix
    return result


def _validate_rubric_review_context(
    context: Mapping[str, Any],
    *,
    common: Mapping[str, str],
    question_ids: Sequence[str],
) -> None:
    if context.get("record_type") != "frozen_rubric_review_context":
        raise ValueError("root-cause review requires a frozen rubric review context")
    if context.get("schema_version") != 1:
        raise ValueError("unsupported frozen rubric review context schema")
    for field in ("course_id", "assessment_id", "rubric_sha256"):
        if context.get(field) != common[field]:
            raise ValueError(
                f"frozen rubric review context does not match source {field}"
            )
    questions = context.get("questions")
    if not isinstance(questions, list):
        raise ValueError("frozen rubric review context needs question entries")
    question_ids_in_context: list[str] = []
    for question in questions:
        if not isinstance(question, Mapping) or not isinstance(question.get("question_id"), str):
            raise ValueError("frozen rubric review context has a malformed question")
        question_id = question["question_id"]
        if not _QUESTION_ID_PATTERN.fullmatch(question_id):
            raise ValueError("frozen rubric review context has an invalid question ID")
        question_ids_in_context.append(question_id)
        if not isinstance(question.get("expected"), str) or not question["expected"].strip():
            raise ValueError("frozen rubric review context must include expected answer guidance")
    if tuple(question_ids_in_context) != tuple(question_ids):
        raise ValueError(
            "frozen rubric review context questions must exactly match the queue selection order"
        )


def _comparison_contract(sources: Sequence[_Source]) -> _ComparisonContract:
    """Validate named route/model comparisons before assigning their labels."""

    by_id = {source.condition_id: source for source in sources}
    route_pair: tuple[str, str] | None = None
    m1 = by_id.get("codex_m1")
    codex_g1 = by_id.get("codex_g1")
    if m1 is not None and codex_g1 is not None:
        m1_mode = _required_input_mode(m1)
        g1_mode = _required_input_mode(codex_g1)
        if m1_mode not in _DIRECT_IMAGE_INPUT_MODES or g1_mode not in _TEXT_INPUT_MODES:
            raise ValueError(
                "codex_m1/codex_g1 route comparison requires direct-image and text-only input modes"
            )
        if (
            m1.provenance.get("provider") != codex_g1.provenance.get("provider")
            or m1.provenance.get("model") != codex_g1.provenance.get("model")
        ):
            raise ValueError(
                "codex_m1/codex_g1 route comparison requires the same provider and model"
            )
        route_pair = ("codex_m1", "codex_g1")

    same_text_provider_pair: tuple[str, str] | None = None
    deepseek_g1 = by_id.get("deepseek_g1")
    if codex_g1 is not None and deepseek_g1 is not None:
        codex_mode = _required_input_mode(codex_g1)
        deepseek_mode = _required_input_mode(deepseek_g1)
        codex_text_hash = _required_text_source_hash(codex_g1)
        deepseek_text_hash = _required_text_source_hash(deepseek_g1)
        if codex_mode not in _TEXT_INPUT_MODES or deepseek_mode not in _TEXT_INPUT_MODES:
            raise ValueError(
                "codex_g1/deepseek_g1 model comparison requires text-only input modes"
            )
        if codex_text_hash != deepseek_text_hash:
            raise ValueError(
                "codex_g1/deepseek_g1 model comparison requires the exact same text source"
            )
        if (
            codex_g1.provenance.get("provider") == deepseek_g1.provenance.get("provider")
            and codex_g1.provenance.get("model") == deepseek_g1.provenance.get("model")
        ):
            raise ValueError(
                "codex_g1/deepseek_g1 model comparison needs genuinely different providers or models"
            )
        same_text_provider_pair = ("codex_g1", "deepseek_g1")
    return _ComparisonContract(
        route_pair=route_pair,
        same_text_provider_pair=same_text_provider_pair,
    )


def _required_input_mode(source: _Source) -> str:
    value = source.provenance.get("input_mode")
    mode = value.strip().casefold() if isinstance(value, str) else ""
    if not mode:
        raise ValueError(f"{source.condition_id} error book lacks input_mode")
    return mode


def _required_text_source_hash(source: _Source) -> str:
    value = source.provenance.get("text_source_sha256")
    if not isinstance(value, str) or not _SHA256_PATTERN.fullmatch(value):
        raise ValueError(f"{source.condition_id} error book lacks a valid text_source_sha256")
    return value


def _provider_focus_question(
    candidates_by_question: Mapping[str, Sequence[_Candidate]],
    *,
    comparison_contract: _ComparisonContract,
) -> str | None:
    """Reserve one of the fixed-size sample slots for same-text model contrast."""

    pair = comparison_contract.same_text_provider_pair
    if pair is None:
        return None
    candidates = [
        candidate
        for question_candidates in candidates_by_question.values()
        for candidate in question_candidates
    ]
    if not candidates:
        return None
    best = min(
        candidates,
        key=lambda candidate: (
            -candidate.score_delta(*pair),
            -candidate.mean_absolute_error,
            _question_sort_key(candidate.question_id),
            candidate.anonymous_student_id.casefold(),
            candidate.anonymous_student_id,
        ),
    )
    return best.question_id if best.score_delta(*pair) > 0 else None


def _question_sort_key(question_id: str) -> tuple[int, str]:
    match = re.fullmatch(r"Q([0-9]+)(.*)", question_id, re.IGNORECASE)
    if match:
        return (int(match.group(1)), match.group(2))
    return (10_000, question_id)


def _collect_candidates(
    sources: Sequence[_Source], question_ids: Sequence[str]
) -> dict[str, tuple[_Candidate, ...]]:
    requested = set(question_ids)
    by_pair: dict[tuple[str, str], dict[str, Mapping[str, Any]]] = defaultdict(dict)
    for source in sources:
        for raw_case in source.payload["cases"]:
            assert isinstance(raw_case, Mapping)
            question_id = str(raw_case["question_id"])
            if question_id not in requested:
                continue
            key = (str(raw_case["anonymous_student_id"]), question_id)
            by_pair[key][source.condition_id] = raw_case

    grouped: dict[str, list[_Candidate]] = defaultdict(list)
    source_order = tuple(source.condition_id for source in sources)
    for (student_id, question_id), cases in by_pair.items():
        golds = {float(case["gold_score"]) for case in cases.values()}
        if len(golds) != 1:
            raise ValueError(
                f"source error books disagree on human gold for one anonymous {question_id} case"
            )
        grouped[question_id].append(
            _Candidate(
                anonymous_student_id=student_id,
                question_id=question_id,
                gold_score=golds.pop(),
                cases_by_condition={
                    condition_id: cases.get(condition_id) for condition_id in source_order
                },
                source_order=source_order,
            )
        )
    return {
        question_id: tuple(
            sorted(
                candidates,
                key=lambda candidate: (
                    candidate.anonymous_student_id.casefold(),
                    candidate.anonymous_student_id,
                ),
            )
        )
        for question_id, candidates in grouped.items()
    }


def _select_for_question(
    candidates: Sequence[_Candidate],
    *,
    source_order: tuple[str, ...],
    count: int,
    comparison_contract: _ComparisonContract,
    prefer_same_text_provider: bool,
) -> list[tuple[_Candidate, dict[str, str]]]:
    """Choose diverse, deterministic cases without inventing a comparison axis."""

    generic_pair = (source_order[0], source_order[1])
    route_pair = comparison_contract.route_pair
    route_or_generic_pair = route_pair or generic_pair
    provider_pair = comparison_contract.same_text_provider_pair
    by_shared = _rank_candidates(
        (candidate for candidate in candidates if candidate.all_conditions_error)
    )
    by_route_or_generic = _rank_by_delta(candidates, route_or_generic_pair)
    by_provider = (
        _rank_by_delta(candidates, provider_pair) if provider_pair is not None else ()
    )
    by_magnitude = _rank_candidates(candidates)

    shared_reason = {
        "code": "shared_failure_highest_average_error",
        "zh": "优先覆盖全部条件共同出错、平均绝对误差最大的案例。",
        "en": "Covers the shared cross-condition failure with the largest average absolute error.",
    }
    if route_pair is not None:
        route_reason = {
            "code": "largest_route_score_delta",
            "zh": f"优先覆盖 {route_pair[0]} 与 {route_pair[1]} 分差最大的已验证路线分歧案例。",
            "en": f"Covers the largest provenance-validated route score difference between {route_pair[0]} and {route_pair[1]}.",
        }
    else:
        route_reason = {
            "code": "largest_condition_score_delta",
            "zh": f"覆盖 {generic_pair[0]} 与 {generic_pair[1]} 分差最大的条件分歧；未把它解释为路线差异。",
            "en": f"Covers the largest score difference between {generic_pair[0]} and {generic_pair[1]} without assigning a route interpretation.",
        }
    provider_reason = {
        "code": "largest_same_text_model_delta",
        "zh": f"覆盖 {provider_pair[0]} 与 {provider_pair[1]} 在同一文本输入上的最大模型分歧。",
        "en": f"Covers the largest same-text model difference between {provider_pair[0]} and {provider_pair[1]}.",
    } if provider_pair is not None else None
    magnitude_reason = {
        "code": "highest_remaining_average_error",
        "zh": "补充覆盖尚未入选的平均绝对误差最大案例。",
        "en": "Adds the remaining case with the largest average absolute error.",
    }

    strategies: list[tuple[Sequence[_Candidate], dict[str, str]]] = []
    if by_shared:
        strategies.append((by_shared, shared_reason))
    if prefer_same_text_provider and _has_positive_delta(by_provider, provider_pair):
        assert provider_reason is not None
        strategies.append((by_provider, provider_reason))
    if _has_positive_delta(by_route_or_generic, route_or_generic_pair):
        strategies.append((by_route_or_generic, route_reason))
    if (
        not prefer_same_text_provider
        and _has_positive_delta(by_provider, provider_pair)
    ):
        assert provider_reason is not None
        strategies.append((by_provider, provider_reason))
    strategies.append((by_magnitude, magnitude_reason))
    selected: list[tuple[_Candidate, dict[str, str]]] = []
    used: set[tuple[str, str]] = set()
    for ranked, reason in strategies:
        for candidate in ranked:
            key = (candidate.anonymous_student_id, candidate.question_id)
            if key in used:
                continue
            selected.append((candidate, reason))
            used.add(key)
            break
        if len(selected) >= count:
            return selected[:count]

    for candidate in by_magnitude:
        key = (candidate.anonymous_student_id, candidate.question_id)
        if key in used:
            continue
        selected.append(
            (
                candidate,
                {
                    "code": "highest_remaining_average_error",
                    "zh": "补充覆盖尚未入选的平均绝对误差最大案例。",
                    "en": "Adds the remaining case with the largest average absolute error.",
                },
            )
        )
        used.add(key)
        if len(selected) >= count:
            break
    return selected


def _rank_candidates(candidates: Iterable[_Candidate]) -> tuple[_Candidate, ...]:
    return tuple(
        sorted(
            candidates,
            key=lambda candidate: (
                -candidate.mean_absolute_error,
                -candidate.max_absolute_error,
                -candidate.error_condition_count,
                candidate.anonymous_student_id.casefold(),
                candidate.anonymous_student_id,
            ),
        )
    )


def _rank_by_delta(
    candidates: Sequence[_Candidate], pair: tuple[str, str]
) -> tuple[_Candidate, ...]:
    return tuple(
        sorted(
            candidates,
            key=lambda candidate: (
                -candidate.score_delta(*pair),
                -candidate.mean_absolute_error,
                -candidate.max_absolute_error,
                candidate.anonymous_student_id.casefold(),
                candidate.anonymous_student_id,
            ),
        )
    )


def _has_positive_delta(
    candidates: Sequence[_Candidate], pair: tuple[str, str] | None
) -> bool:
    return bool(pair and candidates and candidates[0].score_delta(*pair) > 0)


def _queue_item(
    *,
    item_id: str,
    candidate: _Candidate,
    page_suffix: str,
    sources: Sequence[_Source],
    selection_reason: Mapping[str, str],
) -> dict[str, Any]:
    image_path = (
        f"anonymized_pages/{candidate.anonymous_student_id}/"
        f"{candidate.anonymous_student_id}-{page_suffix}.png"
    )
    views = []
    for source in sources:
        case = candidate.cases_by_condition[source.condition_id]
        provenance = source.provenance
        if case is None:
            views.append(
                {
                    "condition_id": source.condition_id,
                    "run_id": provenance["run_id"],
                    "provider": provenance.get("provider"),
                    "model": provenance.get("model"),
                    "input_mode": provenance.get("input_mode"),
                    "error_book_case_id": None,
                    "matches_gold": True,
                    "prediction_source": "inferred_exact_from_complete_error_book",
                    "predicted_score": candidate.gold_score,
                    "absolute_error": 0.0,
                    "confidence": None,
                    "flags": [],
                    "evidence": None,
                    "extracted_evidence": None,
                }
            )
            continue
        views.append(
            {
                "condition_id": source.condition_id,
                "run_id": provenance["run_id"],
                "provider": provenance.get("provider"),
                "model": provenance.get("model"),
                "input_mode": provenance.get("input_mode"),
                "error_book_case_id": case["case_id"],
                "matches_gold": False,
                "prediction_source": "recorded_error_book_case",
                "predicted_score": float(case["predicted_score"]),
                "absolute_error": float(case["absolute_error"]),
                "confidence": case.get("confidence"),
                "flags": list(case.get("flags", [])),
                "evidence": case.get("evidence"),
                "extracted_evidence": case.get("extracted_evidence"),
            }
        )
    source_order = tuple(source.condition_id for source in sources)
    return {
        "queue_item_id": item_id,
        "anonymous_student_id": candidate.anonymous_student_id,
        "question_id": candidate.question_id,
        "gold_score": candidate.gold_score,
        "image": {"page_suffix": page_suffix, "relative_path": image_path},
        "selection": {
            "priority_score": candidate.mean_absolute_error,
            "conditions_with_score_error": candidate.error_condition_count,
            "all_conditions_have_score_error": candidate.all_conditions_error,
            "m1_vs_codex_g1_score_delta": _optional_delta(
                candidate, "codex_m1", "codex_g1"
            ),
            "codex_g1_vs_deepseek_g1_score_delta": _optional_delta(
                candidate, "codex_g1", "deepseek_g1"
            ),
            "reason_code": selection_reason["code"],
            "reason_zh": selection_reason["zh"],
            "reason_en": selection_reason["en"],
        },
        "condition_views": views,
        "review_status": "pending",
    }


def _optional_delta(candidate: _Candidate, first: str, second: str) -> float | None:
    if first not in candidate.source_order or second not in candidate.source_order:
        return None
    return candidate.score_delta(first, second)


def _source_binding(source: _Source) -> dict[str, Any]:
    provenance = source.provenance
    return {
        "condition_id": source.condition_id,
        "private_error_book_sha256": source.sha256,
        "run_id": provenance["run_id"],
        "provider": provenance.get("provider"),
        "model": provenance.get("model"),
        "input_mode": provenance.get("input_mode"),
        "skill_version_id": provenance.get("skill_version_id"),
        "output_set_sha256": provenance.get("output_set_sha256"),
        "text_source_sha256": provenance.get("text_source_sha256"),
    }


def _review_form() -> dict[str, Any]:
    options = []
    for primary_cause, mechanisms in sorted(PRIMARY_CAUSE_MECHANISMS.items()):
        for mechanism_code in sorted(mechanisms):
            definition = MECHANISM_DEFINITIONS[mechanism_code]
            options.append(
                {
                    "primary_cause": primary_cause,
                    "mechanism_code": mechanism_code,
                    "error_layer": definition["error_layer"],
                    "objectivity_level": definition["objectivity_level"],
                    "disposition": definition["skill_update_disposition"],
                    "label_zh": definition["zh"],
                    "label_en": definition["en"],
                }
            )
    return {
        "review_statuses": ["reviewed", "needs_more_evidence"],
        "mechanism_options": options,
        "typical_case_meaning": {
            "zh": "勾选仅表示它有助于说明一类根因；不是泛化或优化已验证的证据。",
            "en": "Checking this means the case explains one suspected mechanism; it is not proof of generalization or a validated optimization.",
        },
    }


def _validate_queue_item(item: Any, *, source_ids: set[str]) -> None:
    if not isinstance(item, Mapping):
        raise ValueError("root-cause review queue item must be an object")
    item_id = item.get("queue_item_id")
    if not isinstance(item_id, str) or not item_id:
        raise ValueError("root-cause review queue item needs an ID")
    student_id = item.get("anonymous_student_id")
    question_id = item.get("question_id")
    if not isinstance(student_id, str) or not _STUDENT_ID_PATTERN.fullmatch(student_id):
        raise ValueError("root-cause review queue item has an invalid anonymous student ID")
    if not isinstance(question_id, str) or not _QUESTION_ID_PATTERN.fullmatch(question_id):
        raise ValueError("root-cause review queue item has an invalid question ID")
    if not isinstance(item.get("gold_score"), (int, float)) or isinstance(item.get("gold_score"), bool):
        raise ValueError("root-cause review queue item needs a numeric gold score")
    image = item.get("image")
    if not isinstance(image, Mapping):
        raise ValueError("root-cause review queue item needs an image binding")
    page_suffix = image.get("page_suffix")
    relative_path = image.get("relative_path")
    if not isinstance(page_suffix, str) or not _PAGE_SUFFIX_PATTERN.fullmatch(page_suffix):
        raise ValueError("root-cause review queue item has invalid page suffix")
    if not isinstance(relative_path, str):
        raise ValueError("root-cause review queue item has invalid image path")
    image_match = _IMAGE_PATH_PATTERN.fullmatch(relative_path)
    if not image_match or image_match.group(1) != student_id or image_match.group(2) != student_id or image_match.group(3) != page_suffix:
        raise ValueError("root-cause review queue image path does not match its anonymous student/page")
    views = item.get("condition_views")
    if not isinstance(views, list) or {view.get("condition_id") for view in views if isinstance(view, Mapping)} != source_ids:
        raise ValueError("root-cause review queue item must cover every source condition once")
    if len(views) != len(source_ids):
        raise ValueError("root-cause review queue item has duplicate condition views")
    for view in views:
        if not isinstance(view, Mapping):
            raise ValueError("root-cause review queue condition view must be an object")
        if not isinstance(view.get("predicted_score"), (int, float)) or isinstance(view.get("predicted_score"), bool):
            raise ValueError("root-cause review queue condition view needs a numeric predicted score")
        if not isinstance(view.get("matches_gold"), bool):
            raise ValueError("root-cause review queue condition view needs matches_gold")


def _validate_human_review(review: Mapping[str, Any], *, valid_item_ids: set[str]) -> None:
    item_id = review.get("queue_item_id")
    if not isinstance(item_id, str) or item_id not in valid_item_ids:
        raise ValueError("human review names an item outside the queue")
    status = review.get("review_status")
    if status not in REVIEW_STATUSES:
        raise ValueError("human review has an invalid review_status")
    reviewer = review.get("reviewer")
    if not isinstance(reviewer, str) or not reviewer.strip() or len(reviewer.strip()) > MAX_REVIEWER_LENGTH:
        raise ValueError("human review needs a reviewer name or initials")
    reviewed_at = review.get("reviewed_at")
    if not isinstance(reviewed_at, str) or not reviewed_at.strip():
        raise ValueError("human review needs reviewed_at")
    try:
        datetime.fromisoformat(reviewed_at.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError("human review reviewed_at must be ISO-8601") from error
    mechanism_code = review.get("mechanism_code")
    primary_cause = review.get("primary_cause")
    if status == "reviewed":
        if not isinstance(mechanism_code, str) or mechanism_code not in MECHANISM_DEFINITIONS:
            raise ValueError("a reviewed root-cause item needs a valid mechanism_code")
        expected_primary = _primary_cause_for_mechanism(mechanism_code)
        if primary_cause != expected_primary:
            raise ValueError("human review primary_cause must match its mechanism_code")
    elif mechanism_code not in (None, "") or primary_cause not in (None, ""):
        raise ValueError("needs_more_evidence items must not assert a mechanism")
    rationale = review.get("review_rationale")
    if not isinstance(rationale, str) or len(rationale.strip()) > MAX_RATIONALE_LENGTH:
        raise ValueError("human review rationale must be text up to 4,000 characters")
    if status == "reviewed" and not rationale.strip():
        raise ValueError("a reviewed root-cause item needs a short rationale")
    if not isinstance(review.get("typical_case"), bool):
        raise ValueError("human review typical_case must be true or false")
    if status == "needs_more_evidence" and review["typical_case"]:
        raise ValueError("needs_more_evidence items cannot be marked as typical cases")


def _primary_cause_for_mechanism(mechanism_code: str) -> str:
    matches = [
        primary_cause
        for primary_cause, mechanisms in PRIMARY_CAUSE_MECHANISMS.items()
        if mechanism_code in mechanisms
    ]
    if len(matches) != 1:
        raise ValueError("mechanism code has no unique primary cause")
    return matches[0]


def _read_json_object(path: Path, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError(f"cannot read {label}: {path}") from error
    if not isinstance(payload, dict):
        raise ValueError(f"{label} must be a JSON object: {path}")
    return payload


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sha256_json(payload: Any) -> str:
    return hashlib.sha256(_canonical_json(payload)).hexdigest()


def _canonical_json(payload: Any) -> bytes:
    return (json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode(
        "utf-8"
    )


def _atomic_write(path: Path, serialized: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            delete=False,
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
        ) as handle:
            temporary_path = Path(handle.name)
            handle.write(serialized)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
    except Exception:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()
        raise
