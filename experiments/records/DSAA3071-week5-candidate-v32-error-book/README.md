# TASK8 Candidate-v3.2 Error Book / TASK8 Candidate-v3.2 错题集

## 中文

本记录把 candidate-v3.2 的开发集评分差异变成可重复生成、可逐案复核的“批作业错题集”。它解决的不是运行报错，而是模型输出已经通过结构校验后，预测分数仍与官方逐题 gold 不一致的问题。

两个层级严格分开：

- 私有层：33 个逐题案例，包含匿名学生编号、题号、gold、预测分数、证据、模型理由、flags 和当前 Codex 会话的中英双语根因诊断。它们只保存在 git 忽略的私有 `Data/` 目录。
- 公开层：只包含 7 名学生、70 个学生-题目对的聚合统计、根因计数、哈希和方法限制；不包含学生编号、答案文字、证据文字或逐案分数。

主要输出：

- `public-summary.json`：确定性提取器生成的评分差异统计。
- `diagnosis-summary.json`：确认 33 个案例均已诊断后生成的脱敏根因汇总。
- `ERROR-ANALYSIS.md`：中英双语结果解释。
- `MODIFICATION-SUGGESTIONS.md`：中英双语修改方案与下一次实验门槛。

私有错题集不会被 Git 跟踪。命令还会检查：如果私有输出位于 Git 仓库内但没有被 ignore，则拒绝写入。

复现命令模板：

```powershell
python -m benchmark.core.cli build-error-book `
  --run-dir <private-run-dir> `
  --gold <private-gold.csv> `
  --packet <private-packet-dir> `
  --private-output <gitignored-private-error-book.json> `
  --public-output experiments/records/DSAA3071-week5-candidate-v32-error-book/public-summary.json

python -m benchmark.core.cli summarize-error-book-diagnoses `
  --private-book <gitignored-private-error-book.json> `
  --diagnoses <gitignored-private-diagnoses.json> `
  --public-output experiments/records/DSAA3071-week5-candidate-v32-error-book/diagnosis-summary.json
```

安全门：

1. 只接受 run metadata 与 packet metadata 都明确标记为 `development`/`dev` 的输入。
2. 拒绝 dry-run、校验未通过、packet hash 不匹配、输出缺失/重复、gold 缺失/重复的记录。
3. 收录所有 33 个分数差异，不人工挑选“好看的案例”。
4. 技术运行错误单独计数，不当作评分认知错误。
5. 逐案诊断未覆盖全部案例时，拒绝生成公开诊断汇总。
6. 测试集没有读取或运行，本记录不能宣称测试集准确率。

## English

This record turns candidate-v3.2 development-split score discrepancies into a reproducible, case-reviewable grading error book. It does not analyze ordinary runtime failures. It analyzes validation-passed model outputs whose question scores still disagree with official per-question gold.

Two layers are strictly separated:

- Private layer: 33 question-level cases with anonymous student IDs, question IDs, gold and predicted scores, evidence, model rationale, flags, and bilingual root-cause diagnoses from the current Codex session. These remain under the gitignored private `Data/` tree.
- Public layer: aggregate statistics, cause counts, hashes, and methodological limits for seven students and 70 student-question pairs. It contains no student identifiers, answer text, evidence text, or case-level scores.

Primary outputs:

- `public-summary.json`: score-discrepancy statistics from the deterministic extractor.
- `diagnosis-summary.json`: privacy-safe cause aggregates produced only after all 33 cases are diagnosed.
- `ERROR-ANALYSIS.md`: bilingual interpretation.
- `MODIFICATION-SUGGESTIONS.md`: bilingual change options and next-run gates.

The private error book is never tracked by Git. The command also refuses to write a private output inside a Git repository unless that destination is ignored.

The command templates are shown above. Their gates require an explicitly labelled development run and packet, a non-dry-run validation-passed result, matching packet provenance, exact output/gold coverage, complete case selection, separation of technical failures, and complete diagnosis coverage before public aggregation. No held-out data was read or run, so this record makes no held-out accuracy claim.
