import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from benchmark.core.research_records import audit_research_records


SOURCE_REPOSITORY = "https://github.com/example/research-harness"
SOURCE_COMMIT = "0123456789abcdef0123456789abcdef01234567"
LITERATURE_MANIFEST = Path(
    "experiments/records/literature-surveys/sci_brain_run_manifest.json"
)


class ResearchRecordAuditTests(unittest.TestCase):
    def test_committed_tooling_survey_manifest_passes(self):
        findings = audit_research_records(
            Path("experiments/records/tooling-surveys/sources.json")
        )

        self.assertEqual(findings, [])

    def test_committed_literature_survey_manifest_passes_with_known_legacy_gap(self):
        findings = audit_research_records(LITERATURE_MANIFEST)

        self.assertEqual(findings, [])

    def test_complete_future_literature_provenance_passes(self):
        payload = _complete_literature_payload()

        findings = _audit_temporary_payload(payload)

        self.assertEqual(findings, [])

    def test_complete_future_literature_provenance_requires_run_time_evidence(self):
        payload = _complete_literature_payload()
        payload["tool"]["source_commit"] = None
        payload["discovery"]["queries"] = None
        payload["discovery"]["selection_log"] = None

        findings = _audit_temporary_payload(payload)

        self.assertTrue(any("tool.source_commit" in item for item in findings))
        self.assertTrue(any("discovery.queries" in item for item in findings))
        self.assertTrue(any("discovery.selection_log" in item for item in findings))

    def test_legacy_literature_exception_cannot_be_reused_for_a_future_run(self):
        payload = _committed_literature_payload()
        payload["run_date"] = "2026-07-27"

        findings = _audit_temporary_payload(payload)

        self.assertTrue(
            any("applies only to its recorded historical run_date" in item for item in findings)
        )

    def test_literature_report_scope_drift_is_rejected(self):
        payload = _complete_literature_payload()
        payload["report_records"][0]["scoped_cite_keys"].pop()

        findings = _audit_temporary_payload(payload)

        self.assertTrue(
            any("do not match citations in source_path" in item for item in findings)
        )
        self.assertTrue(
            any("union of declared report scoped cite keys" in item for item in findings)
        )

    def test_valid_pinned_record_passes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            record_path = root / "experiments/records/tooling-surveys/review.md"
            record_path.parent.mkdir(parents=True)
            record_path.write_text(
                "# Review\n\n"
                f"Source: {SOURCE_REPOSITORY}\n\n"
                f"Commit: {SOURCE_COMMIT}\n\n"
                f"Evidence: {SOURCE_REPOSITORY}/blob/{SOURCE_COMMIT}/README.md\n",
                encoding="utf-8",
            )
            manifest = _write_manifest(root)

            findings = audit_research_records(manifest, repo_root=root)

        self.assertEqual(findings, [])

    def test_mojibake_and_floating_main_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            record_path = root / "experiments/records/tooling-surveys/review.md"
            record_path.parent.mkdir(parents=True)
            record_path.write_text(
                "# Review\n\n"
                f"Source: {SOURCE_REPOSITORY}\n\n"
                f"Commit: {SOURCE_COMMIT}\n\n"
                "Broken: 鍙\n\n"
                f"Floating: {SOURCE_REPOSITORY}/blob/main/README.md\n",
                encoding="utf-8",
            )
            manifest = _write_manifest(root)

            findings = audit_research_records(manifest, repo_root=root)

        self.assertTrue(any("mojibake" in finding for finding in findings))
        self.assertTrue(any("floating GitHub main" in finding for finding in findings))

    def test_invalid_utf8_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            record_path = root / "experiments/records/tooling-surveys/review.md"
            record_path.parent.mkdir(parents=True)
            record_path.write_bytes(b"\xff\xfe\x00")
            manifest = _write_manifest(root)

            findings = audit_research_records(manifest, repo_root=root)

        self.assertTrue(any("not valid UTF-8" in finding for finding in findings))


def _write_manifest(root: Path) -> Path:
    manifest = root / "sources.json"
    manifest.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "records": [
                    {
                        "record_path": (
                            "experiments/records/tooling-surveys/review.md"
                        ),
                        "source_repository": SOURCE_REPOSITORY,
                        "source_commit": SOURCE_COMMIT,
                        "checked_date": "2026-07-25",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return manifest


def _committed_literature_payload() -> dict:
    return json.loads(LITERATURE_MANIFEST.read_text(encoding="utf-8"))


def _complete_literature_payload() -> dict:
    payload = deepcopy(_committed_literature_payload())
    payload["run_date"] = "2026-07-27"
    payload["provenance_status"] = "complete"
    payload.pop("legacy_exception")
    payload["tool"]["source_commit"] = SOURCE_COMMIT
    payload["tool"]["source_commit_status"] = "recorded_at_run_time"
    payload["discovery"]["queries"] = [
        "automated prompt optimization grading skills",
        "LLM grading handwritten mathematics negative results",
    ]
    payload["discovery"]["queries_status"] = "recorded_at_run_time"
    payload["discovery"]["selection_log"] = [
        {
            "source_id": "arxiv:2305.03495",
            "decision": "include",
            "reason": "Direct evidence for textual-gradient prompt optimization.",
        },
        {
            "source_id": "arxiv:0000.00000",
            "decision": "exclude",
            "reason": "Outside the grading and skill-optimization scope.",
        },
    ]
    payload["discovery"]["selection_log_status"] = "recorded_at_run_time"
    return payload


def _audit_temporary_payload(payload: dict) -> list[str]:
    with tempfile.TemporaryDirectory() as temporary:
        manifest = Path(temporary) / "sci-brain-run.json"
        manifest.write_text(
            json.dumps(payload, indent=2) + "\n",
            encoding="utf-8",
        )
        return audit_research_records(manifest, repo_root=Path.cwd())


if __name__ == "__main__":
    unittest.main()
