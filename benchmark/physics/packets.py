import csv
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .privacy import assert_anonymous_name, assert_privacy_approved
from .providers import GRADING_RESPONSE_FORMAT
from .schema import QUESTION_IDS


FORBIDDEN_PACKET_TERMS = (
    "gold",
    "grades.csv",
    "primary_scores",
    "reviewer_scores",
    "predictions.csv",
    "metrics",
    "reports",
    "student_map",
)
FORBIDDEN_TEXT_TERMS = tuple(
    term for term in FORBIDDEN_PACKET_TERMS if term != "reports"
)

TRANSCRIPT_SCHEMA = {
    "type": "object",
    "properties": {
        "student_id": {"type": "string", "pattern": "^S[0-9]{3}$"},
        "answers": {
            "type": "array",
            "minItems": len(QUESTION_IDS),
            "maxItems": len(QUESTION_IDS),
            "items": {
                "type": "object",
                "properties": {
                    "question_id": {"type": "string", "enum": list(QUESTION_IDS)},
                    "text": {"type": "string"},
                    "unclear": {"type": "boolean"},
                },
                "required": ["question_id", "text", "unclear"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["student_id", "answers"],
    "additionalProperties": False,
}

PACKET_INSTRUCTIONS = """# Blind Benchmark Packet

Work only with files inside this packet. Do not inspect parent directories or
any other workspace. Read `prompt.txt`, `manifest.json`, and the files under
`inputs/`. Write exactly one JSON file per expected anonymous student under
`outputs/`, named `<student_id>.json`. Preserve every anonymous ID exactly.
"""


def build_blind_packet(
    benchmark_root: Path,
    condition: str,
    split: str,
    repetition: int,
    output_root: Path,
) -> Path:
    if condition not in {"T1", "G2", "G3"}:
        raise ValueError(f"unsupported Codex condition: {condition}")
    if split not in {"dev", "test"}:
        raise ValueError(f"unsupported split: {split}")
    if repetition != 1:
        raise ValueError("revised benchmark permits one run per condition")
    if split == "test" and not (benchmark_root / "freeze.json").exists():
        raise ValueError("held-out split is sealed until freeze.json exists")

    split_data = _read_json(benchmark_root / "manifest" / "split.json")
    student_ids = _student_ids(split_data, condition, split)
    run_id = f"{condition}-{split}-r{repetition}"
    packet = output_root / run_id
    packet.mkdir(parents=True, exist_ok=False)
    (packet / "inputs").mkdir()
    (packet / "outputs").mkdir()

    if condition == "T1":
        _copy_approved_images(benchmark_root, packet / "inputs", student_ids)
    elif condition == "G2":
        _copy_automatic_transcripts(
            benchmark_root, packet / "inputs", student_ids, split
        )
    else:
        _write_human_transcripts(
            benchmark_root, packet / "inputs", student_ids, split
        )

    prompt_path = Path(__file__).with_name("prompts") / (
        "transcribe.txt" if condition == "T1" else "grade_structured.txt"
    )
    prompt = prompt_path.read_text(encoding="utf-8")
    (packet / "prompt.txt").write_text(prompt, encoding="utf-8")
    (packet / "INSTRUCTIONS.md").write_text(PACKET_INSTRUCTIONS, encoding="utf-8")

    output_schema = (
        TRANSCRIPT_SCHEMA
        if condition == "T1"
        else GRADING_RESPONSE_FORMAT["schema"]
    )
    _write_json(packet / "output.schema.json", output_schema)

    rubric_hash = None
    if condition in {"G2", "G3"}:
        rubric_source = benchmark_root / "rubric" / "rubric_v1.json"
        rubric_target = packet / "rubric.json"
        shutil.copy2(rubric_source, rubric_target)
        rubric_hash = _file_hash(rubric_target)

    config = _read_json(
        Path(__file__).with_name("configs") / "physics_week9.json"
    )
    manifest = {
        "run_id": run_id,
        "condition": condition,
        "split": split,
        "repetition": repetition,
        "provider": config["gpt_execution"],
        "display_model": config["gpt_display_model"],
        "student_ids": student_ids,
        "prompt_hash": _file_hash(packet / "prompt.txt"),
        "rubric_hash": rubric_hash,
        "input_hashes": {
            student_id: _directory_hash(packet / "inputs" / student_id)
            for student_id in student_ids
        },
        "created_at": _utc_now(),
    }
    _write_json(packet / "manifest.json", manifest)

    findings = audit_blind_packet(packet)
    if findings:
        raise ValueError("blind packet audit failed: " + "; ".join(findings))
    return packet


def audit_blind_packet(packet: Path) -> list[str]:
    findings = []
    text_suffixes = {".json", ".md", ".txt", ".csv"}
    for path in packet.rglob("*"):
        relative = path.relative_to(packet).as_posix().lower()
        for term in FORBIDDEN_PACKET_TERMS:
            if term.lower() in relative:
                findings.append(f"forbidden path term {term}: {relative}")
        if path.is_file() and path.suffix.lower() in text_suffixes:
            text = path.read_text(encoding="utf-8").lower()
            for term in FORBIDDEN_TEXT_TERMS:
                if term.lower() in text:
                    findings.append(f"forbidden text term {term}: {relative}")
    return sorted(set(findings))


def _student_ids(
    split_data: dict[str, Any], condition: str, split: str
) -> list[str]:
    key = "development_student_ids" if split == "dev" else "heldout_student_ids"
    if condition == "G3":
        return list(split_data["transcript_gold"][key])
    return list(split_data[key])


def _copy_approved_images(
    benchmark_root: Path, input_root: Path, student_ids: list[str]
) -> None:
    review_path = benchmark_root / "manifest" / "privacy_review.csv"
    with review_path.open(newline="", encoding="utf-8-sig") as handle:
        privacy_rows = list(csv.DictReader(handle))
    assert_privacy_approved(privacy_rows)
    approved_pages = {row["page"] for row in privacy_rows}

    for student_id in student_ids:
        source_paths = sorted((benchmark_root / "anonymized" / student_id).glob("*.jpg"))
        if not source_paths:
            raise FileNotFoundError(f"anonymous images missing for: {student_id}")
        target_dir = input_root / student_id
        target_dir.mkdir()
        for source in source_paths:
            assert_anonymous_name(source)
            if source.name not in approved_pages:
                raise ValueError(f"privacy approval missing for: {source.name}")
            shutil.copy2(source, target_dir / source.name)


def _copy_automatic_transcripts(
    benchmark_root: Path,
    input_root: Path,
    student_ids: list[str],
    split: str,
) -> None:
    source_root = benchmark_root / "transcripts" / "automatic" / f"T1-{split}-r1"
    for student_id in student_ids:
        source = source_root / f"{student_id}.json"
        if not source.exists():
            raise FileNotFoundError(f"automatic transcript missing for: {student_id}")
        target_dir = input_root / student_id
        target_dir.mkdir()
        shutil.copy2(source, target_dir / "transcript.json")


def _write_human_transcripts(
    benchmark_root: Path,
    input_root: Path,
    student_ids: list[str],
    split: str,
) -> None:
    review_path = benchmark_root / "transcripts" / "human" / f"H1-{split}.csv"
    with review_path.open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    by_student: dict[str, list[dict[str, Any]]] = {student_id: [] for student_id in student_ids}
    for row in rows:
        student_id = row["student_id"]
        if student_id in by_student:
            if row["reviewed"].strip().lower() != "true":
                raise ValueError(f"human transcript review incomplete for: {student_id}")
            text = row["human_text"].strip()
            if not text:
                raise ValueError(f"human transcript text missing for: {student_id}")
            by_student[student_id].append(
                {
                    "question_id": row["question_id"],
                    "text": text,
                    "unclear": "[UNCLEAR]" in text,
                }
            )
    for student_id, answers in by_student.items():
        if {answer["question_id"] for answer in answers} != set(QUESTION_IDS):
            raise ValueError(f"human transcript questions incomplete for: {student_id}")
        target_dir = input_root / student_id
        target_dir.mkdir()
        _write_json(
            target_dir / "transcript.json",
            {"student_id": student_id, "answers": answers},
        )


def _directory_hash(path: Path) -> str:
    digest = hashlib.sha256()
    for file_path in sorted(item for item in path.rglob("*") if item.is_file()):
        digest.update(file_path.relative_to(path).as_posix().encode("utf-8"))
        digest.update(file_path.read_bytes())
    return digest.hexdigest()


def _file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
