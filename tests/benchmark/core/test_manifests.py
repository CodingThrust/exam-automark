import json
import tempfile
import unittest
from pathlib import Path

from benchmark.core.manifests import (
    ExperimentRecord,
    stable_json_digest,
    write_record,
)


DIGEST_A = "a" * 64
DIGEST_B = "b" * 64


class ManifestTests(unittest.TestCase):
    def test_experiment_record_round_trips_as_reproducibility_manifest(self):
        record = ExperimentRecord(
            experiment_id="2026-07-10-synthetic",
            course_id="dsaa3073",
            assessment_id="hw1",
            git_branch="codex/repro-experiment-framework",
            git_commit="abc1234",
            data_snapshot_hash=DIGEST_A,
            prompt_packet_hashes={"T1": DIGEST_B},
            conditions=("T1",),
            metrics_path="metrics.json",
            note_path="note.typ",
            report_pdf_path="note.pdf",
            notes=("synthetic fixture only",),
        )

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "experiment.json"
            write_record(record, path)

            loaded = ExperimentRecord.from_json_path(path)
            payload = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(loaded, record)
        self.assertEqual(payload["conditions"], ["T1"])

    def test_requires_prompt_hash_for_every_condition(self):
        with self.assertRaisesRegex(ValueError, "prompt packet hash missing"):
            ExperimentRecord(
                experiment_id="missing-prompt",
                course_id="physics",
                assessment_id="week9",
                git_branch="main",
                git_commit="abc1234",
                data_snapshot_hash=DIGEST_A,
                prompt_packet_hashes={"T1": DIGEST_B},
                conditions=("T1", "G2"),
                metrics_path="metrics.json",
                note_path="note.typ",
            )

    def test_stable_json_digest_is_key_order_independent(self):
        first = stable_json_digest({"b": 2, "a": [1, 2]})
        second = stable_json_digest({"a": [1, 2], "b": 2})

        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
