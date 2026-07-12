# Software Environment Snapshot

Status: pre-model-call snapshot.

Captured date: 2026-07-12, Asia/Shanghai.

This file records the local software state before any model call on
`codex/physics-week9-baseline-candidate-v2-run`.

## Git

- Branch: `codex/physics-week9-baseline-candidate-v2-run`
- Commit: `dc37556418fbe031a01ec649a7b730ebf9f89f39`
- Remote tracking branch:
  `origin/codex/physics-week9-baseline-candidate-v2-run`

## System Software

- OS via .NET: `Microsoft Windows NT 10.0.26200.0`
- OS via `cmd /c ver`: `Microsoft Windows [Version 10.0.26200.7840]`
- PowerShell: `5.1.26100.7705`
- Git: `2.54.0.windows.1`
- Python: `3.12.10`
- pip: `25.1.1 from D:\Miniforge\Lib\site-packages\pip (python 3.12)`
- Typst: `0.15.0 (3ae52774)`
- Typst executable:
  `C:\Users\袁翊\AppData\Local\Microsoft\WinGet\Packages\Typst.Typst_Microsoft.Winget.Source_8wekyb3d8bbwe\typst-x86_64-pc-windows-msvc\typst.exe`
- Typst PATH status: installed via WinGet, but `typst` is not discoverable on
  the current PowerShell `PATH`

## Python Packages Checked

| Package | Version |
| --- | --- |
| `openai` | `NOT_INSTALLED` |
| `Pillow` | `11.3.0` |
| `PyMuPDF` | `NOT_INSTALLED` |
| `zulip` | `NOT_INSTALLED` |
| `pandas` | `2.3.0` |
| `numpy` | `2.1.3` |

## Before Model Runs

Install or otherwise record:

- the API client package needed for the selected model provider
- `PyMuPDF` if this environment performs PDF/image conversion
- Typst `PATH` configuration, or the explicit executable path above, before
  compiling the final PDF report
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
