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
            self.assertIn("manifest.json", manifest["generated_files"])
            self.assertTrue((output_dir / "README.md").exists())
            self.assertTrue((output_dir / "env.deepseek.ps1").exists())
            self.assertTrue((output_dir / "env.deepseek.sh").exists())
            self.assertTrue((output_dir / "configs" / "physics_grading" / "deepseek.yaml").exists())
            self.assertTrue((output_dir / "commands.ps1").exists())
            self.assertTrue((output_dir / "commands.sh").exists())
            text = "\n".join(path.read_text(encoding="utf-8") for path in output_dir.rglob("*") if path.is_file())
            self.assertIn("Read-Host \"DeepSeek API key\"", text)
            self.assertIn("OPENAI_COMPATIBLE_BASE_URL", text)
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
