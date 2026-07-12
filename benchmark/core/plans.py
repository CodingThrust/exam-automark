import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .manifests import GIT_COMMIT, HEX_SHA256
from .packets import audit_prompt_packet, directory_digest
from .schema import CourseSpec
from .skill_snapshots import SkillSnapshot


PLAN_STATUSES = {"planned", "data_inventory", "packets_built", "blocked"}
PACKET_TASKS = {"transcribe", "grade"}
SAFE_PACKET_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")


@dataclass(frozen=True)
class PlannedPacket:
    packet_id: str
    condition: str
    task: str
    prompt_template_id: str
    split: str

    def __post_init__(self) -> None:
        for label, value in (
            ("packet_id", self.packet_id),
            ("condition", self.condition),
            ("prompt_template_id", self.prompt_template_id),
            ("split", self.split),
        ):
            if SAFE_PACKET_ID.fullmatch(value) is None:
                raise ValueError(f"{label} must be a safe token")
        if self.task not in PACKET_TASKS:
            raise ValueError(f"unsupported planned packet task: {self.task}")

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "PlannedPacket":
        return cls(
            packet_id=payload["packet_id"],
            condition=payload["condition"],
            task=payload["task"],
            prompt_template_id=payload["prompt_template_id"],
            split=payload["split"],
        )

    def to_dict(self) -> dict[str, str]:
        return {
            "packet_id": self.packet_id,
            "condition": self.condition,
            "task": self.task,
            "prompt_template_id": self.prompt_template_id,
            "split": self.split,
        }


@dataclass(frozen=True)
class BuiltPacket:
    packet_id: str
    condition: str
    task: str
    split: str
    packet_path: str
    prompt_path: str
    manifest_path: str
    packet_hash: str
    audit_status: str = "passed"

    def __post_init__(self) -> None:
        for label, value in (
            ("packet_id", self.packet_id),
            ("condition", self.condition),
            ("task", self.task),
            ("split", self.split),
        ):
            if SAFE_PACKET_ID.fullmatch(value) is None:
                raise ValueError(f"{label} must be a safe token")
        if self.task not in PACKET_TASKS:
            raise ValueError(f"unsupported built packet task: {self.task}")
        for label, value in (
            ("packet_path", self.packet_path),
            ("prompt_path", self.prompt_path),
            ("manifest_path", self.manifest_path),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{label} must not be blank")
        _require_sha256(self.packet_hash, "packet_hash")
        if self.audit_status != "passed":
            raise ValueError("only audit-passed packets may be recorded")

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "BuiltPacket":
        return cls(
            packet_id=payload["packet_id"],
            condition=payload["condition"],
            task=payload["task"],
            split=payload["split"],
            packet_path=payload["packet_path"],
            prompt_path=payload["prompt_path"],
            manifest_path=payload["manifest_path"],
            packet_hash=payload["packet_hash"],
            audit_status=payload.get("audit_status", "passed"),
        )

    def to_dict(self) -> dict[str, str]:
        return {
            "packet_id": self.packet_id,
            "condition": self.condition,
            "task": self.task,
            "split": self.split,
            "packet_path": self.packet_path,
            "prompt_path": self.prompt_path,
            "manifest_path": self.manifest_path,
            "packet_hash": self.packet_hash,
            "audit_status": self.audit_status,
        }


@dataclass(frozen=True)
class ExperimentPlan:
    experiment_id: str
    course_id: str
    assessment_id: str
    status: str
    git_branch: str
    git_commit: str
    data_inventory_path: str
    data_snapshot_hash: str
    course_spec_path: str
    skill_version_id: str
    skill_source_paths: dict[str, str]
    skill_hashes: dict[str, str]
    prompt_template_hashes: dict[str, str]
    planned_packets: tuple[PlannedPacket, ...]
    built_packets: tuple[BuiltPacket, ...] = ()
    notes: tuple[str, ...] = field(default_factory=tuple)
    schema_version: int = 1

    def __post_init__(self) -> None:
        for label, value in (
            ("experiment_id", self.experiment_id),
            ("course_id", self.course_id),
            ("assessment_id", self.assessment_id),
            ("git_branch", self.git_branch),
            ("data_inventory_path", self.data_inventory_path),
            ("course_spec_path", self.course_spec_path),
            ("skill_version_id", self.skill_version_id),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{label} must not be blank")
        if self.status not in PLAN_STATUSES:
            raise ValueError(f"unsupported experiment plan status: {self.status}")
        if GIT_COMMIT.fullmatch(self.git_commit) is None:
            raise ValueError("git_commit must be a short or full lowercase hex commit")
        _require_sha256(self.data_snapshot_hash, "data_snapshot_hash")
        if not self.prompt_template_hashes:
            raise ValueError("prompt_template_hashes must not be empty")
        if not self.skill_source_paths:
            raise ValueError("skill_source_paths must not be empty")
        if set(self.skill_source_paths) != set(self.skill_hashes):
            raise ValueError("skill_source_paths and skill_hashes labels must match")
        for label, digest in self.skill_hashes.items():
            if SAFE_PACKET_ID.fullmatch(label) is None:
                raise ValueError("skill source label must be a safe token")
            _require_sha256(digest, f"skill_hashes[{label}]")
        for template_id, digest in self.prompt_template_hashes.items():
            if SAFE_PACKET_ID.fullmatch(template_id) is None:
                raise ValueError("prompt template id must be a safe token")
            _require_sha256(digest, f"prompt_template_hashes[{template_id}]")
        if not self.planned_packets:
            raise ValueError("planned_packets must not be empty")
        template_ids = set(self.prompt_template_hashes)
        missing = sorted(
            {
                packet.prompt_template_id
                for packet in self.planned_packets
                if packet.prompt_template_id not in template_ids
            }
        )
        if missing:
            raise ValueError(f"planned packet template missing: {missing}")
        object.__setattr__(self, "built_packets", tuple(self.built_packets))
        self._validate_built_packets()
        object.__setattr__(
            self, "prompt_template_hashes", dict(self.prompt_template_hashes)
        )
        object.__setattr__(self, "skill_source_paths", dict(self.skill_source_paths))
        object.__setattr__(self, "skill_hashes", dict(self.skill_hashes))
        object.__setattr__(self, "planned_packets", tuple(self.planned_packets))
        object.__setattr__(self, "notes", tuple(self.notes))

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ExperimentPlan":
        return cls(
            schema_version=int(payload.get("schema_version", 1)),
            experiment_id=payload["experiment_id"],
            course_id=payload["course_id"],
            assessment_id=payload["assessment_id"],
            status=payload["status"],
            git_branch=payload["git_branch"],
            git_commit=payload["git_commit"],
            data_inventory_path=payload["data_inventory_path"],
            data_snapshot_hash=payload["data_snapshot_hash"],
            course_spec_path=payload["course_spec_path"],
            skill_version_id=payload["skill_version_id"],
            skill_source_paths=dict(payload["skill_source_paths"]),
            skill_hashes=dict(payload["skill_hashes"]),
            prompt_template_hashes=dict(payload["prompt_template_hashes"]),
            planned_packets=tuple(
                PlannedPacket.from_dict(packet)
                for packet in payload["planned_packets"]
            ),
            built_packets=tuple(
                BuiltPacket.from_dict(packet)
                for packet in payload.get("built_packets", ())
            ),
            notes=tuple(payload.get("notes", ())),
        )

    @classmethod
    def from_json_path(cls, path: Path) -> "ExperimentPlan":
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError(f"experiment plan must be a JSON object: {path}")
        return cls.from_dict(payload)

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "schema_version": self.schema_version,
            "experiment_id": self.experiment_id,
            "course_id": self.course_id,
            "assessment_id": self.assessment_id,
            "status": self.status,
            "git_branch": self.git_branch,
            "git_commit": self.git_commit,
            "data_inventory_path": self.data_inventory_path,
            "data_snapshot_hash": self.data_snapshot_hash,
            "course_spec_path": self.course_spec_path,
            "skill_version_id": self.skill_version_id,
            "skill_source_paths": dict(sorted(self.skill_source_paths.items())),
            "skill_hashes": dict(sorted(self.skill_hashes.items())),
            "prompt_template_hashes": dict(
                sorted(self.prompt_template_hashes.items())
            ),
            "planned_packets": [
                packet.to_dict() for packet in self.planned_packets
            ],
            "notes": list(self.notes),
        }
        if self.built_packets:
            payload["built_packets"] = [
                packet.to_dict() for packet in self.built_packets
            ]
        return payload

    def _validate_built_packets(self) -> None:
        packet_ids = [packet.packet_id for packet in self.built_packets]
        if len(packet_ids) != len(set(packet_ids)):
            raise ValueError("built_packets must not contain duplicate packet ids")
        planned = {packet.packet_id: packet for packet in self.planned_packets}
        unknown = sorted(set(packet_ids) - set(planned))
        if unknown:
            raise ValueError(f"built packet was not planned: {unknown}")
        for packet in self.built_packets:
            planned_packet = planned[packet.packet_id]
            if (
                packet.condition != planned_packet.condition
                or packet.task != planned_packet.task
                or packet.split != planned_packet.split
            ):
                raise ValueError(
                    f"built packet does not match planned packet: {packet.packet_id}"
                )


def default_planned_packets(
    *,
    transcribe_template_id: str,
    grade_template_id: str,
) -> tuple[PlannedPacket, ...]:
    return (
        PlannedPacket(
            packet_id="T1-dev-r1",
            condition="T1",
            task="transcribe",
            prompt_template_id=transcribe_template_id,
            split="development",
        ),
        PlannedPacket(
            packet_id="T1-test-r1",
            condition="T1",
            task="transcribe",
            prompt_template_id=transcribe_template_id,
            split="heldout",
        ),
        PlannedPacket(
            packet_id="G1-dev-r1",
            condition="G1",
            task="grade",
            prompt_template_id=grade_template_id,
            split="development",
        ),
        PlannedPacket(
            packet_id="G1-test-r1",
            condition="G1",
            task="grade",
            prompt_template_id=grade_template_id,
            split="heldout",
        ),
    )


def write_experiment_plan(plan: ExperimentPlan, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(plan.to_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def build_standard_experiment_plan(
    *,
    experiment_id: str,
    status: str,
    git_branch: str,
    git_commit: str,
    inventory_path: Path,
    course_spec_path: Path,
    skill_snapshot_path: Path,
    transcribe_prompt_path: Path,
    grade_prompt_path: Path,
    transcribe_template_id: str = "transcribe_standard_v1",
    grade_template_id: str = "grade_standard_v1",
    notes: tuple[str, ...] = (),
) -> ExperimentPlan:
    course = CourseSpec.from_json_path(course_spec_path)
    inventory = _read_json(inventory_path)
    skill_snapshot = SkillSnapshot.from_json_path(skill_snapshot_path)
    snapshot_hash = inventory["snapshot_hash"]
    return ExperimentPlan(
        experiment_id=experiment_id,
        course_id=course.course_id,
        assessment_id=course.assessment_id,
        status=status,
        git_branch=git_branch,
        git_commit=git_commit,
        data_inventory_path=inventory_path.as_posix(),
        data_snapshot_hash=snapshot_hash,
        course_spec_path=course_spec_path.as_posix(),
        skill_version_id=skill_snapshot.skill_version_id,
        skill_source_paths=skill_snapshot.skill_source_paths,
        skill_hashes=skill_snapshot.skill_hashes,
        prompt_template_hashes={
            transcribe_template_id: _file_hash(transcribe_prompt_path),
            grade_template_id: _file_hash(grade_prompt_path),
        },
        planned_packets=default_planned_packets(
            transcribe_template_id=transcribe_template_id,
            grade_template_id=grade_template_id,
        ),
        notes=notes,
    )


def record_built_packet(plan: ExperimentPlan, packet_path: Path) -> ExperimentPlan:
    manifest_path = packet_path / "manifest.json"
    prompt_path = packet_path / "prompt.txt"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"packet manifest missing: {manifest_path}")
    if not prompt_path.is_file():
        raise FileNotFoundError(f"packet prompt missing: {prompt_path}")
    findings = audit_prompt_packet(packet_path)
    if findings:
        raise ValueError("packet audit failed: " + "; ".join(findings))

    manifest = _read_json(manifest_path)
    packet_id = manifest["packet_id"]
    planned = {packet.packet_id: packet for packet in plan.planned_packets}
    if packet_id not in planned:
        raise ValueError(f"packet was not planned: {packet_id}")
    planned_packet = planned[packet_id]
    if manifest["condition"] != planned_packet.condition:
        raise ValueError(f"packet condition does not match plan: {packet_id}")
    if manifest["task"] != planned_packet.task:
        raise ValueError(f"packet task does not match plan: {packet_id}")

    record = BuiltPacket(
        packet_id=packet_id,
        condition=manifest["condition"],
        task=manifest["task"],
        split=planned_packet.split,
        packet_path=packet_path.as_posix(),
        prompt_path=prompt_path.as_posix(),
        manifest_path=manifest_path.as_posix(),
        packet_hash=directory_digest(packet_path),
        audit_status="passed",
    )
    existing = [
        packet
        for packet in plan.built_packets
        if packet.packet_id != record.packet_id
    ]
    built_by_id = {packet.packet_id: packet for packet in existing}
    built_by_id[record.packet_id] = record
    order = {
        packet.packet_id: index
        for index, packet in enumerate(plan.planned_packets)
    }
    built_packets = tuple(
        sorted(built_by_id.values(), key=lambda packet: order[packet.packet_id])
    )
    status = (
        "packets_built"
        if {packet.packet_id for packet in built_packets} == set(order)
        else plan.status
    )
    return ExperimentPlan(
        experiment_id=plan.experiment_id,
        course_id=plan.course_id,
        assessment_id=plan.assessment_id,
        status=status,
        git_branch=plan.git_branch,
        git_commit=plan.git_commit,
        data_inventory_path=plan.data_inventory_path,
        data_snapshot_hash=plan.data_snapshot_hash,
        course_spec_path=plan.course_spec_path,
        skill_version_id=plan.skill_version_id,
        skill_source_paths=plan.skill_source_paths,
        skill_hashes=plan.skill_hashes,
        prompt_template_hashes=plan.prompt_template_hashes,
        planned_packets=plan.planned_packets,
        built_packets=built_packets,
        notes=plan.notes,
        schema_version=plan.schema_version,
    )


def _file_hash(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON object required: {path}")
    return payload


def _require_sha256(value: str, label: str) -> None:
    if not isinstance(value, str) or HEX_SHA256.fullmatch(value) is None:
        raise ValueError(f"{label} must be a lowercase SHA-256 hex digest")
