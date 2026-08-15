"""Build matched M1 and T1 image packets from one immutable snapshot.

This small orchestration layer removes a common manual failure mode: building
the direct grading packet and transcription packet from different student lists
or different source snapshots.  It creates no model outputs and leaves model
authorization disabled.
"""

from __future__ import annotations

import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .packets import PromptPacketResult, SAFE_TOKEN, directory_digest
from .route_lineage import check_m1_t1_g1_lineage
from .schema import (
    GRADING_OUTPUT_CONTRACT_V1,
    GRADING_OUTPUT_CONTRACTS,
    CourseSpec,
)
from .submission_snapshot_packets import (
    SubmissionSnapshotPacketSpec,
    build_submission_snapshot_packet,
)


@dataclass(frozen=True)
class MatchedImageRouteSpec:
    course: CourseSpec
    snapshot_root: Path
    output_root: Path
    split: str
    student_ids: tuple[str, ...]
    m1_packet_id: str
    t1_packet_id: str
    grade_prompt_text: str
    transcribe_prompt_text: str
    rubric: dict[str, Any]
    grading_output_contract: str = GRADING_OUTPUT_CONTRACT_V1
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.split, str) or SAFE_TOKEN.fullmatch(self.split) is None:
            raise ValueError("split must be a safe token")
        if self.m1_packet_id == self.t1_packet_id:
            raise ValueError("M1 and T1 packet IDs must differ")
        if not self.student_ids:
            raise ValueError("student_ids must not be empty")
        if len(self.student_ids) != len(set(self.student_ids)):
            raise ValueError("student_ids must be unique")
        for student_id in self.student_ids:
            self.course.validate_student_id(student_id)
        if not self.grade_prompt_text.strip() or not self.transcribe_prompt_text.strip():
            raise ValueError("route prompt text must not be blank")
        if self.grading_output_contract not in GRADING_OUTPUT_CONTRACTS:
            raise ValueError(
                "unsupported grading output contract: "
                f"{self.grading_output_contract}"
            )
        object.__setattr__(self, "snapshot_root", Path(self.snapshot_root))
        object.__setattr__(self, "output_root", Path(self.output_root))
        object.__setattr__(self, "student_ids", tuple(self.student_ids))
        object.__setattr__(self, "metadata", dict(self.metadata))


def build_matched_image_route_packets(
    spec: MatchedImageRouteSpec,
) -> dict[str, Any]:
    """Build a matched direct-grade/transcription pair and verify it.

    Packets are first built into a private temporary sibling so an invalid T1
    build cannot leave an M1 packet behind.  The resulting readiness report
    proves matching packet inputs but does not authorize any provider call.
    """

    target_root = spec.output_root.resolve()
    target_m1 = target_root / spec.m1_packet_id
    target_t1 = target_root / spec.t1_packet_id
    if target_m1.exists() or target_t1.exists():
        raise FileExistsError("matched route packet target already exists")
    target_root.parent.mkdir(parents=True, exist_ok=True)
    temporary_root = Path(
        tempfile.mkdtemp(prefix=".matched-image-routes-", dir=target_root.parent)
    )
    metadata = dict(spec.metadata)
    metadata["split"] = spec.split
    try:
        m1_temporary = build_submission_snapshot_packet(
            SubmissionSnapshotPacketSpec(
                course=spec.course,
                packet_id=spec.m1_packet_id,
                condition="M1",
                task="grade",
                prompt_text=spec.grade_prompt_text,
                student_ids=spec.student_ids,
                snapshot_root=spec.snapshot_root,
                output_root=temporary_root,
                rubric=spec.rubric,
                grading_output_contract=spec.grading_output_contract,
                metadata=metadata,
            )
        )
        t1_temporary = build_submission_snapshot_packet(
            SubmissionSnapshotPacketSpec(
                course=spec.course,
                packet_id=spec.t1_packet_id,
                condition="T1",
                task="transcribe",
                prompt_text=spec.transcribe_prompt_text,
                student_ids=spec.student_ids,
                snapshot_root=spec.snapshot_root,
                output_root=temporary_root,
                metadata=metadata,
            )
        )
        temporary_report = check_m1_t1_g1_lineage(
            m1_packet=m1_temporary.packet_path,
            t1_packet=t1_temporary.packet_path,
        )
        if temporary_report["status"] != "ready":
            raise ValueError("matched route packets failed lineage validation")

        target_root.mkdir(parents=True, exist_ok=True)
        m1_temporary.packet_path.replace(target_m1)
        t1_temporary.packet_path.replace(target_t1)
        report = check_m1_t1_g1_lineage(m1_packet=target_m1, t1_packet=target_t1)
        if report["status"] != "ready":
            raise ValueError("moved route packets failed lineage validation")
    finally:
        if temporary_root.exists():
            shutil.rmtree(temporary_root)

    return {
        "status": "ready",
        "model_run_allowed": False,
        "m1": _result_for(target_m1),
        "t1": _result_for(target_t1),
        "lineage": report,
    }


def _result_for(packet_path: Path) -> dict[str, Any]:
    return {
        "packet_path": str(packet_path),
        "packet_hash": directory_digest(packet_path),
    }
