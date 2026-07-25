# quantum.harness / beginner-training：我们实际借鉴了什么

Date: 2026-07-25

Upstream repository: <https://github.com/QuantumBFS/quantum.harness>

Upstream snapshot checked for this report:
`3bed20a166fe0228cf40b82d7d6dbd0a77014df1`

## 直接结论

导师让我们看 `quantum.harness`，真正值得借鉴的不是量子物理代码，也不是
Julia、Slurm 或某一种数值算法，而是它如何约束 AI agent 完成可复现实验：

1. 用结构化文件保存事实，不依赖聊天记忆；
2. 在昂贵或有风险的操作前设置 readiness gate；
3. 把 workflow skill、领域知识、运行结果和报告分层；
4. 用 negative control 证明检查真的能拦截错误；
5. 让每个报告中的数字都能追溯到一次具体运行；
6. 在关键决策处让用户确认，但不把稳定的内部步骤都变成人工操作。

我们已经把其中一部分思想落实到了 `exam-automark`，尤其是 experiment
plan/record、prompt packet hash、readiness check、`Data/` 隔离、skill version
hash、运行元数据和派生报告。它们不是全部由这次调研从零创造的：部分结构在
调研前已经存在。更准确的说法是，`quantum.harness` 帮助我们把这些零散做法
整理成了一套明确的可复现实验原则，并推动了后续 gate 和记录字段的完善。

目前仍缺少三项关键能力：

- 对外部调研来源固定 commit，并自动检查调研记录是否过期或乱码；
- 在 CI 中持续运行 negative controls，证明 privacy/readiness/report gate
  仍然有用；
- 用统一 lineage contract 证明报告确实由指定 run/metrics 生成，而不是被
  人工修改成第二套事实。

## 本次调研范围和上游变化

本报告阅读并核对了当前上游的：

- `README.md`
- `AGENTS.md`
- `skills/beginner-training/SKILL.md`
- beginner-training 的五个 track
- `skills/reproduce-paper/SKILL.md`

需要特别记录一个上游变化：当前 snapshot 的 README 已将快速入口写成
`/track-starter`，但 `skills/beginner-training/` 仍存在，并保留五条
confirm-gated 教学路线。此前本地调研只记录了分支和日期，没有固定 upstream
commit，而且文件出现了编码乱码。这说明“记录来源版本”和“检查文档可读性”
本身就是可复现调研的一部分。

本报告不声称运行过量子模拟，也不声称亲自完成了 beginner-training 的五条
交互训练。这里分析的是它的系统设计和对 AI 阅卷项目的适用性。

## quantum.harness 到底是什么

这里的 harness 可以理解为“实验护栏系统”，而不是一个万能程序。

普通脚本关注“命令能不能运行”。Harness 还需要回答：

- 这次运行到底用了哪个问题设置？
- 哪个输入、模型、skill、prompt 和代码版本参与了运行？
- 哪些参数是来源明确的事实，哪些是用户选择？
- 运行前做过哪些检查？
- 怎样证明检查不是只会通过的装饰？
- 结果如何被验证？
- 报告中的数字能否追溯回运行产物？

`quantum.harness` 把内容分成四层：

| 层 | 作用 | AI 阅卷中的对应物 |
| --- | --- | --- |
| Knowledge cards | 保存可复用的领域事实、约定和证据来源 | course spec、rubric、错误类型、评分政策 |
| Skills | 保存跨任务复用的工作流程和决策规则 | grading skill、advisor run/submit skill、PR review skill |
| Run records | 保存一次实验的参数、输入和结果锚点 | plan、manifest、run metadata、metrics |
| Reports | 给人阅读的派生结果 | Markdown、Typst、PDF、PR 结算 |

最重要的边界是：skill 不应硬编码会变化的领域事实；report 也不应成为新的
事实源。事实变化应该修改上游结构化记录，再重新生成报告。

## beginner-training 在做什么

`beginner-training` 不是批处理脚本，而是教学 launcher。它先让学习者选择
track，再要求每一步都遵循同一个 Teaching Protocol：

1. 说明当前是第几步；
2. 用初学者能理解的语言解释将发生什么；
3. 解释这一步为什么重要；
4. 展示准确命令和正确结果应有的形状；
5. 等学习者确认；
6. 执行并解释真实输出；
7. 最后运行 checkpoint。

它的五条 track 是：

| Track | 学习内容 | 最终可信度检查 |
| --- | --- | --- |
| 1. Setup check | 检查 skills、PDF 工具、Julia 和 GitHub CLI | 故意导入不存在的包，证明 availability check 能失败 |
| 2. Reproduce a paper | 从论文设置到复现图和 self-check | 故意使用错误 sector/boundary，观察结果或检查失败 |
| 3. Literature survey | 下载真实文献、建索引、做主题调研 | 假 arXiv ID 必须失败；索引数必须匹配真实文件 |
| 4. Develop code | issue → design → plan → test → review → PR | PR、CI 和 self-review record 都必须存在 |
| 5. Go beyond | 在已复现结果上提出小型扩展研究 | 报告无 placeholder，每个数字可追溯到 script/data |

它真正训练的不是记住五组命令，而是形成三个习惯：

- 先确认问题和环境，再运行；
- 不只看“成功”，还要证明错误输入会失败；
- 产物必须能被另一个人复核。

## 我们已经实际借鉴的内容

下表区分“已经实现”“部分实现”和“尚未实现”。证据路径指向当前项目中的
实际文件，避免把相似概念当成已经完成。

| quantum.harness 思想 | exam-automark 中的实际落地 | 状态 | 对项目的帮助 |
| --- | --- | --- | --- |
| `run.json` 是一次运行的事实源 | `ExperimentPlan`、`ExperimentRecord`、packet `manifest.json` 保存 commit、data snapshot、prompt/skill hash 和 condition | 已实现 | 不再从聊天记录猜实验配置 |
| Compute 前确认 consequential setup | readiness 检查比较 course、assessment、split、data snapshot、rubric、prompt、skill 和 Git anchor | 已实现 | 避免 baseline/candidate 使用不同输入却被错误比较 |
| Skills 与 knowledge 分离 | `.agents/.claude` skills 保存流程；course specs、rubric、skill snapshots 保存结构化内容 | 部分实现 | workflow 可以跨课程复用，但知识层仍较分散 |
| Raw/private 与 public artifact 分离 | `.gitignore` 隔离 `Data/`、`.private-data/`；public PR 只允许 aggregate record | 已实现 | 降低学生数据和凭据泄露风险 |
| Negative control 证明 gate 有效 | readiness/privacy/packet 测试包含已知错误 fixture；advisor workflow 有 dry-run 和安全拒绝 | 部分实现 | 已有测试，但尚未成为 main 的 required GitHub Actions check |
| Report 从结构化结果派生 | metrics JSON 生成 Markdown/Typst/PDF；advisor workflow 从 aggregate allowlist 生成报告 | 部分实现 | 大部分报告可追溯，但并非所有 Markdown/PDF 都能自动重建和比对 |
| 每个数字带 provenance | data、prompt、packet、skill hash 和 run commit 已进入计划/记录 | 部分实现 | 能定位运行版本；错误解释和调研结论还缺统一 provenance schema |
| 关键决策 confirm-gated | advisor skill 在安装/登录、私有数据恢复、模型 probe、真实学生数据和 held-out 前请求批准 | 已实现且做了适配 | 保留高风险决策权，同时自动运行稳定步骤 |
| 分阶段 onboarding | advisor skill 有 doctor → probe → plan → prepare → run → package → submit | 部分实现 | 已有阶段化自动流程，但还不是面向教师的教学 track |
| 写完结果后做 integrity checkpoint | privacy scan、schema validation、students passed/expected、immutable retry、draft PR | 已实现 | 失败也会留下记录，不只保留成功实验 |

主要证据：

- `experiments/knowledge/reproducible-ai-grading.md`
- `benchmark/core/manifests.py`
- `benchmark/core/plans.py`
- `benchmark/core/readiness.py`
- `benchmark/core/advisor_workflow.py`
- `.agents/skills/run-submit-grading-benchmark/SKILL.md`
- `.agents/skills/review-experiment-pr/SKILL.md`
- `.gitignore`

其中 `experiments/knowledge/reproducible-ai-grading.md` 明确记录了三项直接采用的
原则：单一结构化事实源、昂贵模型调用前的 cheap gate、从记录事实生成报告。
其他相似结构有些早于本次调研，因此应表述为“被调研验证并进一步系统化”，
而不是全部声称为“从 quantum.harness 新增”。

## 这些借鉴具体改善了什么

### 1. 实验可复现性

过去只知道“某个模型跑了某个 prompt”是不够的。现在计划和记录需要同时保存：

- Git commit；
- data snapshot hash；
- prompt packet hash；
- skill version 和 hash；
- condition、split、input mode；
- metrics/report 路径。

这让另一个人可以判断两次结果是否真的可比较。

### 2. 运行前阻止错误

`benchmark/core/readiness.py` 不只检查文件存在，还检查 baseline/candidate 是否：

- 使用同一课程和 assessment；
- 使用同一 data snapshot；
- 使用匹配的 student/input hash；
- 保持 rubric/transcription 条件一致；
- 确实改变了计划修改的 prompt/skill；
- 仍然处在计划的 Git anchor 上。

这比模型跑完后才发现实验不可比更省成本。

### 3. 导师运行更自动化但仍保留关键批准

我们没有照搬 beginner-training 的“每一步都确认”。那会让导师实验仍然需要
大量人工干预。当前 advisor skill 只在真正有后果的边界请求批准：

- 安装软件或改变登录状态；
- 恢复私有数据；
- 进行可能消耗额度的模型 probe；
- 把学生内容发送给外部模型；
- development 通过后进入 sealed test。

一旦选择确定，packet preparation、两种 input mode、validation、package 和
draft PR submission 可以自动进行。这是对 beginner-training 思想的项目化
适配，而不是机械复制。

### 4. 失败能够被正确记录

Negative control 的思想帮助我们区分：

- gate 正确拒绝已知坏输入；
- 技术运行失败；
- 实验完整运行但准确率没有提高。

这也是 TASK2 不再反思每一个普通命令报错，而只复盘对项目决策有意义的负结果
的原因。

## 目前做得不够好的地方

### 1. 原调研记录没有固定 upstream commit

只记录 `main` 和日期不够。上游 README 已从 `/beginner-training` 演进到
`/track-starter` 入口，而旧报告没有自动提示。这会导致几周后无法知道引用的
到底是哪一版设计。

### 2. 文档编码没有进入质量检查

旧调研文件在 Git 中已经是乱码，但测试没有发现。报告存在不等于报告可读。

### 3. Negative controls 没有成为 main 的 required CI

本地测试可以证明当前开发机上通过，但合并 PR 时 GitHub 还没有强制运行这些
检查。若后续修改破坏 readiness/privacy gate，main 仍可能接受。

### 4. Report lineage 尚未完全闭环

部分 Markdown、Typst 和 PDF 是人工维护的。即使内容正确，也缺少统一的机器
检查来证明：

```text
run metadata + metrics -> report source -> rendered report
```

报告与 JSON 发生漂移时，目前仍依赖人工发现。

### 5. Knowledge 层仍然分散

Course spec、rubric、prompt、skill snapshot 和错误经验存在，但没有统一的人类
可读索引。直接复制成另一套手写 cards 又会产生重复事实，因此如果要做 cards，
应该从 JSON/record 派生，而不是手工维护第二份真相。

## 可选择的项目改进

### 选项 A：调研来源快照与文档健康检查

增加规则：

- 外部仓库调研必须记录 URL、commit SHA、检查日期；
- CI 扫描新增 Markdown 的 UTF-8 可读性和常见乱码特征；
- 当报告引用 floating `main` 时明确标记它不是固定证据。

收益：低成本解决本次已经发生的真实问题。

成本：低。

风险：只能保证来源和可读性，不改善评分准确率。

建议：立即实施。

### 选项 B：把 negative controls 加入 GitHub Actions

让 CI 强制运行：

- packet/readiness 已知坏输入必须失败；
- `Data/` 和 secret/privacy 扫描；
- report 中不能出现学生 ID；
- experiment record schema 和 hash consistency；
- 中英双语失败报告检查。

收益：把“本地习惯”变成 main 的合并门槛。

成本：低到中。

风险：Windows/Linux 路径差异可能导致早期 CI 调整。

建议：作为 TASK5 的核心内容实施。

### 选项 C：统一 run-to-report lineage contract

为所有模型路径统一记录：

- run ID、parent run ID；
- provider/model/input mode；
- prompt/rubric/skill/data/packet hash；
- metrics source；
- report generator version；
- rendered artifact hash。

并增加命令重新生成报告、检查报告与 source JSON 是否一致。

收益：直接提高所有实验和四模型比较的可信度。

成本：中。

风险：需要兼容现有 DeepSeek、Codex、Kimi、Claude 的不同记录格式。

建议：在 TASK7 新多模态比较前先定义最小 schema，逐步迁移，不一次重写全部
历史记录。

### 选项 D：增加面向教师的 grading-beginner-training 模式

在现有自动化 advisor skill 外提供教学模式：

- 解释 text-first 与 direct multimodal 的区别；
- 展示 development 与 held-out 的边界；
- 演示一个不会调用模型的 dry-run；
- 用 synthetic/bad packet 做 negative control；
- 最后让教师看懂自动生成的 PR。

收益：教师不仅能运行，还能理解关键判断。

成本：中。

风险：如果每次真实运行都强制逐步确认，会降低自动化程度。因此教学模式必须
可选，真实批量运行继续只在关键边界确认。

建议：先等导师完成一次真实 Kimi/Claude 流程，再根据实际卡点设计，不现在
猜测全部教学步骤。

### 选项 E：生成 course/rubric/skill 可读卡片

从现有 JSON 自动生成只读 Markdown cards，帮助人和 agent 快速理解课程、评分
规则和 skill 已知缺陷。

收益：降低跨课程和新成员理解成本。

成本：中。

风险：如果人工编辑 cards，会形成第二套事实源。

建议：只有在能保证 cards 全部由结构化 source 自动生成时再做。

## 我的推荐

推荐选择：

1. **立即做 A**：修复来源快照和乱码检查；
2. **TASK5 做 B**：把关键 negative controls 变成 GitHub Actions required
   check；
3. **TASK7 前做 C 的最小版本**：先冻结统一 lineage schema，再运行新的
   Codex/Claude 多模态比较；
4. **暂缓 D**：等导师真实运行反馈；
5. **暂缓 E**：避免过早制造重复知识层。

这套顺序的理由是：先让现有记录可信，再让合并过程自动守住可信度，然后才
扩展新的模型实验。它不会为了“看起来像 quantum.harness”而引入与阅卷无关的
复杂工具链。

## 不建议直接迁移的内容

- 量子模型卡中的 Hamiltonian、symmetry sector 和数值算法；
- Julia/ITensors/Slurm 作为默认运行栈；
- Ion remote-skill symlink 机制；
- 每一步都必须人工确认的训练协议；
- 把 HTML renderer 直接替换现有 Typst/PDF 报告。

这些内容要么属于量子物理领域，要么会降低当前阅卷自动化。我们应该迁移
“决策与证据的结构”，而不是迁移上游的领域工具。

## 用户决策

2026-07-25，YY 选择 **A+B+C**，暂缓 D+E。

- A 已在 TASK3 分支实现：`sources.json` 固定外部调研的 repository、commit 和
  checked date；`python -m benchmark.core.research_records` 检查 UTF-8、常见
  乱码、缺失 commit 以及指向 floating GitHub `main` 的证据链接。
- B 已进入 TASK5 scope：把 negative controls 和文档健康检查变成 GitHub
  Actions required check。
- C 已进入 TASK7 前置条件：新的多模态比较前先冻结最小 run-to-report
  lineage schema。
- D、E 暂不实施。

这里的“选择”不等于 B、C 已经实现。TASK3 只实现 A，并把 B、C 写入各自任务
的明确验收条件。

## Upstream references

- Repository: <https://github.com/QuantumBFS/quantum.harness>
- README:
  <https://github.com/QuantumBFS/quantum.harness/blob/3bed20a166fe0228cf40b82d7d6dbd0a77014df1/README.md>
- Harness instructions:
  <https://github.com/QuantumBFS/quantum.harness/blob/3bed20a166fe0228cf40b82d7d6dbd0a77014df1/AGENTS.md>
- Beginner training:
  <https://github.com/QuantumBFS/quantum.harness/blob/3bed20a166fe0228cf40b82d7d6dbd0a77014df1/skills/beginner-training/SKILL.md>
- Reproduce paper:
  <https://github.com/QuantumBFS/quantum.harness/blob/3bed20a166fe0228cf40b82d7d6dbd0a77014df1/skills/reproduce-paper/SKILL.md>
