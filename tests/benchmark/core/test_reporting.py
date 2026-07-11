import json
import tempfile
import unittest
from pathlib import Path

from benchmark.core.manifests import ExperimentRecord, write_record
from benchmark.core.reporting import render_typst_note, write_typst_note


DIGEST_A = "a" * 64
DIGEST_B = "b" * 64
FIXTURES = Path(__file__).parents[2] / "fixtures" / "synthetic"


class ReportingTests(unittest.TestCase):
    def _record(self) -> ExperimentRecord:
        return ExperimentRecord(
            experiment_id="2026-07-11-synthetic",
            course_id="dsaa3073",
            assessment_id="hw1",
            git_branch="codex/repro-experiment-framework",
            git_commit="abc1234",
            data_snapshot_hash=DIGEST_A,
            prompt_packet_hashes={"G2": DIGEST_B},
            conditions=("G2",),
            metrics_path="tests/fixtures/synthetic/metrics_dsaa3073_hw1.json",
            note_path="experiments/records/2026-07-11-synthetic/note.typ",
            notes=("synthetic fixture only",),
        )

    def test_render_typst_note_includes_packets_metrics_and_commands(self):
        metrics = json.loads(
            (FIXTURES / "metrics_dsaa3073_hw1.json").read_text(encoding="utf-8")
        )

        note = render_typst_note(self._record(), metrics=metrics)
        normalized = " ".join(note.split())

        self.assertIn("dsaa3073 hw1 Reproducibility Note", note)
        self.assertIn("Reading guide", note)
        self.assertIn("@preview/cetz:0.5.2", note)
        self.assertIn("What Is Being Reproduced", note)
        self.assertIn("Key Findings", note)
        self.assertIn("Prompt Packet Registry", note)
        self.assertIn("bbbbbbbbbbbb...", note)
        self.assertIn("Results At A Glance", note)
        self.assertIn("Accuracy vs severe-error risk", note)
        self.assertIn("Transcript-path delta", note)
        self.assertIn("Question-level agreement heatmap", note)
        self.assertIn("Condition Details", note)
        self.assertIn("G2", note)
        self.assertIn("75.0%", note)
        self.assertIn("Best exact", note)
        self.assertIn("highest exact-agreement condition", note)
        self.assertIn("python -m benchmark.core.cli audit-packet", note)
        self.assertIn("reference scores are single-primary-rater", normalized)

    def test_write_typst_note_loads_record_and_metrics(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            record_path = root / "experiment.json"
            metrics_path = root / "metrics.json"
            output_path = root / "note.typ"
            write_record(self._record(), record_path)
            metrics_path.write_text(
                (FIXTURES / "metrics_dsaa3073_hw1.json").read_text(encoding="utf-8"),
                encoding="utf-8",
            )

            written = write_typst_note(
                record_path,
                output_path,
                metrics_path=metrics_path,
                title="Synthetic DSAA3073 Note",
            )

            text = written.read_text(encoding="utf-8")

        self.assertEqual(written, output_path)
        self.assertIn("Synthetic DSAA3073 Note", text)
        self.assertIn("Lowest-agreement questions", text)
        self.assertIn("Reproducibility Anchors", text)

    def test_physics_pilot_note_renders_pilot_caveat(self):
        record = ExperimentRecord.from_json_path(
            Path("experiments/records/physics-week9-pilot/experiment.json")
        )

        note = render_typst_note(record)

        self.assertIn("Pilot record", note)
        self.assertIn("must not be generalized", note)


if __name__ == "__main__":
    unittest.main()
