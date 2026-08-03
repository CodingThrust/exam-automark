# W4 representative root-cause review / W4 代表性错题根因复核

## Purpose / 目的

This protocol turns existing **development-split** error books into a small,
human-reviewable queue before proposing another grading-skill change. It is a
discovery step, not a final diagnosis and not a new model experiment.

本流程把已有的**开发集**错题集整理成少量可人工复核的案例，再决定是否提出新的评分 skill 修改。它是发现根因的步骤，不是最终诊断，也不会运行新模型。

For W4, the first queue covers Q7–Q10 with two cases per question:

- the largest shared cross-condition error, then
- the largest Codex direct-multimodal vs. Codex transcript-first score gap;
  one of those second slots is reserved globally for the largest same-text
  Codex-G1 vs. DeepSeek-G1 gap when that provenance contract is valid.

W4 首轮队列覆盖 Q7–Q10，每题两例：先选三路共同失败中误差最大的案例，再选 Codex 直接多模态与 Codex 转录后评分分差最大的案例；其中一个第二槽位会在 provenance 合法时保留给同一文本输入下 Codex-G1 与 DeepSeek-G1 的最大分差。它既能发现共同的评分/规则问题，也能暴露输入路线差异；不把路线差异误称为“改进”。

## Safety contract / 安全边界

- Inputs and outputs are private, gitignored files under `Data/`; never add them to a commit or PR.
- The builder accepts only development error books that explicitly exclude technical failures from grading cases.
- All sources must have the same course, assessment, gold, prompt, rubric, and image-snapshot hashes.
- A route label is permitted only after verifying the named input modes and same Codex model; a same-text model label additionally requires the exact same text-source hash.
- An absent case is shown as “matches gold” only after the source error book proves complete disagreement coverage and an identical development population.
- The browser reviewer binds to the exact snapshot-manifest hash and to each allowed image hash. It listens only on `127.0.0.1` with a fresh single-session token.
- Neither command invokes a model, transmits data, changes gold, or writes a final `diagnoses.private.json`.

- 输入和输出均位于 `Data/` 下的私有、gitignore 文件；绝不能加入 commit 或 PR。
- 构建器只接受明确排除技术运行失败的开发集错误书。
- 所有来源必须有相同的课程、考试、gold、prompt、rubric 和图像快照哈希。
- 只有在验证命名输入模式及相同 Codex 模型后才允许标为“路线”差异；标为“同一文本模型”差异还必须验证完全相同的 text-source 哈希。
- 只有错误书证明完整分歧覆盖且开发集总体一致时，缺失案例才会显示为“与 gold 一致”。
- 浏览器审核器绑定精确的快照 manifest 哈希及每张允许图片的哈希，只监听带随机单次 token 的 `127.0.0.1`。
- 两个命令均不调用模型、不传输数据、不改 gold，也不生成最终 `diagnoses.private.json`。

## Run locally / 本地运行

Build a versioned queue from three existing private W4 error books:

```powershell
python -B scripts/build_error_review_queue.py `
  --course experiments/course_specs/DSAA3071_week4_full_q1_q10.json `
  --rubric <exact-frozen-rubric-used-by-source-packets.json> `
  --condition codex_m1=<private-codex-m1-error-book.json> `
  --condition codex_g1=<private-codex-g1-error-book.json> `
  --condition deepseek_g1=<private-deepseek-g1-error-book.json> `
  --question Q7 --question Q8 --question Q9 --question Q10 `
  --items-per-question 2 `
  --output <new-private-root-cause-review-queue.json>
```

Open the resulting queue with the local reviewer:

```powershell
python -u -B scripts/review_error_cases.py `
  --queue <private-root-cause-review-queue.json> `
  --scoped-image-root <matching-approved-private-snapshot-root> `
  --output <new-private-human-root-cause-review.json>
```

The terminal prints a local URL. Do not share that URL. The UI saves one case
atomically at a time and moves to the next unfinished case.

终端会打印一个本地 URL，不要分享它。页面每次原子保存一个案例，并自动跳到下一个未完成案例。

## Human decision guide / 人工判断指引

For each case:

1. Inspect the source image and gold first.
2. Compare the three condition summaries; model evidence is collapsed until needed to reduce anchoring.
3. Choose one constrained mechanism when supported, or choose **needs more evidence**.
4. Mark a case as typical only when it illustrates a repeatable mechanism, not merely because its score difference is large.

Mechanism choices are shared with the confidence audit taxonomy:

- `explicit_evidence_omission`: visible, verifiable answer evidence was missed.
- `unsupported_evidence_credit`: a keyword, implication, or unstated step was credited.
- `rule_precedence_or_gate_error`: an explicit cap, gate, precedence, or context check was not applied.
- `official_style_tolerance_mismatch` / `score_band_boundary_disagreement`: grading-style or partial-credit calibration needs an owner decision first.
- `rubric_gold_contract_inconsistency`: rubric and gold cannot both be reproduced; do not optimize the skill first.
- `text_representation_ambiguity`: text loses notation/layout/state needed from the image; paired multimodal investigation is required.

每个案例先看原图和 gold，再看三路摘要；如有需要才展开模型证据，以减少被模型理由锚定。只有证据足够时才选择受限机制；否则选择“需要更多证据”。只有案例能够说明可重复机制时才勾选“典型案例”，不是因为它的分差很大。

## What follows / 后续工作

The resulting human-review file determines whether the next candidate skill
should target an objective model decision, a representation route, or a
rubric/gold adjudication. It does **not** justify a candidate by itself.
Before a public diagnosis summary or a skill acceptance decision, complete the
required all-case diagnosis workflow separately.

若人工复核确认的是客观模型判断问题，才把它转化为可测试的 candidate skill 假设；若是输入表示或 rubric/gold 问题，则先处理相应前置条件。首轮抽样本身不能证明 candidate 有效。发布公开诊断汇总或做 skill 验收前，仍需另行完成全量案例诊断。

If the UI displays a legacy snapshot-label warning, keep using the exact
hash-verified snapshot shown by the tool; do not substitute another one. Log
the label-alignment cleanup separately before the next benchmark preparation.

若页面显示旧快照标签警告，仍应使用工具已逐哈希验证的精确快照，不能自行替换成其他快照；在下一次 benchmark 准备前单独记录和清理标签对齐问题。
