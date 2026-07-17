# quantum.harness beginner-training 学习记录

记录日期：2026-07-15
本仓库分支：`codex/quantum-harness-training-notes`
范围：只读调研 `QuantumBFS/quantum.harness` 的 README、`/beginner-training` 及其关联技能/目录说明；未 clone 外部仓库，未运行模型，未访问或修改 `Data/`。

定位说明：本记录是 Codex 对 quantum.harness beginner-training 材料的调研总结，不等同于学习者本人完成 `/beginner-training` 的交互式训练。真正训练应由学习者按 confirm-gated Teaching Protocol 逐步完成：先理解每一步，再由学习者确认是否运行命令。

## 结论摘要

`quantum.harness` 是一个面向计算量子多体研究的 agent harness：它把“研究问题、领域知识、数值方法、软件栈、验证检查、报告产物”拆成可组合的技能和知识卡片，让 AI agent 不只是运行代码，而是按研究实践确认假设、估算成本、执行计算、做负控/一致性检查，并生成可复现报告。

`/beginner-training` 是这个 harness 的入门训练入口。它不是一个自动脚本，而是一个确认门控的教学流程：先让新用户选择训练 track，再用“解释一步、展示命令、等待确认、运行、解释实际结果”的协议逐步带用户完成 setup、论文复现、文献库、专业开发流程和挑战报告。

对 `exam-automark` 最值得迁移的不是量子物理内容，而是它的工程形状：单一事实源、技能与知识分离、负控/完整性检查、运行前显式确认、私有数据隔离、派生报告不可反向编辑，以及让报告成为 durable record。

## 外部资料锚点

- Repository: <https://github.com/QuantumBFS/quantum.harness>
- README: <https://raw.githubusercontent.com/QuantumBFS/quantum.harness/main/README.md>
- Harness operating instructions: <https://raw.githubusercontent.com/QuantumBFS/quantum.harness/main/AGENTS.md>
- Beginner training skill: <https://raw.githubusercontent.com/QuantumBFS/quantum.harness/main/skills/beginner-training/SKILL.md>
- Beginner training tracks:
  - <https://raw.githubusercontent.com/QuantumBFS/quantum.harness/main/skills/beginner-training/tracks/track1-setup.md>
  - <https://raw.githubusercontent.com/QuantumBFS/quantum.harness/main/skills/beginner-training/tracks/track2-reproduce.md>
  - <https://raw.githubusercontent.com/QuantumBFS/quantum.harness/main/skills/beginner-training/tracks/track3-survey.md>
  - <https://raw.githubusercontent.com/QuantumBFS/quantum.harness/main/skills/beginner-training/tracks/track4-develop.md>
  - <https://raw.githubusercontent.com/QuantumBFS/quantum.harness/main/skills/beginner-training/tracks/track5-beyond.md>
- Skill registry: <https://raw.githubusercontent.com/QuantumBFS/quantum.harness/main/Ion.toml>
- Report renderer skill: <https://raw.githubusercontent.com/QuantumBFS/quantum.harness/main/skills/report/SKILL.md>
- Reproduce-paper skill: <https://raw.githubusercontent.com/QuantumBFS/quantum.harness/main/skills/reproduce-paper/SKILL.md>
- Download-ref skill: <https://raw.githubusercontent.com/QuantumBFS/quantum.harness/main/skills/download-ref/SKILL.md>
- Challenge-report skill: <https://raw.githubusercontent.com/QuantumBFS/quantum.harness/main/skills/challenge-report/SKILL.md>
- Git ignore policy: <https://raw.githubusercontent.com/QuantumBFS/quantum.harness/main/.gitignore>

## quantum.harness 是什么

从 README 看，`quantum.harness` 还处于早期阶段，定位是“computational quantum research harness”。它帮助 AI agent 做量子系统模拟，并把领域专家的实践经验固化成可调用的工作流：

- 模型卡片：Hamiltonian、对称性、边界条件、守恒扇区、可观测量等。
- 数值方法和工具使用技能：参数设置、资源估计、验证检查。
- 支撑技能：文献调研、报告写作、论文复现。
- 集群支持：当计算不适合本地笔记本时，用集群 workflow 接管。

它的核心不是“一个万能脚本”，而是一个可复现研究环境：技能负责流程，知识库负责事实，报告负责留下可审计结果。

## /beginner-training 解决什么问题

`/beginner-training` 解决的是新用户不会使用 harness、也不一定理解科研计算实践的问题。它明确假设读者是本科生水平，不假设用户懂 Git、GitHub CLI、Julia、文献工具或量子多体术语。

它有两层职责：

1. Track selector：让用户选择从哪条训练路线开始。
2. Teaching Protocol：规定每一步都必须解释目的、展示命令和正确结果、等待用户确认，然后才运行。

这类设计的价值是防止 agent 把“替用户完成任务”误做成黑箱。训练的真正目标是让学生理解每个决策为什么重要，例如为什么要做 smoke test、为什么论文复现要先确认模型和边界条件、为什么负控能证明检查有 teeth。

## beginner-training 的五条 track

| Track | 目标 | 关键产物或检查 |
| --- | --- | --- |
| Track 1 — Setup check | 检查 harness 技能、PDF 渲染、Julia 环境、GitHub CLI | `make skills`、`pymupdf4llm` import、Julia project instantiate、`gh` 可见性；最后用一个故意不存在的 Python 包做负控 |
| Track 2 — Reproduce a paper | 选择方法 track，复现论文图或任务 | 扫描 `tracks/*/README.md`，交给 `/reproduce-paper`，并用正确签名 + 故意错误参数做 checkpoint |
| Track 3 — Conduct a literature survey | 构建小型 `.knowledge/` 文献库 | 用 `/download-ref` 加入已知论文，再用 `/survey` 扩展主题；检查不存在 arXiv ID 必须失败，索引数量必须与实际文献匹配 |
| Track 4 — Develop code like an expert | 在训练 repo 上完成 issue → design → plan → tests → review → PR | GitHub fork、good first issue、Superpowers brainstorming/writing-plans/requesting-code-review、PR 与 self-review 记录 |
| Track 5 — Go beyond | 在已复现实验上提出并完成一个小挑战 | `/challenge` 生成候选，记录计划和 kill criterion，执行计算后用 `/challenge-report` 生成报告并做完整性检查 |

注意：当前提交树的 `skills/` 目录清单中看不到 `survey`，但 `Ion.toml` 把 `survey` 声明为远程 skill，`.gitignore` 也明确忽略 `skills/survey`。也就是说，它不是普通 committed local skill，而是由 Ion 管理和同步的 remote skill。

## skills / harness / knowledge base / reports 如何组织

### Skills

`skills/` 是 workflow 层。用户可调用的技能通常表现为 `/name`，例如 `/beginner-training`、`/reproduce-paper`、`/download-ref`、`/report`、`/challenge-report`。另有自动触发的 dispatcher，例如 `model` 和 `physics`。

技能分几类：

- 训练与用户流程：`beginner-training`、`onboard`、`solve`、`challenge`。
- 复现实验流程：`reproduce-paper`、`parameter-scan`、`scaling-fit`、`cross-method-check`。
- 方法层：`method-ed`、`method-mps`、`method-peps`、`method-qmc` 等。
- 软件栈层：`using-itensors`、`using-quspin`、`using-xdiag`、`using-slurm` 等。
- 知识/文献工具：`download-ref`、`find-docs`、远程 `survey`。
- 报告层：`report`、`challenge-report`。

Ion 负责 skill 管理：`Ion.toml` 指定哪些技能是 local，哪些来自远程 registry；远程技能作为 symlink 进入 `skills/`，但被 `.gitignore` 忽略，并由 `Ion.lock` 固定版本。

### Harness operating model

`AGENTS.md` 是 user-facing 的运行说明。里面一个特别值得注意的原则是：harness 在运行时应当稳定，用户在会话中学习，harness 本身的变化应放到开发周期，而不是边教边改。

它还强调：

- 在任何计算前确认 consequential setup：Hamiltonian、符号约定、格点、边界、对称扇区、目标 observable、系统尺寸。
- domain content 按问题组织，而不是按课程或工具组织。
- 技能不应硬编码事实，而应读取 `.knowledge/` 的卡片。
- 验证优先级是 limit checks、symmetry、convergence、internal consistency、cross-method validation、literature comparison。

### Knowledge base

`.knowledge/` 是事实和文献层，不是教程、路线图或任务列表。当前结构包括：

```text
.knowledge/
  conventions.md
  limits.md
  symmetry-cheatsheet.md
  literature/
  models/
  physics/
```

`model` dispatcher 读取 `.knowledge/models/<name>/MODEL.md`；`physics` dispatcher 读取 `.knowledge/physics/<topic>/PHYSICS.md`。AGENTS 中要求数值 anchor 必须带 provenance 标签：`Literal`、`Analytic` 或 `Harness anchor`。这条设计很硬，但也很有价值：没有来源标签的数字默认不可信。

文献库由 `download-ref` 维护：`ref.bib` 是 source of truth，per-method `INDEX.md` 和 rendered markdown 是 committed artifacts，PDF 和 extracted figures 放在 `.raw/` / `.figures/` 并被 Git 忽略。

### Reports

`report` 是通用 HTML renderer：读取 `<run-dir>/report.json`，输出 `<run-dir>/report.html`。它把 CSS、图片、MathML 都内嵌成一个离线文件，类似单文件 PDF。

`reproduce-paper` 使用一个更严格的数据链：

```text
run.json -> report.json -> report.html
```

其中 `run.json` 是唯一事实源；`report.json` 和 HTML 是派生视图，不反向编辑。脚本进入 `tracks/<track>/solutions/`，生成数据和图进入 `tracks/<track>/results/`，而 `tracks/**/results/` 被 Git 忽略。

仓库顶层 `reports/` 目前有一个 `qmb-model-method-report.typ/pdf`，更像静态方法报告样例；真正的运行报告按 track/run 生成在 results 下。

## 对 exam-automark 的启发

`exam-automark` 和 `quantum.harness` 的领域不同，但工程问题很像：都需要让 agent 在私有数据、复杂流程和可复现报告之间保持纪律。可迁移的核心是“把事实、流程、运行、报告分层”。

### 1. Prompt packet 可以承担 run.json 的角色

我们已经有 prompt packet、manifest、rubric、schema 和 packet audit。可以进一步明确：

- packet manifest 是模型调用的唯一事实源；
- metrics/report 只从 packet manifest、run metadata、prediction outputs 派生；
- 不从聊天上下文补参数；
- prompt hash、rubric hash、input hash、schema hash、model config hash 都进入报告。

这与 `reproduce-paper` 的 `run.json -> report.json -> report.html` 很相似。

### 2. 把 training protocol 用于教师/助教 onboarding

`/beginner-training` 的 confirm-gated 教学协议可以迁移成 `/grading-beginner-training` 或 `docs/onboarding/teacher-training.md`：

- Step 1：检查环境和 Data 是否被 Git 忽略。
- Step 2：解释 prompt packet 和为什么不能直接改模型提示。
- Step 3：跑 dry-run/audit，不调用模型。
- Step 4：解释一次小样本 grading run 的记录字段。
- Step 5：生成报告并核验没有私有学生内容。

这对老师/TA 比直接甩 CLI 更友好，也能减少“误跑模型、误提交 Data、误把开发集当 held-out”的事故。

### 3. 为 AI 阅卷设计负控和完整性检查

quantum.harness 的每条 track 都要求 checkpoint，不是“看起来跑完了”就结束。阅卷框架可以设计类似检查：

- Schema negative control：故意给一个缺字段/错类型输出，验证 validator 必须失败。
- Rubric mismatch negative control：把不匹配课程的 rubric 接到 packet，readiness gate 必须拦截。
- Student ID integrity：调换或缺失 student_id，metrics 必须拒绝。
- Prompt packet integrity：manifest 里声明的输入数量与实际文件数量不一致时必须失败。
- Privacy integrity：报告中扫描是否出现原始学生姓名、图片路径或私有 Data 路径。

这些检查大多可以 dry-run，不需要真的调用模型。

### 4. 知识库卡片可迁移为 course/rubric/skill cards

`.knowledge/models/` 和 `.knowledge/physics/` 的思想可以迁移为：

```text
experiments/knowledge/
  courses/<course>/COURSE.md
  assessments/<course>/<assessment>/ASSESSMENT.md
  rubrics/<course>/<assessment>/RUBRIC.md
  grading-skills/<skill-version>/SKILL-CARD.md
```

每张卡片应只放可复用事实和 provenance，不放一次性运行记录。一次性运行仍属于 `experiments/records/`。

可能的卡片内容：

- 课程/考试：题型、评分尺度、常见错误、允许的部分分。
- Rubric：每个子问的得分点、常见误判、人工 gold 来源。
- Grading skill：适用输入类型、输出 schema、known failure modes、验证清单。

### 5. 报告可以更明确地区分 source、derived、rendered

当前 `exam-automark` 已经有 Markdown、JSON、Typst/PDF 报告。可以借鉴 `report` 的原则：

```text
experiment.json 或 metrics.json -> report source json -> Typst/PDF/HTML
```

报告生成后不应成为新的事实源；若发现报告内容错，应改上游 JSON 或记录，再重新生成。

### 6. 资源估计可迁移成模型调用预算估计

quantum.harness 在计算前估算本地/集群成本。阅卷中对应的是：

- 学生数、页数、token 估算；
- provider/model/input-mode 成本；
- 最大重试次数；
- 是否会接触私有数据；
- 是否只是 dry-run/audit；
- 是否需要老师明确授权 model call。

这可以变成 preflight gate，而不是等调用失败或费用异常后再补记录。

## 可以迁移到 AI 阅卷实验框架的设计

优先级建议：

1. 单一事实源：把 packet/run metadata 明确为所有 metrics/report 的 source of truth。
2. Readiness gate + negative controls：让每次 benchmark 先证明 validator 能失败。
3. Course/rubric/skill cards：把跨实验复用知识从一次性 records 中分离出来。
4. Confirm-gated onboarding：给教师/助教一个教学式 dry-run，不默认跑模型。
5. Report derivation contract：从 JSON 派生 Typst/PDF/HTML，不手改最终报告。
6. Private artifact policy：继续保持 `Data/` ignored，只提交安全摘要、hash、聚合指标。
7. Explicit setup confirmation：在真实模型调用前确认 course、assessment、split、rubric、prompt packet、provider、model、input mode。

## 不适合直接迁移的设计

- 量子物理模型卡、Hamiltonian、对称扇区、数值方法细节不能直接迁移；只能迁移卡片结构。
- Julia、Slurm、cluster-first 的计算模型不是当前阅卷核心；阅卷更需要 provider/API、OCR、vision/text boundary 的 preflight。
- 每一步都等用户确认不适合 headless benchmark；适合 onboarding、首次实验、真实 model-call gate，不适合批量自动评测的内部循环。
- Ion remote skill symlink 机制需要谨慎。`exam-automark` 如果要可复现实验，最好把核心 grading skills 提交到仓库或用 lock 文件固定，并在报告中记录 skill hash。
- `report.html` 单文件 renderer 很有吸引力，但不应立即替换现有 Typst/PDF；可以先作为可浏览的附加产物。
- 真实负控不应总是调用昂贵模型。优先做 cheap integrity checks 和 validator negative controls。

## 建议的下一步

1. 新增 `experiments/knowledge/` 的最小卡片草案，只覆盖一个已有 pilot，例如 Physics Week 9。
2. 给 `check-run-readiness` 增加一组 cheap negative-control fixtures，证明 packet/schema/rubric/student-id 检查会失败。
3. 定义 `run.json` 或 `experiment-run.json` 的固定字段，把 provider、model、prompt hash、packet hash、data snapshot、split、input mode、cost estimate 放在一个事实源。
4. 设计一个教师 onboarding dry-run 文档，不调用模型，只解释 packet、audit、metrics、privacy boundary。
5. 后续若做 HTML 报告，先从现有 metrics JSON 派生，不手写第二套事实。

## 本次调研限制

- 没有运行 quantum.harness 的 `/beginner-training`，只是阅读其 README、skill 文档、track 文档和相关组织文件。
- 没有 clone quantum.harness，也没有把它的仓库内容复制进 `exam-automark`。
- 没有运行任何模型或计算任务。
- 没有访问或修改 `Data/`。
- quantum.harness 自身仍在早期阶段；README、skills 和远程 Ion-managed skills 之间可能继续变化，本记录是 2026-07-15 的快照理解。
