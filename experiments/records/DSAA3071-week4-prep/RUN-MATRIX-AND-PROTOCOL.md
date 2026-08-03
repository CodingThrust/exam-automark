# DSAA3071 Week 4 Future Run Matrix and Protocol

Status / 状态: **blocked preparation / 已阻断的运行前准备**. This document
defines a future development-only workflow; it records no model call, model
output, gold score, or accuracy result.

本文定义未来仅针对 development 集的工作流；其中没有模型调用、模型输出、gold
分数或准确率结果。

The machine-readable companion is
[`advisor-workflow-development.blocked.json`](advisor-workflow-development.blocked.json).
It is valid under the current `advisor_workflow` configuration schema, but its
own `future_run_contract.model_run_allowed` is `false`. Its deliberately
unusable model placeholders prevent an accidental real run.

对应的机器可读配置为
[`advisor-workflow-development.blocked.json`](advisor-workflow-development.blocked.json)。
它能通过当前 `advisor_workflow` 的配置 schema 校验，但其
`future_run_contract.model_run_allowed` 为 `false`；模型名也有意保留为不可运行的
占位符，以避免误启动真实运行。

## Frozen controls / 已冻结的控制条件

| Control / 控制项 | Fixed value / 固定值 |
| --- | --- |
| Assessment scope / 题目范围 | W4 partial: Q1-Q4, Q9, Q10; 60 points. Q5-Q8 are excluded everywhere. / W4 部分 benchmark：Q1-Q4、Q9、Q10，共 60 分；Q5-Q8 在所有环节排除。 |
| Development cohort / 开发集 | 7 anonymous students from the frozen split. / 冻结 anonymous split 中的 7 名学生。 |
| Source pages / 源页面 | Final-approved anonymous `p01` and `p03` only. / 仅使用终审通过的匿名 `p01`、`p03`。 |
| Rubric and grade prompt / rubric 与评分提示词 | `rubric_v0.json` and `grade_standard_v1_strict_schema.txt`. / 固定使用当前 rubric 与标准评分提示词。 |
| Transcription prompt / 转录提示词 | `transcribe_standard_v1.txt`. |
| Image provenance / 图像来源 | The scoped snapshot and final anonymization review paths pinned in the blocked config. / 阻断配置中固定的 scoped snapshot 与匿名化终审路径。 |
| Gold / 人工 gold | One private question-level table for the same six questions; currently blank and required before accuracy calculation, claims, or tuning. / 同一六题的私有逐题 gold 表，当前为空；在计算/宣称准确率或调参前必须完成。 |

The authoritative scope and page mapping are in the
[preparation contract](PREPARATION-CONTRACT.md). The machine-readable gate
state is [PRE-RUN-STATUS.json](PRE-RUN-STATUS.json).

范围和页面映射以[准备合同](PREPARATION-CONTRACT.md)为准；各门槛的机器可读状态见
[PRE-RUN-STATUS.json](PRE-RUN-STATUS.json)。

## Current packet state / 当前 packet 状态

The private W4 preparation already contains audited image packets for both
splits: direct-image `M1` and fresh-transcription `T1`. They contain no model
output. The development-only blocked configuration references `M1-dev-r1` and
`T1-dev-r1`; its future activation must still bind them to the workflow's
privacy provenance and all remaining hard gates before it can run.

私有 W4 准备目录已经包含两个 split 的、通过本地 packet audit 的图像 packet：直接
图像 `M1` 与新鲜转录 `T1`，其中没有模型输出。development 阻断配置引用
`M1-dev-r1` 与 `T1-dev-r1`；未来 activation 仍必须把它们绑定到工作流的隐私
provenance 与其余硬门槛后才能运行。

## Planned development matrix / 计划中的 development 矩阵

`T1` and direct-image `M1` begin from the same seven students and the same approved images.
The text route is not allowed to reuse an older transcript: each engine first
creates its **own fresh automatic T1 transcript**, then that output passes
**unchanged** into only that engine's text-only `G1` packet.

`T1` 与直接图像 `M1` 从同一 7 名学生、同一批已审批图像开始。文本路线不得复用历史转录：
每个 engine 必须先生成**自己的新鲜自动 T1 转录**，再把该输出**原样**制作成它自己
的文本 `G1` packet。

| Stage / 阶段 | Run ID / 运行 ID | Engine | Input | Purpose / 目的 |
| --- | --- | --- | --- | --- |
| Fresh transcription / 新鲜转录 | `kimi-transcription` | Kimi Code | T1, multimodal | Produce Kimi's own transcript. / 生成 Kimi 自己的转录。 |
| Fresh transcription / 新鲜转录 | `claude-transcription` | Claude Code | T1, multimodal | Produce Claude's own transcript. / 生成 Claude 自己的转录。 |
| Direct grading / 直接评分 | `kimi-multimodal-standard` | Kimi Code | M1, multimodal | Grade approved page images directly. / 直接评分已审批图像。 |
| Transcript-first grading / 先转录后评分 | `kimi-text-standard` | Kimi Code | G1, text-only | Grade only Kimi's fresh transcript. / 只评分 Kimi 的新鲜转录。 |
| Direct grading / 直接评分 | `claude-multimodal-standard` | Claude Code | M1, multimodal | Grade approved page images directly. / 直接评分已审批图像。 |
| Transcript-first grading / 先转录后评分 | `claude-text-standard` | Claude Code | G1, text-only | Grade only Claude's fresh transcript. / 只评分 Claude 的新鲜转录。 |

Exact Kimi Code and Claude Code model identifiers are intentionally **not
pinned yet**. They must be verified on the runner, then recorded in a new
versioned activation config before zero-data probes or student-data runs. The
blocked config must remain unchanged as the record of the pre-run state.

当前**尚未固定** Kimi Code 与 Claude Code 的精确模型标识符。必须先在运行机器上
核验可用性，再在新的版本化 activation config 中记录，之后才可做零数据探针或学生
数据运行。当前阻断配置必须保持不变，作为运行前状态记录。

## Planned comparisons / 计划中的比较

| Comparison / 比较 | Only changing axis / 唯一变化轴 | Required interpretation / 必要解释 |
| --- | --- | --- |
| Kimi text vs multimodal | input mode / 输入模态 | Measures the effect of Kimi's own transcription route versus direct images. / 衡量 Kimi 自身转录路线与直接图像的影响。 |
| Claude text vs multimodal | input mode / 输入模态 | Measures the effect of Claude's own transcription route versus direct images. / 衡量 Claude 自身转录路线与直接图像的影响。 |
| Kimi vs Claude, multimodal | engine/model / engine 与模型 | Compares engines on identical direct-image evidence. / 在相同直接图像证据上比较 engine。 |
| Kimi vs Claude, text-only | engine/model / engine 与模型 | Compares engine-specific fresh-transcript routes, not a shared transcript. / 比较各自新鲜转录路线，不能把它解释为共享转录上的纯模型比较。 |

The 15 held-out students are not part of this file. They remain sealed until
development results are analyzed, no tuning decision remains, and a separate
held-out configuration plus explicit approval exists.

其余 15 名 held-out 学生不属于本文件。在分析完 development 结果、停止调参且另有
held-out 配置和明确批准前，他们必须保持封存。

## Hard gates / 硬门槛

| Gate / 门槛 | Current state / 当前状态 | What makes it ready / 如何变为 ready |
| --- | --- | --- |
| Final anonymization / 匿名化终审 | ready | Already passed for the frozen W4 v1 artifact. / 已通过。 |
| Question-level gold / 逐题 gold | blocked | Independently fill and validate all six in-scope question scores for the development cohort before any accuracy calculation, claim, or tuning decision. / 在任何准确率计算、结论或调参决定前，独立填写并验证 development 集每人六题的分数。 |
| Primary fresh-transcript lineage / 主路线新鲜转录 lineage | not started | Each engine's automatic T1 output must pass unchanged into its own text G1 packet, with run and source hashes verified. / 每个 engine 的自动 T1 输出必须原样进入自己的文本 G1 packet，并验证 run 与源哈希。 |
| Optional transcription-quality audit / 可选转录质量审计 | not started, non-blocking | A separate audit may measure transcription quality after the primary runs; it must not alter the automatic primary route. / 主运行后可单独评估转录质量；不得改写自动主路线。 |
| Packet + lineage audit / packet 与 lineage 审计 | not started | Audit M1, T1, and each fresh-text G1 for scope, privacy, split, hashes, and image-to-transcript lineage. / 审计范围、隐私、划分、哈希及图像到转录的 lineage。 |
| Explicit run approval / 明确运行批准 | not started | Record approval only after all previous rows are ready. / 仅在前面全部 ready 后记录批准。 |

## Activation protocol / 启动协议

1. **Keep this configuration frozen.** Do not invoke `advisor_experiment.py
   run` from this file, including with `--dry-run`, because it is designed as a
   blocked planning record rather than a runner authorization.

   **保持配置冻结。** 不得用本文件执行 `advisor_experiment.py run`，包括
   `--dry-run`；它是被阻断的规划记录，不是运行授权。

2. **Finish gold before accuracy work.** Fill the private 132-row template and
   validate the development subset against the frozen course spec before any
   accuracy calculation, accuracy claim, or tuning decision. A missing or
   disputed human score blocks reporting rather than becoming a model score.

   **在准确率工作前完成 gold。** 填写私有的 132 行模板，并在任何准确率计算、
   准确率结论或调参决定前用冻结课程规范验证 development 子集。缺失或存在争议的人工
   分数会阻断汇报，不能被当成模型分数。

3. **Bind and audit image packets.** The immutable `T1-dev-r1` (task
   `transcribe`) and `M1-dev-r1` (task `grade`) have already been built from
   the pinned scoped snapshot, frozen student list, rubric, and tracked
   prompts. Before activation, bind their approved-image provenance to the
   workflow and re-audit their scope/privacy metadata; do not replace them
   with a broader page set.

   **绑定并审计图像 packet。** 不可变的 `T1-dev-r1`（转录）和 `M1-dev-r1`（评分）
   已经从固定 snapshot、学生列表、rubric 和提示词构建完成。activation 前必须把已批准
   图像的 provenance 绑定到工作流并重新审计范围/隐私 metadata；不得换成更宽的页面集。

4. **Pin CLI models and probe without student data.** Create a new activation
   config with exact Kimi Code and Claude Code model IDs, record the CLI
   versions/authentication mode, and perform only the approved zero-data probes.
   Never put a key, token, or credential in the config or a tracked record.

   **固定 CLI 模型并做零数据探针。** 新建 activation config，记录确切模型 ID、CLI
   版本和认证方式，只执行已经批准的零数据探针。不得把 key、token 或凭据写入配置或
   tracked record。

5. **Stage fresh transcription before grading.** Run each engine's T1 arm as a
   separate stage and validate its JSON/schema output. Pass each successful
   automatic T1 output unchanged into only the same engine's text-only G1
   packet. Do not insert a full human semantic review, normalization, or
   correction between T1 and this primary grade arm.

   **在评分前分阶段处理新鲜转录。** 每个 engine 的 T1 先独立运行并验证 JSON/schema
   输出；成功的自动 T1 输出必须原样进入同一 engine 的文本 G1 packet。不得在 T1 与
   该主评分臂之间插入完整人工语义复核、规范化或修订。

6. **Build engine-specific text packets and audit lineage.** Build Kimi's
   text-only G1 only from Kimi T1 output, and Claude's only from Claude T1
   output. Verify that both T1 image inputs match direct M1 image inputs, and
   that each text packet references the corresponding T1 run and source hashes.
   The model-free `benchmark.core.modality_lineage` helper is the intended
   validation layer once the packet artifacts exist.

   **构建 engine 专属文本 packet 并审计 lineage。** Kimi 的文本 G1 只能来自 Kimi
   T1 输出，Claude 同理；验证两个 T1 图像输入与直接 M1 图像输入一致，并验证每个文本
   packet 绑定对应 T1 run 与源哈希。packet 生成后，应使用无模型的
   `benchmark.core.modality_lineage` 进行验证。

7. **Optionally audit transcription quality afterward.** This audit may label
   readability or transcription errors for analysis, but it cannot overwrite
   the automatic transcripts used in the primary text-only arm. A separately
   human-corrected transcript, if studied, is a new secondary condition and
   must be reported separately.

   **之后可选择性审计转录质量。** 该审计可标注可读性或转录错误以供分析，但不能覆盖
   主文本评分臂使用的自动转录。如研究人工校正转录，它是新的次级条件，必须单独汇报。

8. **Obtain explicit approval, then run the four grading arms.** Retain raw
   outputs and student-level results only under ignored `Data/`; package only
   privacy-safe aggregates for a bilingual draft PR.

   **获得明确批准后，再运行四个评分臂。** 原始输出与学生级结果只能保留在忽略的
   `Data/` 下；只将隐私安全的聚合结果打包成中英双语 draft PR。

9. **Use the implemented course-generic metrics command after the runs.**
   Invoke `python -m benchmark.core.cli compare-course-runs` only after
   complete validated gold and two completed grading runs exist. For every
   planned pair, pass `--require-same-data-snapshot`, preserve the
   baseline/candidate order stated below, and write aggregate-only reports.
   Do not enable `comparisons` in the current advisor workflow: its
   operational comparison step still calls a physics-specific metrics CLI. A
   future workflow-level integration must explicitly select the generic command,
   course spec, gold table, and frozen student list.

   **在运行后使用已经实现的课程通用指标命令。** 只有在完整、已验证的 gold 与两条
   完成的评分运行都存在后，才可调用
   `python -m benchmark.core.cli compare-course-runs`。每一个计划比较都必须带
   `--require-same-data-snapshot`、固定下述 baseline/candidate 顺序，并只输出
   aggregate-only 报告。当前 advisor workflow 的比较步骤仍调用 physics 专用 metrics CLI，
   因此不能直接开启 `comparisons`。未来的工作流级接入必须显式选择通用命令、
   课程规范、gold 表和冻结学生名单。

   | Planned pair / 计划对 | Baseline / 基线 | Candidate / 候选 | Delta interpretation / 差值含义 |
   | --- | --- | --- | --- |
   | Kimi input mode / Kimi 输入模态 | `kimi-text-standard` | `kimi-multimodal-standard` | direct multimodal minus text-first / 直接多模态减先转录后评分 |
   | Claude input mode / Claude 输入模态 | `claude-text-standard` | `claude-multimodal-standard` | direct multimodal minus text-first / 直接多模态减先转录后评分 |
   | Direct-multimodal engine / 直接多模态 engine | `kimi-multimodal-standard` | `claude-multimodal-standard` | Claude minus Kimi / Claude 减 Kimi |
   | Text-first engine / 先转录后评分 engine | `kimi-text-standard` | `claude-text-standard` | Claude minus Kimi, with engine-specific transcripts / Claude 减 Kimi，且各自使用自己的转录 |

## What the configuration does and does not automate / 自动化边界

It already fixes the exact future arm names, private output locations, source
review paths, required engines/modes, fresh-transcript provenance, and a draft
PR destination. This removes the choice of whether to use direct multimodal or
transcript-first input: both are mandatory arms.

该配置已经固定未来的 arm 名称、私有输出位置、来源审核路径、必须的 engine/模态、
新鲜转录 provenance 和 draft PR 目标。因此“直接多模态还是先转录”的选择不再依赖
临时决定：两条路线都必须运行。

It intentionally does **not** automate over the hard gates above. The primary
automatic transcript-first route intentionally has no human semantic-editing
pause: that keeps the causal comparison intact. The current advisor workflow
hard-rejects probes and runs while this file has
`future_run_contract.model_run_allowed: false`, but it does not yet select the
standalone generic comparator automatically or independently prove the remaining
human-gold, lineage, and explicit-approval conditions. Treating either gap as if
it were complete would allow an incorrectly measured or unauthorized result.
Those are the next automation improvements, not experimental failures.

它有意**不会**越过上述硬门槛。自动主路线有意不设置人工语义编辑暂停点，以保持因果
比较成立；本文件的 `future_run_contract.model_run_allowed: false` 会让当前
advisor workflow 对 probe 和 run 都作硬拒绝，但它还不会自动选择独立通用比较器，
也不会独立证明其余人工 gold、lineage 与显式批准条件。若假装这些缺口已经解决，就可能
得到度量错误或未经授权的结果。它们是下一步自动化改进，而不是实验失败。
