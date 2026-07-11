import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


HEX_SHA256 = re.compile(r"^[0-9a-f]{64}$")
GIT_COMMIT = re.compile(r"^[0-9a-f]{7,40}$")


@dataclass(frozen=True)
class ExperimentRecord:
    experiment_id: str
    course_id: str
    assessment_id: str
    git_branch: str
    git_commit: str
    data_snapshot_hash: str
    prompt_packet_hashes: dict[str, str]
    conditions: tuple[str, ...]
    metrics_path: str
    note_path: str
    report_pdf_path: str | None = None
    skill_version_id: str | None = None
    skill_source_paths: dict[str, str] = field(default_factory=dict)
    skill_hashes: dict[str, str] = field(default_factory=dict)
    notes: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        for label, value in (
            ("experiment_id", self.experiment_id),
            ("course_id", self.course_id),
            ("assessment_id", self.assessment_id),
            ("git_branch", self.git_branch),
            ("metrics_path", self.metrics_path),
            ("note_path", self.note_path),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{label} must not be blank")
        if GIT_COMMIT.fullmatch(self.git_commit) is None:
            raise ValueError("git_commit must be a short or full lowercase hex commit")
        _require_sha256(self.data_snapshot_hash, "data_snapshot_hash")
        if not self.prompt_packet_hashes:
            raise ValueError("prompt_packet_hashes must not be empty")
        for condition, digest in self.prompt_packet_hashes.items():
            if not condition:
                raise ValueError("prompt packet condition must not be blank")
            _require_sha256(digest, f"prompt_packet_hashes[{condition}]")
        if not self.conditions:
            raise ValueError("conditions must not be empty")
        missing = sorted(set(self.conditions) - set(self.prompt_packet_hashes))
        if missing:
            raise ValueError(f"prompt packet hash missing for conditions: {missing}")
        if self.skill_version_id is not None:
            if not self.skill_source_paths:
                raise ValueError("skill_source_paths must not be empty when skill_version_id is set")
            if set(self.skill_source_paths) != set(self.skill_hashes):
                raise ValueError("skill_source_paths and skill_hashes labels must match")
            for label, digest in self.skill_hashes.items():
                if not label:
                    raise ValueError("skill source label must not be blank")
                _require_sha256(digest, f"skill_hashes[{label}]")
        object.__setattr__(self, "prompt_packet_hashes", dict(self.prompt_packet_hashes))
        object.__setattr__(self, "skill_source_paths", dict(self.skill_source_paths))
        object.__setattr__(self, "skill_hashes", dict(self.skill_hashes))
        object.__setattr__(self, "conditions", tuple(self.conditions))
        object.__setattr__(self, "notes", tuple(self.notes))

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ExperimentRecord":
        return cls(
            experiment_id=payload["experiment_id"],
            course_id=payload["course_id"],
            assessment_id=payload["assessment_id"],
            git_branch=payload["git_branch"],
            git_commit=payload["git_commit"],
            data_snapshot_hash=payload["data_snapshot_hash"],
            prompt_packet_hashes=dict(payload["prompt_packet_hashes"]),
            conditions=tuple(payload["conditions"]),
            metrics_path=payload["metrics_path"],
            note_path=payload["note_path"],
            report_pdf_path=payload.get("report_pdf_path"),
            skill_version_id=payload.get("skill_version_id"),
            skill_source_paths=dict(payload.get("skill_source_paths", {})),
            skill_hashes=dict(payload.get("skill_hashes", {})),
            notes=tuple(payload.get("notes", ())),
        )

    @classmethod
    def from_json_path(cls, path: Path) -> "ExperimentRecord":
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError(f"experiment record must be a JSON object: {path}")
        return cls.from_dict(payload)

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "experiment_id": self.experiment_id,
            "course_id": self.course_id,
            "assessment_id": self.assessment_id,
            "git_branch": self.git_branch,
            "git_commit": self.git_commit,
            "data_snapshot_hash": self.data_snapshot_hash,
            "prompt_packet_hashes": dict(sorted(self.prompt_packet_hashes.items())),
            "conditions": list(self.conditions),
            "metrics_path": self.metrics_path,
            "note_path": self.note_path,
            "notes": list(self.notes),
        }
        if self.skill_version_id is not None:
            payload["skill_version_id"] = self.skill_version_id
            payload["skill_source_paths"] = dict(sorted(self.skill_source_paths.items()))
            payload["skill_hashes"] = dict(sorted(self.skill_hashes.items()))
        if self.report_pdf_path is not None:
            payload["report_pdf_path"] = self.report_pdf_path
        return payload


def stable_json_digest(payload: Any) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def write_record(record: ExperimentRecord, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(record.to_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _require_sha256(value: str, label: str) -> None:
    if not isinstance(value, str) or HEX_SHA256.fullmatch(value) is None:
        raise ValueError(f"{label} must be a lowercase SHA-256 hex digest")
