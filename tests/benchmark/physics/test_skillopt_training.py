import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from benchmark.physics.cli import main
from benchmark.physics.skillopt_training import build_deepseek_training_package


class SkillOptDeepSeekTrainingPackageTests(unittest.TestCase):
    def test_builds_deepseek_training_package_without_api_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            split_dir = root / "skillopt_split"
            split_dir.mkdir()
            output_dir = root / "deepseek_package"
            (output_dir / "outputs" / "old-run").mkdir(parents=True)
            (output_dir / "outputs" / "old-run" / "result.json").write_text(
                "{}",
                encoding="utf-8",
            )
            (output_dir / "preflight" / "old-run").mkdir(parents=True)
            (output_dir / "preflight" / "old-run" / "raw_response.txt").write_text(
                "private model output",
                encoding="utf-8",
            )

            manifest = build_deepseek_training_package(
                split_dir=split_dir,
                output_dir=output_dir,
                exam_automark_root=root / "exam-automark",
                skillopt_root=root / "SkillOpt",
                model="deepseek-v4-pro",
                base_url="https://api.deepseek.com",
            )

            self.assertEqual(
                manifest["record_type"],
                "physics_skillopt_deepseek_training_package",
            )
            self.assertEqual(manifest["model"], "deepseek-v4-pro")
            self.assertEqual(manifest["target_max_tokens"], 12000)
            self.assertEqual(manifest["target_timeout_seconds"], 240)
            self.assertIn("manifest.json", manifest["generated_files"])
            self.assertTrue((output_dir / "README.md").exists())
            self.assertTrue((output_dir / "env.deepseek.ps1").exists())
            self.assertTrue((output_dir / "env.deepseek.sh").exists())
            self.assertTrue((output_dir / "configs" / "_base_" / "default.yaml").exists())
            self.assertTrue((output_dir / "configs" / "physics_grading" / "deepseek.yaml").exists())
            self.assertTrue((output_dir / "commands.ps1").exists())
            self.assertTrue((output_dir / "commands.sh").exists())
            generated = set(manifest["generated_files"])
            self.assertIn("configs/_base_/default.yaml", generated)
            self.assertNotIn("outputs/old-run/result.json", generated)
            self.assertNotIn("preflight/old-run/raw_response.txt", generated)
            text = "\n".join(path.read_text(encoding="utf-8") for path in output_dir.rglob("*") if path.is_file())
            self.assertIn("Read-Host \"DeepSeek API key\"", text)
            self.assertIn("OPENAI_COMPATIBLE_BASE_URL", text)
            self.assertIn('OPENAI_COMPATIBLE_MAX_TOKENS = "12000"', text)
            self.assertIn('OPENAI_COMPATIBLE_TIMEOUT_SECONDS = "240"', text)
            self.assertIn("env.max_completion_tokens=12000", text)
            self.assertIn("env.exec_timeout=240", text)
            self.assertIn("max_completion_tokens: 12000", text)
            self.assertIn("PYTHONUTF8", text)
            self.assertIn("model.optimizer_backend=openai_compatible", text)
            self.assertNotIn("sk-", text)

    def test_cli_builds_deepseek_training_package(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            split_dir = root / "skillopt_split"
            split_dir.mkdir()
            output_dir = root / "deepseek_package"

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                code = main(
                    [
                        "skillopt-deepseek-package",
                        "--split-dir",
                        str(split_dir),
                        "--output-dir",
                        str(output_dir),
                        "--exam-automark-root",
                        str(root / "exam-automark"),
                        "--skillopt-root",
                        str(root / "SkillOpt"),
                    ]
                )

            self.assertEqual(code, 0)
            result = json.loads(stdout.getvalue())
            self.assertEqual(
                result["record_type"],
                "physics_skillopt_deepseek_training_package",
            )
            self.assertTrue((output_dir / "manifest.json").exists())


if __name__ == "__main__":
    unittest.main()
