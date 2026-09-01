import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .manifests import HEX_SHA256


SAFE_SKILL_VERSION = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
SAFE_LABEL = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")


@dataclass(frozen=True)
class SkillSnapshot:
    skill_version_id: str
    skill_source_paths: dict[str, str]
    skill_hashes: dict[str, str]
    mirror_synchronized: bool
    canonical_hash: str
    hash_policy: str = (
        "sha256(normalized LF utf-8 text for files; recursive relative path plus "
        "normalized content in case-folded POSIX relative-path order with an "
        "original-path tie-breaker for directories; excluding __pycache__ runtime caches)"
    )
    schema_version: int = 1

    def __post_init__(self) -> None:
        if SAFE_SKILL_VERSION.fullmatch(self.skill_version_id) is None:
            raise ValueError("skill_version_id must be a safe token")
        if not self.skill_source_paths:
            raise ValueError("skill_source_paths must not be empty")
        if set(self.skill_source_paths) != set(self.skill_hashes):
            raise ValueError("skill_source_paths and skill_hashes labels must match")
        for label in self.skill_source_paths:
            if SAFE_LABEL.fullmatch(label) is None:
                raise ValueError("skill source label must be a safe token")
        for label, digest in self.skill_hashes.items():
            _require_sha256(digest, f"skill_hashes[{label}]")
        _require_sha256(self.canonical_hash, "canonical_hash")
        if self.canonical_hash not in set(self.skill_hashes.values()):
            raise ValueError("canonical_hash must be one of the skill hashes")
        object.__setattr__(self, "skill_source_paths", dict(self.skill_source_paths))
        object.__setattr__(self, "skill_hashes", dict(self.skill_hashes))

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "SkillSnapshot":
        return cls(
            schema_version=int(payload.get("schema_version", 1)),
            skill_version_id=payload["skill_version_id"],
            skill_source_paths=dict(payload["skill_source_paths"]),
            skill_hashes=dict(payload["skill_hashes"]),
            mirror_synchronized=bool(payload["mirror_synchronized"]),
            canonical_hash=payload["canonical_hash"],
            hash_policy=payload.get(
                "hash_policy", "sha256(normalized LF utf-8 text)"
            ),
        )

    @classmethod
    def from_json_path(cls, path: Path) -> "SkillSnapshot":
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError(f"skill snapshot must be a JSON object: {path}")
        return cls.from_dict(payload)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "skill_version_id": self.skill_version_id,
            "skill_source_paths": dict(sorted(self.skill_source_paths.items())),
            "skill_hashes": dict(sorted(self.skill_hashes.items())),
            "mirror_synchronized": self.mirror_synchronized,
            "canonical_hash": self.canonical_hash,
            "hash_policy": self.hash_policy,
        }


def build_skill_snapshot(
    *,
    skill_version_id: str,
    source_paths: dict[str, Path],
) -> SkillSnapshot:
    if not source_paths:
        raise ValueError("at least one skill source path is required")
    skill_hashes = {
        label: _source_hash(path) for label, path in source_paths.items()
    }
    first_hash = next(iter(skill_hashes.values()))
    mirror_synchronized = all(digest == first_hash for digest in skill_hashes.values())
    canonical_hash = next(iter(skill_hashes.values()))
    return SkillSnapshot(
        skill_version_id=skill_version_id,
        skill_source_paths={
            label: path.as_posix() for label, path in source_paths.items()
        },
        skill_hashes=skill_hashes,
        mirror_synchronized=mirror_synchronized,
        canonical_hash=canonical_hash,
    )


def write_skill_snapshot(snapshot: SkillSnapshot, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(snapshot.to_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _normalized_text(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _source_hash(path: Path) -> str:
    if path.is_file():
        return _text_hash(_normalized_text(path))
    if path.is_dir():
        return _directory_hash(path)
    raise FileNotFoundError(f"skill source path missing: {path}")


def _directory_hash(path: Path) -> str:
    digest = hashlib.sha256()
    files = (
        item
        for item in path.rglob("*")
        if item.is_file()
        and "__pycache__" not in item.relative_to(path).parts
    )
    for file_path in sorted(
        files,
        key=lambda item: (
            item.relative_to(path).as_posix().casefold(),
            item.relative_to(path).as_posix(),
        ),
    ):
        digest.update(file_path.relative_to(path).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(_normalized_file_bytes(file_path))
        digest.update(b"\0")
    return digest.hexdigest()


def _normalized_file_bytes(path: Path) -> bytes:
    try:
        return _normalized_text(path).encode("utf-8")
    except UnicodeDecodeError:
        return path.read_bytes()


def _text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _require_sha256(value: str, label: str) -> None:
    if not isinstance(value, str) or HEX_SHA256.fullmatch(value) is None:
        raise ValueError(f"{label} must be a lowercase SHA-256 hex digest")
