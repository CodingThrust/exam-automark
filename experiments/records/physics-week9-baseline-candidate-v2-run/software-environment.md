# Software Environment Snapshot

Status: pre-model-call preflight snapshot.

Captured date: 2026-07-12, Asia/Shanghai.

This file records the local software state before any model call on
`codex/physics-week9-baseline-candidate-v2-run`.

## Git

- Branch: `codex/physics-week9-baseline-candidate-v2-run`
- Commit: `93f843f405df5cbf4d4d4cd1524c77a153121959`
- Remote tracking branch:
  `origin/codex/physics-week9-baseline-candidate-v2-run`

## System Software

- OS: `Microsoft Windows 11 Professional`, version `10.0.26200`,
  build `26200`, `64-bit`
- OS via .NET: `Microsoft Windows NT 10.0.26200.0`
- OS via `cmd /c ver`: `Microsoft Windows [Version 10.0.26200.7840]`
- PowerShell: `5.1.26100.7705`
- Git: `2.54.0.windows.1`
- Python: `3.12.10`
- pip: `25.1.1 from D:\Miniforge\Lib\site-packages\pip (python 3.12)`
- Typst: `0.15.0 (3ae52774)`
- Typst executable: `C:\Tools\typst\typst.exe`
- Typst PATH status: `C:\Tools\typst` has been added to the user `PATH`;
  reopen PowerShell/Codex sessions to refresh existing process environments

## Python Packages Checked

| Package | Version |
| --- | --- |
| `openai` | `NOT_INSTALLED` |
| `Pillow` | `11.3.0` |
| `PyMuPDF` | `NOT_INSTALLED` |
| `zulip` | `NOT_INSTALLED` |
| `pandas` | `2.3.0` |
| `numpy` | `2.1.3` |

## Provider Configuration

- Provider: `deepseek`
- API client: OpenAI-compatible Python SDK
- API key source: `DEEPSEEK_API_KEY` environment variable
- API key status in current Codex/PowerShell process: `NOT_SET`
- Planned model for real dev run: `deepseek-v4-pro`
- Real API calls recorded in this snapshot: `false`

The user reported that a DeepSeek API key is prepared. The key value must not be
written into commands, files, Git commits, or reports.

## Before Model Runs

Install or otherwise record:

- `openai` for the OpenAI-compatible DeepSeek API client
- `DEEPSEEK_API_KEY` visible in the process environment
- `PyMuPDF` if this environment performs PDF/image conversion
- exact provider/model/version metadata for every model run

The final model-run record should capture a fresh environment snapshot at the
exact run commit.

## Language Policy

All model-facing rubrics must be English.

This includes:

- rubric criteria
- scoring rules
- partial-credit rules
- prompt instructions
- model-facing evidence/feedback requirements

If a source solution or teacher note is not English, translate it into an
English rubric before packet construction, then freeze and hash that rubric. If
translation changes any scoring meaning, stop and ask the teacher before running
models.
