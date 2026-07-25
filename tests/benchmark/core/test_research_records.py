import json
import tempfile
import unittest
from pathlib import Path

from benchmark.core.research_records import audit_research_records


SOURCE_REPOSITORY = "https://github.com/example/research-harness"
SOURCE_COMMIT = "0123456789abcdef0123456789abcdef01234567"


class ResearchRecordAuditTests(unittest.TestCase):
    def test_committed_tooling_survey_manifest_passes(self):
        findings = audit_research_records(
            Path("experiments/records/tooling-surveys/sources.json")
        )

        self.assertEqual(findings, [])

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


if __name__ == "__main__":
    unittest.main()
