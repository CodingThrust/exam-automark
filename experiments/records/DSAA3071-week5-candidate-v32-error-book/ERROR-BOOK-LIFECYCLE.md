# Skill 错题生命周期 / Skill Error-Book Lifecycle

## 中文

### 强制规则

从 candidate-v3.2 开始，每次修改主评分 skill 都必须同步更新错题册。只修改 `.agents/skills/grade-homework` 或 `.claude/skills/grade-homework` 而没有完成下列产物，不算一次完成的 skill 更新，CI 应当失败。

每个新版本必须：

1. 冻结新的 skill snapshot，并保持 Codex 与 Claude 镜像一致。
2. 在同一 development split、相同输入模式和可比运行条件下重新评分；不得用 held-out/test 纠错。
3. 生成完整的私有机器可读错题集，收录所有 gold 与预测不一致的学生-题目对。
4. 逐案诊断全部错误，为每例标记固定 `mechanism_code`，并生成私有可阅读的 `TYPICAL-ERROR-CASES.private.md`。典型部分必须优先保留人工指定关键例，再覆盖受影响题目、根因和严重高估/低估；文末保留完整错题索引。
5. 与上一 skill 版本比较，并把每个学生-题目对归入：
   - `resolved`：旧版错、新版与 gold 一致；
   - `regression`：旧版一致、新版出错；
   - `persistent_improved`：仍错，但绝对分差减小；
   - `persistent_unchanged`：绝对分差不变；
   - `persistent_worsened`：仍错且绝对分差增大。
6. 重新计算 confidence、flags、错误机制和人工复核策略的脱敏审计；不能沿用上一版的自我评估结论。
7. 对 registry 中全部已登记的典型错题回归套件运行 `evaluate-error-regressions`。任何一个套件未全部通过，都不能把 candidate 登记为新的 active skill。
8. 生成脱敏公开汇总、回归结果和版本差异，随后把新版本追加到 `experiments/records/grading-skill-error-book-registry.json`。不得覆盖旧版本目录。

### CI 如何防止遗漏

`check-error-book-registry` 会重建当前 `.agents` 和 `.claude` 评分 skill 的规范哈希，并与 registry 的 active entry 比较。若 skill 发生变化但没有新的 snapshot、完整诊断、confidence/flag/taxonomy 审计、公开汇总和 registry 条目，安全检查会失败。第一版 candidate-v3.2 只建立基线；从下一版开始，缺少上一版对比文件或任一已登记回归套件的公开通过结果都会失败。

Registry 只记录私有典型错题册的 SHA-256，不记录私有路径或学生编号。公开 GitHub 只能保存汇总；含匿名学生编号和答案证据的完整错题册必须留在 gitignored `Data/` 或私有数据仓库。

### 当前可阅读错题

candidate-v3.2 的私有报告位于：

`Data/DSAA3071/week5-benchmark-redaction-v3/error_book/C32-dev-reviewed-r1/TYPICAL-ERROR-CASES.private.md`

它展开 12 个典型案例，包含匿名学生、题号、原始证据、模型理由、gold、预测分数、根因和建议动作，并在文末列出全部 33 个评分差异。该文件不可提交到公开 GitHub。

### 更新命令

```powershell
python -m benchmark.core.cli render-typical-error-cases `
  --private-book <new-private-error-book.json> `
  --diagnoses <new-private-diagnoses.json> `
  --output <gitignored-new-version>/TYPICAL-ERROR-CASES.private.md

python -m benchmark.core.cli compare-error-books `
  --previous-private-book <previous-private-error-book.json> `
  --current-private-book <new-private-error-book.json> `
  --private-output <gitignored-new-version>/iteration-delta.private.json `
  --public-output <new-public-record>/iteration-delta.public.json

python -m benchmark.core.cli audit-error-confidence `
  --run-dir <new-private-run-dir> `
  --private-book <new-private-error-book.json> `
  --diagnoses <new-private-diagnoses.json> `
  --public-error-summary <new-public-record>/public-summary.json `
  --public-output <new-public-record>/confidence-taxonomy-summary.json `
  --markdown-output <new-public-record>/CONFIDENCE-ANALYSIS.md

python -m benchmark.core.cli evaluate-error-regressions `
  --suite <gitignored-regression-suite>/suite.private.json `
  --current-private-book <new-private-error-book.json> `
  --private-output <gitignored-new-version>/regression-evaluation.private.json `
  --public-output <new-public-record>/regression-evaluation.json

python -m benchmark.core.cli check-error-book-registry `
  --registry experiments/records/grading-skill-error-book-registry.json `
  --repo-root .
```

## English

### Mandatory rule

Starting with candidate-v3.2, every main grading-skill change must update the error book. Editing `.agents/skills/grade-homework` or `.claude/skills/grade-homework` without the complete artifacts below is not a completed skill update and must fail CI.

Each new version must:

1. Freeze a new skill snapshot and keep the Codex and Claude mirrors synchronized.
2. Re-grade the same development split under the same input mode and comparable run conditions. Held-out or test data must not drive the update.
3. Generate a complete private machine-readable error book containing every gold/prediction disagreement.
4. Diagnose every error, assign a fixed `mechanism_code`, and generate a private readable `TYPICAL-ERROR-CASES.private.md`. The full cases must prioritize reviewer-nominated cases and cover affected questions, causes, and severe over/under-scoring, followed by a complete error index.
5. Compare with the predecessor and classify each student-question pair as `resolved`, `regression`, `persistent_improved`, `persistent_unchanged`, or `persistent_worsened`.
6. Recompute the privacy-safe confidence, flag, error-mechanism, and review-policy audit. A new version must not inherit its predecessor's self-assessment conclusions.
7. Run `evaluate-error-regressions` against every suite registered in the registry. A candidate cannot become the active skill if any suite does not pass completely.
8. Generate privacy-safe public summaries, regression results, and a version delta, then append the version to `experiments/records/grading-skill-error-book-registry.json`. Prior version directories must not be overwritten.

### CI enforcement

`check-error-book-registry` rebuilds the canonical hash of the current `.agents` and `.claude` grading skills and compares it with the active registry entry. If the skill changes without a new snapshot, complete diagnosis, confidence/flag/taxonomy audit, public summaries, and registry entry, the safety check fails. Candidate-v3.2 initializes the baseline; every later entry must also provide a predecessor comparison and a passing public evaluation for every registered regression suite.

The registry stores only the SHA-256 of the private readable report, never its private path or student identifiers. Public GitHub contains aggregates only. Full cases with anonymous student IDs and answer evidence remain in gitignored `Data/` or the private data repository.

### Current readable cases

The private candidate-v3.2 report is:

`Data/DSAA3071/week5-benchmark-redaction-v3/error_book/C32-dev-reviewed-r1/TYPICAL-ERROR-CASES.private.md`

It expands 12 cases with anonymous student, question, answer evidence, model rationale, gold, prediction, cause, and recommended action, followed by an index of all 33 discrepancies. It must not be committed to public GitHub.

The update commands are shown in the Chinese section and are platform-neutral Python CLI commands wrapped with PowerShell line continuation only for readability.
