import json
import subprocess
from pathlib import Path
from typing import Any

from .packets import audit_prompt_packet, directory_digest
from .plans import BuiltPacket, ExperimentPlan, PlannedPacket


def build_run_readiness_report(
    *,
    baseline_plan_path: Path,
    candidate_plan_path: Path,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    root = Path.cwd() if repo_root is None else Path(repo_root)
    baseline = ExperimentPlan.from_json_path(baseline_plan_path)
    candidate = ExperimentPlan.from_json_path(candidate_plan_path)
    checks: list[dict[str, Any]] = []

    _check(
        checks,
        "plans_are_packetized",
        baseline.status == "packets_built" and candidate.status == "packets_built",
        f"baseline={baseline.status}; candidate={candidate.status}",
    )
    _check(
        checks,
        "same_course_and_assessment",
        (
            baseline.course_id == candidate.course_id
            and baseline.assessment_id == candidate.assessment_id
        ),
        f"{baseline.course_id}/{baseline.assessment_id} vs "
        f"{candidate.course_id}/{candidate.assessment_id}",
    )
    _check(
        checks,
        "same_data_snapshot",
        baseline.data_snapshot_hash == candidate.data_snapshot_hash,
        _compare_short(baseline.data_snapshot_hash, candidate.data_snapshot_hash),
    )
    _check(
        checks,
        "same_data_inventory_and_course_spec",
        (
            baseline.data_inventory_path == candidate.data_inventory_path
            and baseline.course_spec_path == candidate.course_spec_path
        ),
        f"inventory={baseline.data_inventory_path}; course_spec={baseline.course_spec_path}",
    )
    _check(
        checks,
        "same_git_anchor",
        (
            baseline.git_branch == candidate.git_branch
            and baseline.git_commit == candidate.git_commit
        ),
        f"{baseline.git_branch}@{baseline.git_commit} vs "
        f"{candidate.git_branch}@{candidate.git_commit}",
    )
    _check(
        checks,
        "different_skill_versions",
        baseline.skill_version_id != candidate.skill_version_id,
        f"{baseline.skill_version_id} vs {candidate.skill_version_id}",
    )
    _check(
        checks,
        "different_skill_hashes",
        set(baseline.skill_hashes.values()) != set(candidate.skill_hashes.values()),
        "candidate skill hash must differ from baseline skill hash",
    )

    baseline_planned = _planned_by_id(baseline)
    candidate_planned = _planned_by_id(candidate)
    baseline_built = _built_by_id(baseline)
    candidate_built = _built_by_id(candidate)
    _check(
        checks,
        "same_planned_packet_ids",
        set(baseline_planned) == set(candidate_planned),
        _set_compare_detail(set(baseline_planned), set(candidate_planned)),
    )
    _check(
        checks,
        "same_built_packet_ids",
        set(baseline_built) == set(candidate_built),
        _set_compare_detail(set(baseline_built), set(candidate_built)),
    )
    _check(
        checks,
        "all_packets_audit_recorded_passed",
        all(packet.audit_status == "passed" for packet in baseline.built_packets)
        and all(packet.audit_status == "passed" for packet in candidate.built_packets),
        "all built packet records must have audit_status=passed",
    )

    baseline_grade_ids = _template_ids_for_task(baseline, "grade")
    candidate_grade_ids = _template_ids_for_task(candidate, "grade")
    baseline_transcribe_ids = _template_ids_for_task(baseline, "transcribe")
    candidate_transcribe_ids = _template_ids_for_task(candidate, "transcribe")
    _check(
        checks,
        "grade_prompt_differs",
        (
            baseline_grade_ids != candidate_grade_ids
            and _template_hashes(baseline, baseline_grade_ids)
            != _template_hashes(candidate, candidate_grade_ids)
        ),
        f"{sorted(baseline_grade_ids)} vs {sorted(candidate_grade_ids)}",
    )
    _check(
        checks,
        "transcribe_prompt_held_constant",
        _template_hashes(baseline, baseline_transcribe_ids)
        == _template_hashes(candidate, candidate_transcribe_ids),
        f"{sorted(baseline_transcribe_ids)} vs {sorted(candidate_transcribe_ids)}",
    )

    manifests = _load_manifests(root, baseline_built, candidate_built, checks)
    _check_manifest_consistency(
        checks,
        root,
        baseline,
        candidate,
        baseline_planned,
        candidate_planned,
        baseline_built,
        candidate_built,
        manifests,
    )
    _check_no_result_artifacts(
        checks,
        root,
        baseline_plan_path,
        candidate_plan_path,
    )
    git_state = _check_git_state(
        checks,
        root,
        expected_branch=baseline.git_branch,
        expected_commit=baseline.git_commit,
    )

    failed = [check for check in checks if check["status"] == "failed"]
    report = {
        "schema_version": 1,
        "report_type": "run_readiness",
        "status": "not_ready" if failed else "ready",
        "model_run_status": "not_started",
        "baseline_plan_path": baseline_plan_path.as_posix(),
        "candidate_plan_path": candidate_plan_path.as_posix(),
        "anchors": {
            "course_id": baseline.course_id,
            "assessment_id": baseline.assessment_id,
            "data_snapshot_hash": baseline.data_snapshot_hash,
            "course_spec_path": baseline.course_spec_path,
            "data_inventory_path": baseline.data_inventory_path,
            "git_branch": baseline.git_branch,
            "git_commit": baseline.git_commit,
            "current_git_branch": git_state["current_branch"],
            "current_git_commit": git_state["current_commit"],
            "baseline": _plan_anchor(baseline),
            "candidate": _plan_anchor(candidate),
        },
        "checks": checks,
        "next_actions": _next_actions(checks),
    }
    return report


def write_readiness_json(report: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def write_readiness_markdown(report: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_readiness_markdown(report), encoding="utf-8", newline="\n")


def render_readiness_markdown(report: dict[str, Any]) -> str:
    anchors = report["anchors"]
    title = f"{anchors['course_id']} {anchors['assessment_id']} Run Readiness"
    lines = [
        f"# {title}",
        "",
        f"Status: **{report['status']}**",
        "",
        "No model calls are recorded by this checklist.",
        "",
        "## Anchors",
        "",
        f"- Course: `{anchors['course_id']}`",
        f"- Assessment: `{anchors['assessment_id']}`",
        f"- Data snapshot: `{anchors['data_snapshot_hash']}`",
        f"- Course spec: `{anchors['course_spec_path']}`",
        f"- Data inventory: `{anchors['data_inventory_path']}`",
        f"- Git: `{anchors['git_branch']} @ {anchors['git_commit']}`",
        f"- Current Git: `{anchors['current_git_branch']} @ {anchors['current_git_commit']}`",
        f"- Baseline skill: `{anchors['baseline']['skill_version_id']}`",
        f"- Candidate skill: `{anchors['candidate']['skill_version_id']}`",
        "",
        "## Checks",
        "",
        "| Check | Status | Detail |",
        "| --- | --- | --- |",
    ]
    for check in report["checks"]:
        lines.append(
            "| `{}` | {} | {} |".format(
                check["id"],
                check["status"],
                _escape_table(str(check.get("detail", ""))),
            )
        )
    lines.extend(["", "## Next Actions", ""])
    if report["next_actions"]:
        lines.extend(f"- {action}" for action in report["next_actions"])
    else:
        lines.append("- Ready to run only after the researcher explicitly starts model calls.")
    lines.append("")
    return "\n".join(lines)


def _check(
    checks: list[dict[str, Any]],
    check_id: str,
    passed: bool,
    detail: str,
    *,
    status_if_false: str = "failed",
) -> None:
    checks.append(
        {
            "id": check_id,
            "status": "passed" if passed else status_if_false,
            "detail": detail,
        }
    )


def _planned_by_id(plan: ExperimentPlan) -> dict[str, PlannedPacket]:
    return {packet.packet_id: packet for packet in plan.planned_packets}


def _built_by_id(plan: ExperimentPlan) -> dict[str, BuiltPacket]:
    return {packet.packet_id: packet for packet in plan.built_packets}


def _template_ids_for_task(plan: ExperimentPlan, task: str) -> set[str]:
    return {
        packet.prompt_template_id
        for packet in plan.planned_packets
        if packet.task == task
    }


def _template_hashes(plan: ExperimentPlan, template_ids: set[str]) -> set[str]:
    return {
        digest
        for template_id, digest in plan.prompt_template_hashes.items()
        if template_id in template_ids
    }


def _load_manifests(
    root: Path,
    baseline_built: dict[str, BuiltPacket],
    candidate_built: dict[str, BuiltPacket],
    checks: list[dict[str, Any]],
) -> dict[tuple[str, str], dict[str, Any]]:
    manifests = {}
    missing = []
    for label, packets in (("baseline", baseline_built), ("candidate", candidate_built)):
        for packet_id, packet in packets.items():
            path = _resolve(root, packet.manifest_path)
            if not path.is_file():
                missing.append(f"{label}:{packet_id}:{packet.manifest_path}")
                continue
            payload = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                missing.append(f"{label}:{packet_id}:manifest_not_object")
                continue
            manifests[(label, packet_id)] = payload
    _check(
        checks,
        "packet_manifests_exist",
        not missing,
        "; ".join(missing) if missing else "all packet manifests are present",
    )
    return manifests


def _check_manifest_consistency(
    checks: list[dict[str, Any]],
    root: Path,
    baseline: ExperimentPlan,
    candidate: ExperimentPlan,
    baseline_planned: dict[str, PlannedPacket],
    candidate_planned: dict[str, PlannedPacket],
    baseline_built: dict[str, BuiltPacket],
    candidate_built: dict[str, BuiltPacket],
    manifests: dict[tuple[str, str], dict[str, Any]],
) -> None:
    common_ids = sorted(set(baseline_built) & set(candidate_built))
    packet_paths = [
        packet.packet_path
        for packet in list(baseline_built.values()) + list(candidate_built.values())
    ]
    _check(
        checks,
        "packet_paths_are_local_data",
        all(path.startswith("Data/") for path in packet_paths),
        "all packet paths should be under ignored Data/",
    )

    missing_paths = []
    hash_mismatches = []
    audit_findings = []
    prompt_mismatches = []
    metadata_mismatches = []
    for label, plan, planned, built in (
        ("baseline", baseline, baseline_planned, baseline_built),
        ("candidate", candidate, candidate_planned, candidate_built),
    ):
        for packet_id, packet in built.items():
            packet_path = _resolve(root, packet.packet_path)
            if not packet_path.is_dir():
                missing_paths.append(f"{label}:{packet_id}:{packet.packet_path}")
                continue
            actual_hash = directory_digest(packet_path)
            if actual_hash != packet.packet_hash:
                hash_mismatches.append(f"{label}:{packet_id}")
            findings = audit_prompt_packet(packet_path)
            if findings:
                audit_findings.append(f"{label}:{packet_id}:{findings}")
            manifest = manifests.get((label, packet_id))
            planned_packet = planned[packet_id]
            if manifest is None:
                continue
            expected_prompt_hash = plan.prompt_template_hashes[
                planned_packet.prompt_template_id
            ]
            if manifest.get("prompt_hash") != expected_prompt_hash:
                prompt_mismatches.append(f"{label}:{packet_id}")
            metadata = manifest.get("metadata", {})
            expected_metadata = {
                "experiment_id": plan.experiment_id,
                "skill_version_id": plan.skill_version_id,
                "prompt_template_id": planned_packet.prompt_template_id,
                "split": planned_packet.split,
            }
            for key, expected in expected_metadata.items():
                if metadata.get(key) != expected:
                    metadata_mismatches.append(
                        f"{label}:{packet_id}:{key}={metadata.get(key)}"
                    )
    _check(
        checks,
        "packet_directories_exist",
        not missing_paths,
        "; ".join(missing_paths) if missing_paths else "all packet directories exist",
    )
    _check(
        checks,
        "packet_hashes_match_local_files",
        not hash_mismatches,
        "; ".join(hash_mismatches) if hash_mismatches else "all packet hashes match",
    )
    _check(
        checks,
        "packet_audits_pass_now",
        not audit_findings,
        "; ".join(audit_findings) if audit_findings else "all packet audits pass",
    )
    _check(
        checks,
        "manifest_prompt_hashes_match_plan",
        not prompt_mismatches,
        "; ".join(prompt_mismatches)
        if prompt_mismatches
        else "all manifest prompt hashes match plan templates",
    )
    _check(
        checks,
        "manifest_metadata_matches_plan",
        not metadata_mismatches,
        "; ".join(metadata_mismatches)
        if metadata_mismatches
        else "all packet metadata matches plan",
    )

    input_mismatches = []
    rubric_mismatches = []
    for packet_id in common_ids:
        base_manifest = manifests.get(("baseline", packet_id))
        cand_manifest = manifests.get(("candidate", packet_id))
        if base_manifest is None or cand_manifest is None:
            continue
        if (
            base_manifest.get("student_ids") != cand_manifest.get("student_ids")
            or base_manifest.get("input_hashes") != cand_manifest.get("input_hashes")
        ):
            input_mismatches.append(packet_id)
        if base_manifest.get("task") == "grade":
            if base_manifest.get("rubric_hash") != cand_manifest.get("rubric_hash"):
                rubric_mismatches.append(packet_id)
    _check(
        checks,
        "same_students_and_inputs_per_packet",
        not input_mismatches,
        "; ".join(input_mismatches)
        if input_mismatches
        else "matching packet ids use the same student ids and input hashes",
    )
    _check(
        checks,
        "same_rubric_for_grade_packets",
        not rubric_mismatches,
        "; ".join(rubric_mismatches)
        if rubric_mismatches
        else "grade packets use the same rubric hash",
    )


def _check_no_result_artifacts(
    checks: list[dict[str, Any]],
    root: Path,
    baseline_plan_path: Path,
    candidate_plan_path: Path,
) -> None:
    found = []
    for plan_path in (baseline_plan_path, candidate_plan_path):
        directory = _resolve(root, plan_path).parent
        for pattern in ("experiment.json", "metrics*.json", "predictions*.csv"):
            found.extend(path.as_posix() for path in directory.glob(pattern))
    _check(
        checks,
        "no_model_result_artifacts_in_plan_dirs",
        not found,
        "; ".join(found) if found else "no experiment, metrics, or prediction artifacts found",
    )


def _check_git_state(
    checks: list[dict[str, Any]],
    root: Path,
    *,
    expected_branch: str,
    expected_commit: str,
) -> dict[str, str | None]:
    state: dict[str, str | None] = {
        "current_branch": None,
        "current_commit": None,
    }
    if not (root / ".git").exists():
        for check_id, detail in (
            (
                "git_worktree_clean",
                "not a git worktree; cannot verify clean commit anchor",
            ),
            (
                "current_git_branch_matches_plan",
                "not a git worktree; cannot verify current branch",
            ),
            (
                "planned_git_commit_exists",
                "not a git worktree; cannot resolve planned commit",
            ),
            (
                "current_git_head_contains_plan_commit",
                "not a git worktree; cannot compare HEAD and planned commit",
            ),
            (
                "post_anchor_changes_are_record_only",
                "not a git worktree; cannot inspect post-anchor changes",
            ),
            (
                "data_ignored_by_git",
                "not a git worktree; cannot verify Data/ ignore status",
            ),
        ):
            _check(checks, check_id, False, detail, status_if_false="warning")
        return state

    branch = _git(root, "rev-parse", "--abbrev-ref", "HEAD")
    head = _git(root, "rev-parse", "HEAD")
    current_branch = branch.stdout.strip() if branch.returncode == 0 else None
    current_commit = head.stdout.strip() if head.returncode == 0 else None
    state["current_branch"] = current_branch
    state["current_commit"] = current_commit

    _check(
        checks,
        "current_git_branch_matches_plan",
        current_branch == expected_branch,
        f"current={current_branch}; planned={expected_branch}",
    )

    resolved = _git(
        root,
        "rev-parse",
        "--verify",
        "--quiet",
        f"{expected_commit}^{{commit}}",
    )
    resolved_commit = resolved.stdout.strip() if resolved.returncode == 0 else None
    _check(
        checks,
        "planned_git_commit_exists",
        resolved_commit is not None,
        f"planned={expected_commit}; resolved={resolved_commit}",
    )

    contains_anchor = False
    if current_commit is not None and resolved_commit is not None:
        if current_commit == resolved_commit:
            contains_anchor = True
        else:
            merge_base = _git(
                root,
                "merge-base",
                "--is-ancestor",
                resolved_commit,
                "HEAD",
            )
            contains_anchor = merge_base.returncode == 0
    _check(
        checks,
        "current_git_head_contains_plan_commit",
        contains_anchor,
        f"HEAD={current_commit}; planned={resolved_commit}",
    )

    disallowed_changes: list[str] = []
    if contains_anchor and current_commit != resolved_commit:
        diff = _git(root, "diff", "--name-only", resolved_commit, "HEAD")
        changed_paths = [
            line.strip() for line in diff.stdout.splitlines() if line.strip()
        ]
        disallowed_changes = [
            path
            for path in changed_paths
            if not path.startswith("experiments/records/")
        ]
        detail = (
            "post-anchor commits only touch experiment records"
            if not disallowed_changes
            else "; ".join(disallowed_changes)
        )
    elif contains_anchor:
        detail = "HEAD is exactly the planned commit"
    else:
        detail = "cannot inspect post-anchor changes until planned commit is in HEAD"
    _check(
        checks,
        "post_anchor_changes_are_record_only",
        contains_anchor and not disallowed_changes,
        detail,
    )

    status = _git(root, "status", "--porcelain")
    dirty_lines = [line for line in status.stdout.splitlines() if line.strip()]
    _check(
        checks,
        "git_worktree_clean",
        not dirty_lines,
        "working tree clean"
        if not dirty_lines
        else f"{len(dirty_lines)} uncommitted/untracked entries; commit before model calls",
    )

    ignored = _git(root, "check-ignore", "-q", "Data")
    tracked = _git(root, "ls-files", "--", "Data")
    tracked_files = [line for line in tracked.stdout.splitlines() if line.strip()]
    _check(
        checks,
        "data_ignored_by_git",
        ignored.returncode == 0 and not tracked_files,
        "Data/ is ignored and has no tracked files"
        if ignored.returncode == 0 and not tracked_files
        else "Data/ ignore or tracking status is unsafe",
    )
    return state


def _git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=root,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )


def _plan_anchor(plan: ExperimentPlan) -> dict[str, Any]:
    return {
        "experiment_id": plan.experiment_id,
        "skill_version_id": plan.skill_version_id,
        "skill_hashes": dict(sorted(plan.skill_hashes.items())),
        "prompt_template_hashes": dict(sorted(plan.prompt_template_hashes.items())),
        "packet_hashes": {
            packet.packet_id: packet.packet_hash for packet in plan.built_packets
        },
    }


def _next_actions(checks: list[dict[str, Any]]) -> list[str]:
    actions = []
    failed_ids = {check["id"] for check in checks if check["status"] == "failed"}
    if "git_worktree_clean" in failed_ids:
        actions.append("Commit or otherwise freeze the current repository state before model calls.")
    if {
        "current_git_branch_matches_plan",
        "planned_git_commit_exists",
        "current_git_head_contains_plan_commit",
        "post_anchor_changes_are_record_only",
    } & failed_ids:
        actions.append("Update the git anchor or move back to the recorded experiment branch before model calls.")
    if any(check_id.startswith("packet") or check_id.startswith("manifest") for check_id in failed_ids):
        actions.append("Regenerate or re-record prompt packets before running a model.")
    if "data_ignored_by_git" in failed_ids:
        actions.append("Fix Data/ git ignore or tracking status before sharing the repository.")
    if not actions and failed_ids:
        actions.append("Resolve failed readiness checks before model calls.")
    return actions


def _resolve(root: Path, path: str | Path) -> Path:
    value = Path(path)
    return value if value.is_absolute() else root / value


def _compare_short(left: str, right: str) -> str:
    return f"{left[:12]}... vs {right[:12]}..."


def _set_compare_detail(left: set[str], right: set[str]) -> str:
    if left == right:
        return ", ".join(sorted(left))
    return f"only_left={sorted(left - right)}; only_right={sorted(right - left)}"


def _escape_table(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")
