import json
import tempfile
import unittest
from pathlib import Path

from benchmark.core.skill_snapshots import (
    SkillSnapshot,
    build_skill_snapshot,
    write_skill_snapshot,
)


class SkillSnapshotTests(unittest.TestCase):
    def test_build_snapshot_normalizes_line_endings(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            agent = root / "agent.md"
            claude = root / "claude.md"
            agent.write_bytes(b"line one\nline two\n")
            claude.write_bytes(b"line one\r\nline two\r\n")

            snapshot = build_skill_snapshot(
                skill_version_id="skill_baseline_v1",
                source_paths={"agents": agent, "claude": claude},
            )

        self.assertTrue(snapshot.mirror_synchronized)
        self.assertEqual(snapshot.skill_hashes["agents"], snapshot.skill_hashes["claude"])

    def test_write_and_read_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "SKILL.md"
            source.write_text("skill text\n", encoding="utf-8")
            output = root / "snapshot.json"
            snapshot = build_skill_snapshot(
                skill_version_id="skill_baseline_v1",
                source_paths={"agents": source},
            )

            write_skill_snapshot(snapshot, output)
            loaded = SkillSnapshot.from_json_path(output)

        self.assertEqual(loaded.skill_version_id, "skill_baseline_v1")
        self.assertEqual(loaded.canonical_hash, snapshot.canonical_hash)

    def test_directory_snapshot_tracks_bundled_resources(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = root / "agent"
            second = root / "claude"
            for folder in (first, second):
                (folder / "scripts").mkdir(parents=True)
                (folder / "SKILL.md").write_text("skill\n", encoding="utf-8")
                (folder / "scripts" / "tool.py").write_text(
                    "print('ok')\n",
                    encoding="utf-8",
                )

            snapshot = build_skill_snapshot(
                skill_version_id="skill_candidate_v2",
                source_paths={"agents": first, "claude": second},
            )

        self.assertTrue(snapshot.mirror_synchronized)
        self.assertIn("directories", snapshot.hash_policy)

    def test_checked_in_baseline_snapshot_is_synchronized(self):
        snapshot = SkillSnapshot.from_json_path(
            Path("experiments/skill_versions/skill_baseline_v1.json")
        )

        self.assertEqual(snapshot.skill_version_id, "skill_baseline_v1")
        self.assertTrue(snapshot.mirror_synchronized)
        self.assertEqual(
            set(snapshot.skill_source_paths),
            {"agents", "claude"},
        )
        self.assertEqual(len(set(snapshot.skill_hashes.values())), 1)

    def test_current_skill_directories_match_candidate_v31_snapshot(self):
        snapshot_path = Path("experiments/skill_versions/skill_candidate_v3_1_r2.json")
        snapshot = SkillSnapshot.from_json_path(snapshot_path)
        rebuilt = build_skill_snapshot(
            skill_version_id=snapshot.skill_version_id,
            source_paths={
                label: Path(path)
                for label, path in snapshot.skill_source_paths.items()
            },
        )

        self.assertEqual(rebuilt.skill_hashes, snapshot.skill_hashes)
        self.assertTrue(snapshot.mirror_synchronized)

    def test_historical_candidate_v3_snapshot_remains_loadable_and_distinct(self):
        baseline = SkillSnapshot.from_json_path(
            Path("experiments/skill_versions/skill_baseline_v1.json")
        )
        candidate_v3 = SkillSnapshot.from_json_path(
            Path("experiments/skill_versions/skill_candidate_v3.json")
        )
        candidate_v31 = SkillSnapshot.from_json_path(
            Path("experiments/skill_versions/skill_candidate_v3_1.json")
        )
        candidate_v31_r2 = SkillSnapshot.from_json_path(
            Path("experiments/skill_versions/skill_candidate_v3_1_r2.json")
        )

        self.assertEqual(candidate_v3.skill_version_id, "skill_candidate_v3")
        self.assertTrue(candidate_v3.mirror_synchronized)
        self.assertEqual(len(set(candidate_v3.skill_hashes.values())), 1)
        self.assertNotEqual(candidate_v3.canonical_hash, baseline.canonical_hash)
        self.assertNotEqual(candidate_v3.canonical_hash, candidate_v31.canonical_hash)
        self.assertNotEqual(candidate_v3.canonical_hash, candidate_v31_r2.canonical_hash)

    def test_historical_candidate_v2_snapshot_remains_loadable_and_distinct(self):
        baseline = SkillSnapshot.from_json_path(
            Path("experiments/skill_versions/skill_baseline_v1.json")
        )
        candidate_v2 = SkillSnapshot.from_json_path(
            Path("experiments/skill_versions/skill_candidate_v2.json")
        )
        candidate_v3 = SkillSnapshot.from_json_path(
            Path("experiments/skill_versions/skill_candidate_v3.json")
        )
        candidate_v31 = SkillSnapshot.from_json_path(
            Path("experiments/skill_versions/skill_candidate_v3_1.json")
        )
        candidate_v31_r2 = SkillSnapshot.from_json_path(
            Path("experiments/skill_versions/skill_candidate_v3_1_r2.json")
        )

        self.assertEqual(candidate_v2.skill_version_id, "skill_candidate_v2")
        self.assertTrue(candidate_v2.mirror_synchronized)
        self.assertEqual(len(set(candidate_v2.skill_hashes.values())), 1)
        self.assertNotEqual(candidate_v2.canonical_hash, baseline.canonical_hash)
        self.assertNotEqual(candidate_v2.canonical_hash, candidate_v3.canonical_hash)
        self.assertNotEqual(candidate_v2.canonical_hash, candidate_v31.canonical_hash)
        self.assertNotEqual(candidate_v2.canonical_hash, candidate_v31_r2.canonical_hash)

    def test_candidate_v31_snapshot_differs_from_baseline(self):
        baseline = SkillSnapshot.from_json_path(
            Path("experiments/skill_versions/skill_baseline_v1.json")
        )
        candidate = SkillSnapshot.from_json_path(
            Path("experiments/skill_versions/skill_candidate_v3_1_r2.json")
        )

        self.assertNotEqual(candidate.canonical_hash, baseline.canonical_hash)


if __name__ == "__main__":
    unittest.main()
