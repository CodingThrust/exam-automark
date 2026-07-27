# TASK5 Zulip 结算稿 / TASK5 Zulip Settlement Draft

> 状态：已准备，尚未实际发送到 Zulip。
> Status: prepared, not yet posted to Zulip.
>
> PR: https://github.com/CodingThrust/exam-automark/pull/35

## 中文

### 目标

为 `main` 增加可执行、公开安全、不会“0 tests 假绿”的 GitHub Actions
质量门禁，同时保留仓库所有者合并自己 PR 的能力。

### 做了什么

- 增加 `CI / Core tests`，运行至少 218 个 core 测试；
- 增加 `CI / Physics tests`，运行至少 85 个 Physics 测试；
- 增加 `CI / Safety and provenance gates`，单独执行调研记录审计、
  privacy、held-out approval 和 sealed-test 负向控制；
- 增加测试发现数门禁，避免错误的 discovery 路径运行 0 个测试仍显示成功；
- 首次 Ubuntu CI 暴露了目录哈希排序依赖操作系统的问题；现已固定为
  case-folded POSIX 相对路径顺序，并增加跨平台回归测试，同时保留历史
  实验记录引用的 canonical hash；
- 记录公开 CI 与真实私有 sealed test 的数据边界；
- 计划在本 PR 首次跑出准确 check context 后，把三个检查设为 `main`
  required status checks，审批人数保持 0。

### 改善了什么

以前是否运行测试依赖提交者本地操作，GitHub 合并页面没有自动证据。
现在每个面向 `main` 的 PR 都会在干净环境中复现检查，且关键安全控制
有独立、可见的状态。

### 如何帮助项目

它缩短了发现回归的时间，防止隐私、测试集隔离和调研来源链被无意破坏，
也让导师或仓库所有者可以在不等待 8 人审批的情况下，依据自动检查安全
地合并自己的 PR。

### 限制与禁止声明

- CI 通过不代表模型评分 accuracy 提高；
- CI 不运行真实 Kimi、Claude、Codex 或 DeepSeek API；
- CI 不接触真实学生答卷或 sealed test 内容；
- 公开 runner 只验证 sealed-test 执行门禁，真实测试集仍必须在私有环境运行；
- 本文是可粘贴到 Zulip 的草稿，当前环境没有 Zulip connector，因此尚未发送。

### 下一步

让 PR 跑出并通过三个检查，确认 GitHub 显示的准确 context 名，然后把它们
设为 `main` 的 required status checks。

## English

### Goal

Add an executable, public-safe GitHub Actions quality gate for `main` that
cannot turn green after discovering zero tests, while preserving the
repository owner's ability to merge their own pull requests.

### What was done

- Added `CI / Core tests` with a floor of 218 discovered core tests.
- Added `CI / Physics tests` with a floor of 85 discovered Physics tests.
- Added `CI / Safety and provenance gates` for research-record audits plus
  privacy, held-out approval, and sealed-test negative controls.
- Added a discovery-count gate so a wrong path cannot run zero tests and pass.
- The first Ubuntu run exposed platform-dependent directory-hash ordering. The
  implementation now uses case-folded POSIX relative-path order and has a
  cross-platform regression test while preserving the canonical hash cited by
  historical experiment records.
- Documented the boundary between public CI and the real private sealed test.
- Planned to require the three exact status contexts on `main` after this pull
  request produces them once; required approvals remain zero.

### What improved

Previously, test execution depended on each contributor's local behavior and
the GitHub merge page had no automatic evidence. Every pull request targeting
`main` now reproduces the checks in a clean environment, with critical safety
controls exposed as a separate visible status.

### How this helps the project

It shortens regression detection, protects privacy, test-set isolation, and
research provenance, and lets the advisor or repository owner safely merge
their own pull request based on automated checks without waiting for eight
approvals.

### Limitations and prohibited claims

- Passing CI does not mean model grading accuracy improved.
- CI does not call the real Kimi, Claude, Codex, or DeepSeek APIs.
- CI does not access real student work or sealed-test content.
- A public runner verifies sealed-test execution controls only; real held-out
  evaluation must remain in a private environment.
- This is a Zulip-ready draft. No Zulip connector is available in the current
  environment, so it has not been posted.

### Next

Run and pass the three checks on the pull request, confirm their exact GitHub
context names, and then require those contexts on `main`.
