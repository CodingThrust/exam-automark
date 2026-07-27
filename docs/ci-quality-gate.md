# GitHub Actions CI Quality Gate / GitHub Actions CI 质量门禁

## 中文

### 为什么要补 CI

在本地运行测试只能证明某一台电脑、某一个时刻通过。GitHub Actions
会在每个面向 `main` 的 PR 上重新执行同一组公开安全的检查，并把结果
显示为可要求通过的状态检查。这样，合并者可以是仓库所有者本人，也不
需要把审批人数设成 8；真正阻止有问题代码进入 `main` 的是“必须经 PR”
和“必须通过检查”。

CI 不能证明模型评分已经变准。它能防止的是已经被测试覆盖的功能、隐私
边界、封闭测试集门禁和调研来源链被代码修改悄悄破坏。

### 三个稳定检查

三项检查都属于 `CI` workflow；分支保护使用下表中的准确 context 名：

| 状态检查 | 内容 | 当前最低发现数 |
| --- | --- | ---: |
| `Core tests` | 核心评分、advisor workflow、报告与研究记录逻辑 | 218 |
| `Physics tests` | Physics benchmark、packet、privacy、评分流程 | 85 |
| `Safety and provenance gates` | 调研 manifest 审计，以及隐私、held-out 审批和 sealed-test 负向控制 | 不适用 |

`scripts/run_ci_tests.py` 先统计测试，再运行测试。如果路径写错导致发现
0 个测试，或者发现数低于已经审核过的基线，CI 会失败，而不是出现
“运行 0 个测试但显示绿色”的误报。需要有意删除或迁移测试时，应在同一个
PR 中解释原因并更新最低数。

### 数据与测试集边界

- Actions 只 checkout Git 中公开的代码、合成 fixture 和公开安全记录。
- 不上传 `Data/`、学生答卷、页面图片、原始模型响应、密钥或私有逐题分析。
- CI 验证“测试集在 freeze 前不可运行”“held-out 运行必须显式批准”
  等控制逻辑，但不会在公开 runner 上实际打开真实封闭测试集。
- 真实 sealed test 仍在私有环境运行；公开 PR 只提交匿名汇总和允许公开的
  证据。

所以“测试集也要覆盖”的正确含义是：自动检查测试集隔离和执行门禁，
而不是把真实测试集放进 GitHub Actions。

### 本地等价命令

```powershell
python -m pip install -e .
python scripts/run_ci_tests.py core
python scripts/run_ci_tests.py physics
python -m benchmark.core.research_records --manifest experiments/records/tooling-surveys/sources.json
python -m benchmark.core.research_records --manifest experiments/records/literature-surveys/sci_brain_run_manifest.json
```

### `main` 分支保护

1. 必须通过 PR 合并；
2. required approvals 保持为 `0`，因此仓库所有者可以合并自己的 PR；
3. 必须通过上面的三个稳定状态检查；
4. 必须解决所有 review conversation；
5. 禁止 force push 和删除分支；
6. 对管理员同样生效。

状态检查只有在 workflow 首次运行后才会出现在 GitHub 可选列表中。
PR #35 已实际跑出并通过三个准确 context；它们已绑定 GitHub Actions
app，并被设为 `main` 的 required status checks。

## English

### Why CI is needed

A local test run proves only that one machine passed at one moment. GitHub
Actions reruns the same public-safe checks for every pull request targeting
`main` and exposes the results as enforceable status checks. The repository
owner can still merge their own pull request and the required approval count
can remain zero. Protection comes from requiring a pull request and passing
checks, not from requiring all eight students to approve.

CI does not prove that model grading accuracy improved. It prevents changes
from silently breaking behavior already covered by tests, privacy boundaries,
sealed-test controls, and research provenance.

### Three stable checks

All three checks belong to the `CI` workflow. Branch protection uses the exact
contexts in the table:

| Status check | Coverage | Current discovery floor |
| --- | --- | ---: |
| `Core tests` | Core grading, advisor workflow, reporting, and research-record logic | 218 |
| `Physics tests` | Physics benchmark, packets, privacy, and grading flow | 85 |
| `Safety and provenance gates` | Manifest audits plus privacy, held-out approval, and sealed-test negative controls | N/A |

`scripts/run_ci_tests.py` counts tests before running them. A bad discovery
path that returns zero tests, or a count below the reviewed baseline, fails
instead of producing a false green result. An intentional test deletion or
move must explain and update the floor in the same pull request.

### Data and test-set boundary

- Actions checks out only committed public code, synthetic fixtures, and
  public-safe records.
- It does not upload `Data/`, student answers, page images, raw model
  responses, credentials, or private case-level analysis.
- CI verifies controls such as “the test split is blocked before freeze” and
  “held-out execution requires explicit approval”; it does not open the real
  sealed test set on a public runner.
- Real sealed-test execution remains in a private environment. Only approved,
  anonymized aggregate evidence may enter a public pull request.

“Cover the test set” therefore means automatically testing isolation and
execution gates, not publishing the real test set to GitHub Actions.

### Local equivalent

```powershell
python -m pip install -e .
python scripts/run_ci_tests.py core
python scripts/run_ci_tests.py physics
python -m benchmark.core.research_records --manifest experiments/records/tooling-surveys/sources.json
python -m benchmark.core.research_records --manifest experiments/records/literature-surveys/sci_brain_run_manifest.json
```

### `main` protection

1. Changes must enter through a pull request.
2. Required approvals remain `0`, so the owner can merge their own PR.
3. All three stable status checks are required.
4. Review conversations must be resolved.
5. Force pushes and branch deletion are disabled.
6. The rules apply to administrators.

GitHub exposes a check for branch protection only after the workflow has run
once. PR #35 produced and passed all three exact contexts. They are now bound
to the GitHub Actions app and required on `main`.
