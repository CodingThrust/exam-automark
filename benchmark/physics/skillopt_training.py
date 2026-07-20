import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEFAULT_DEEPSEEK_MODEL = "deepseek-v4-pro"


def build_deepseek_training_package(
    *,
    split_dir: Path,
    output_dir: Path,
    exam_automark_root: Path,
    skillopt_root: Path,
    model: str = DEFAULT_DEEPSEEK_MODEL,
    base_url: str = DEFAULT_DEEPSEEK_BASE_URL,
    run_name: str = "physics-week9-deepseek-skillopt-r1",
) -> dict[str, Any]:
    """Write a no-secret DeepSeek SkillOpt training package."""
    split_dir = _absolute_path(split_dir)
    output_dir = _absolute_path(output_dir)
    exam_automark_root = _absolute_path(exam_automark_root)
    skillopt_root = _absolute_path(skillopt_root)
    output_dir.mkdir(parents=True, exist_ok=True)
    config_path = output_dir / "configs" / "physics_grading" / "deepseek.yaml"
    files = {
        "README.md": _readme(
            split_dir=split_dir,
            output_dir=output_dir,
            exam_automark_root=exam_automark_root,
            skillopt_root=skillopt_root,
            model=model,
            base_url=base_url,
            run_name=run_name,
        ),
        "env.deepseek.ps1": _powershell_env(base_url=base_url, model=model),
        "env.deepseek.sh": _shell_env(base_url=base_url, model=model),
        "commands.ps1": _powershell_commands(
            skillopt_root=skillopt_root,
            output_dir=output_dir,
            config_path=config_path,
            run_name=run_name,
            model=model,
        ),
        "commands.sh": _shell_commands(
            skillopt_root=skillopt_root,
            output_dir=output_dir,
            config_path=config_path,
            run_name=run_name,
            model=model,
        ),
        "expected-return-files.md": _expected_return_files(run_name=run_name),
    }
    for relative, text in files.items():
        path = output_dir / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")

    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        _deepseek_yaml(
            split_dir=split_dir,
            skillopt_root=skillopt_root,
            model=model,
        ),
        encoding="utf-8",
        newline="\n",
    )
    generated_files = sorted(
        str(path.relative_to(output_dir))
        for path in output_dir.rglob("*")
        if path.is_file()
    )
    if "manifest.json" not in generated_files:
        generated_files.append("manifest.json")
    manifest = {
        "record_type": "physics_skillopt_deepseek_training_package",
        "generated_at": _utc_now(),
        "base_url": base_url,
        "model": model,
        "run_name": run_name,
        "split_dir": str(split_dir),
        "output_dir": str(output_dir),
        "exam_automark_root": str(exam_automark_root),
        "skillopt_root": str(skillopt_root),
        "contains_api_key": False,
        "training_invokes_model_api": True,
        "generated_files": sorted(generated_files),
    }
    _write_json(output_dir / "manifest.json", manifest)
    return manifest


def _deepseek_yaml(*, split_dir: Path, skillopt_root: Path, model: str) -> str:
    initial_skill = skillopt_root / "skillopt" / "envs" / "physics_grading" / "skills" / "initial.md"
    return f"""_base_: ../_base_/default.yaml

model:
  optimizer_backend: openai_compatible
  target_backend: openai_compatible
  optimizer: {model}
  target: {model}
  reasoning_effort: medium

train:
  batch_size: 4
  accumulation: 1
  num_epochs: 1

gradient:
  minibatch_size: 4
  merge_batch_size: 4
  analyst_workers: 2

optimizer:
  learning_rate: 2
  use_slow_update: false
  use_meta_skill: false

evaluation:
  use_gate: true

env:
  name: physics_grading
  skill_init: {initial_skill.as_posix()}
  split_mode: split_dir
  split_dir: {split_dir.as_posix()}
  workers: 1
  max_completion_tokens: 4096
  limit: 0
"""


def _powershell_env(*, base_url: str, model: str) -> str:
    return f"""# Load DeepSeek credentials for SkillOpt OpenAI-compatible backend.
# This file intentionally does not store your API key.
$secure = Read-Host "DeepSeek API key" -AsSecureString
$bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
try {{
  $env:OPENAI_COMPATIBLE_API_KEY = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
}} finally {{
  [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
}}

$env:OPENAI_COMPATIBLE_BASE_URL = "{base_url}"
$env:OPENAI_COMPATIBLE_MODEL = "{model}"
$env:OPENAI_COMPATIBLE_TEMPERATURE = "0"
$env:OPENAI_COMPATIBLE_MAX_TOKENS = "4096"
$env:OPENAI_COMPATIBLE_TIMEOUT_SECONDS = "120"
"""


def _shell_env(*, base_url: str, model: str) -> str:
    return f"""#!/usr/bin/env bash
set -euo pipefail

read -rsp "DeepSeek API key: " OPENAI_COMPATIBLE_API_KEY
echo
export OPENAI_COMPATIBLE_API_KEY
export OPENAI_COMPATIBLE_BASE_URL="{base_url}"
export OPENAI_COMPATIBLE_MODEL="{model}"
export OPENAI_COMPATIBLE_TEMPERATURE="0"
export OPENAI_COMPATIBLE_MAX_TOKENS="4096"
export OPENAI_COMPATIBLE_TIMEOUT_SECONDS="120"
"""


def _powershell_commands(
    *,
    skillopt_root: Path,
    output_dir: Path,
    config_path: Path,
    run_name: str,
    model: str,
) -> str:
    out_root = output_dir / "outputs" / run_name
    return f"""Set-Location "{skillopt_root}"

# One-time setup, source install from main is recommended for openai_compatible.
# git clone https://github.com/microsoft/SkillOpt.git "{skillopt_root}"
# python -m pip install -e .

. "{output_dir / 'env.deepseek.ps1'}"

python scripts/train.py `
  --config "{config_path}" `
  --out_root "{out_root}" `
  --cfg-options `
  model.optimizer_backend=openai_compatible `
  model.target_backend=openai_compatible `
  model.optimizer={model} `
  model.target={model}

$exit = $LASTEXITCODE
Remove-Item Env:OPENAI_COMPATIBLE_API_KEY -ErrorAction SilentlyContinue
"SkillOpt DeepSeek training exit=$exit"
exit $exit
"""


def _shell_commands(
    *,
    skillopt_root: Path,
    output_dir: Path,
    config_path: Path,
    run_name: str,
    model: str,
) -> str:
    out_root = output_dir / "outputs" / run_name
    return f"""#!/usr/bin/env bash
set -euo pipefail

cd "{skillopt_root.as_posix()}"

# One-time setup, source install from main is recommended for openai_compatible.
# git clone https://github.com/microsoft/SkillOpt.git "{skillopt_root.as_posix()}"
# python -m pip install -e .

source "{(output_dir / 'env.deepseek.sh').as_posix()}"

python scripts/train.py \\
  --config "{config_path.as_posix()}" \\
  --out_root "{out_root.as_posix()}" \\
  --cfg-options \\
  model.optimizer_backend=openai_compatible \\
  model.target_backend=openai_compatible \\
  model.optimizer={model} \\
  model.target={model}

status=$?
unset OPENAI_COMPATIBLE_API_KEY
echo "SkillOpt DeepSeek training exit=$status"
exit "$status"
"""


def _readme(
    *,
    split_dir: Path,
    output_dir: Path,
    exam_automark_root: Path,
    skillopt_root: Path,
    model: str,
    base_url: str,
    run_name: str,
) -> str:
    return f"""# Physics SkillOpt DeepSeek Training Package

This package prepares the first real SkillOpt training run for the physics week 9
text-only grading benchmark.

It uses the SkillOpt `openai_compatible` backend for both optimizer and target
roles, with DeepSeek as the provider.

## Inputs

- Exam repo: `{exam_automark_root}`
- SkillOpt source checkout: `{skillopt_root}`
- Split directory: `{split_dir}`
- Model: `{model}`
- Base URL: `{base_url}`

## Run

PowerShell:

```powershell
Set-Location "{skillopt_root}"
{output_dir / 'commands.ps1'}
```

macOS/Linux:

```bash
cd "{skillopt_root.as_posix()}"
bash "{(output_dir / 'commands.sh').as_posix()}"
```

## Important

- This package does not contain an API key.
- Running `commands.ps1` or `commands.sh` will call the DeepSeek API and may cost money.
- Use SkillOpt source install from `main`; the generic `openai_compatible` research backend may not be available in older PyPI releases.
- Do not use `test/items.json` for SkillOpt candidate selection. It is only for final evaluation after a best skill has been selected.

## Expected Outputs

The SkillOpt run should produce files under:

```text
{(output_dir / 'outputs' / run_name).as_posix()}
```

Return `best_skill.md`, `history.json`, `config.json`, and the exact terminal
command/output summary to exam-automark for evaluation.
"""


def _expected_return_files(*, run_name: str) -> str:
    return f"""# Expected Return Files

After running SkillOpt, collect:

- `outputs/{run_name}/best_skill.md`
- `outputs/{run_name}/history.json`
- `outputs/{run_name}/config.json`
- `outputs/{run_name}/metrics.json` if SkillOpt writes one
- exact command line
- terminal summary including exit code

Do not send raw API keys. Do not put the returned run outputs into GitHub unless
they have been reviewed for private transcript leakage.
"""


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _absolute_path(path: Path) -> Path:
    if path.is_absolute():
        return path
    return Path.cwd() / path
