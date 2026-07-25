# TASK3 Zulip 结算：quantum.harness / beginner-training

## 中文版

```text
Topic: [exam-automark] TASK3 - quantum.harness / beginner-training 借鉴说明

状态：
completed

对应导师安排：
上周遗留的 quantum.harness / beginner-training 调研解释。

目标：
讲清楚 quantum.harness 和 beginner-training 本身做了什么、exam-automark
实际借鉴了什么、哪些只是相似而不能声称为新增，并提供可选择的项目改进。

完成内容：
- 按 upstream commit 3bed20a166fe0228cf40b82d7d6dbd0a77014df1 重新核对
  README、AGENTS.md、beginner-training 五个 track 和 reproduce-paper skill。
- 修复原调研文件的乱码并重建可读报告。
- 将借鉴项分为已经实现、部分实现和尚未实现。
- 把每项已实现内容映射到 exam-automark 的实际代码或记录。
- 提出 A-E 五个改进选项，并给出收益、成本、风险和推荐顺序。

证据：
- experiments/records/tooling-surveys/quantum-harness-beginner-training.md
- experiments/knowledge/reproducible-ai-grading.md
- benchmark/core/manifests.py
- benchmark/core/plans.py
- benchmark/core/readiness.py
- benchmark/core/advisor_workflow.py

关键结果：
最值得迁移的不是量子物理工具链，而是结构化事实源、昂贵操作前的 readiness
gate、negative control、private/public 分层和 run-to-report provenance。

exam-automark 已经实现 experiment plan/record、packet/skill/data hash、readiness
check、Data/ 隔离和关键决策批准。Report lineage、required CI negative controls
和统一知识索引仍不完整。

发现的问题：
- 原报告没有固定 upstream commit，无法可靠识别上游入口变化。
- 原报告存在乱码，但测试没有发现。
- 现有本地 gate 尚未成为 main 的 required GitHub Actions check。
- 部分 Markdown/Typst/PDF 仍缺少机器可验证的 run-to-report lineage。

对项目的帮助：
防止从聊天记忆重建实验配置，减少跑完模型后才发现条件不匹配的浪费，并让
导师自动化流程只在安装、登录、私有数据、模型调用和 held-out 等关键边界
请求批准。

限制 / 禁止表述：
- 没有运行 quantum.harness 的量子模拟。
- 没有亲自完成 beginner-training 五条交互 track。
- 不能把所有现有 prompt packet/readiness 结构都声称为本次调研新建。
- A-E 改进选项尚未全部实现。

已接受的决策：
YY 选择 A+B+C，暂缓 D+E。
A 已在 TASK3 实现为 commit-pinned sources.json、UTF-8/乱码检查和 floating
GitHub main 检查；B 进入 TASK5；C 成为 TASK7 前置条件。

下一步：
验证 A 的 checker 和回归测试，创建中英双语 TASK3 draft PR；B 和 C 分别在
TASK5、TASK7 中实现。
```

---

## English version

```text
Topic: [exam-automark] TASK3 - quantum.harness / beginner-training lessons

Status:
completed

Advisor mapping:
Carry-over explanation for the earlier quantum.harness / beginner-training
review.

Goal:
Explain what quantum.harness and beginner-training do, identify what
exam-automark actually adopted, avoid claiming pre-existing similar structures
as new work, and present selectable project improvements.

What was done:
- Rechecked README, AGENTS.md, all five beginner-training tracks, and the
  reproduce-paper skill at upstream commit
  3bed20a166fe0228cf40b82d7d6dbd0a77014df1.
- Replaced the corrupted local survey with a readable report.
- Classified lessons as implemented, partially implemented, or not implemented.
- Mapped each implemented lesson to concrete exam-automark evidence.
- Proposed options A-E with benefits, costs, risks, and a recommended order.

Key result:
The transferable value is not the quantum-physics toolchain. It is the
structured source of truth, pre-compute readiness gates, negative controls,
private/public layering, and run-to-report provenance.

exam-automark already has experiment plans/records, packet/skill/data hashes,
readiness checks, Data/ isolation, and approval at consequential decision
boundaries. Report lineage, required CI negative controls, and a unified
knowledge index remain incomplete.

Problems found:
- The earlier report did not pin an upstream commit.
- The earlier report was corrupted by an encoding defect that tests missed.
- Local gates are not yet required GitHub Actions checks on main.
- Some Markdown/Typst/PDF artifacts lack machine-verifiable run-to-report
  lineage.

How this helps:
It prevents experiments from being reconstructed from chat memory, catches
non-comparable runs before model cost is incurred, and keeps advisor automation
interactive only at consequential installation, login, private-data, model-call,
and held-out boundaries.

Limitations / prohibited claims:
- No quantum simulation was run.
- The five interactive beginner-training tracks were not personally completed.
- Pre-existing packet/readiness structures are not all new outcomes of this
  review.
- Options A-E are not all implemented.

Accepted decision:
YY selected A+B+C and deferred D+E. A is implemented in TASK3 as a
commit-pinned sources.json manifest plus UTF-8/mojibake and floating-main
checks. B is assigned to TASK5. C is a prerequisite for TASK7.

Next action:
Validate the A checker and regression tests, then open the bilingual TASK3
draft PR. Implement B and C in TASK5 and TASK7 respectively.
```
