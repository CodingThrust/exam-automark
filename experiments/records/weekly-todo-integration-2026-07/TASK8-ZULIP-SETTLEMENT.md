# TASK8 Zulip 结算草稿 / TASK8 Zulip Settlement Draft

> 状态 / Status: `ready_not_posted`

## 中文

### TASK8：candidate-v3.2 批作业错题集与缺陷审计

**做了什么**

- 新增确定性 `build-error-book` 命令，只接受开发集、非 dry-run、校验通过且 packet provenance 匹配的运行。
- 从 DSAA3071 Week 5 candidate-v3.2 的 70 个开发集学生-题目对中完整提取 33 个评分差异，没有挑选案例。
- 私有错题集保留匿名学生编号、题号、gold、预测分数、证据、理由、confidence 和 flags，并存放在 gitignored `Data/`。
- 当前 Codex 会话逐案复核全部 33 例，并提供完整中英双语诊断；公开仓库只保存脱敏根因计数。
- 新增公开隐私审计、完整诊断覆盖门、Git ignore 私有输出门以及 15 个相关测试。

**改善了什么**

- 把“模型不准”拆成四类可行动原因：13 例模型评分错误、10 例分数档位校准、9 例 rubric-gold 不一致、1 例文字表示歧义。
- 发现 Q8/Q9 占 10/16 个严重差异，Q6 为 7/7 不一致且系统性高估。
- 发现 10/16 个严重差异没有任何 flag；confidence 有方向性，但 high 仍有 5 个严重差异。
- 运行报错没有混入认知失败分析：本次技术失败为 0。

**最重要的新认知**

- 不能把 33 个差异全部用来优化 skill。Q8 出现近似答案官方一例 0 分、一例满分；Q6 rubric 的满分门槛与要素总分冲突；Q10 官方 12 分不能由离散要素档位复现。先裁决这些合同问题，否则会把 benchmark 噪声学进 skill。
- 可直接改进的模型问题包括：Q6 关键词过度给分、Q8 不接受有效间接构造且过早触发 cap、Q9 机械计算证据族并因简短自动降档。

**如何帮助项目**

- 为主线准确率改进提供完整错题集、逐案根因、回归保护区和 candidate-v3.3 的预注册通过门。
- 为 TASK6 的错误 taxonomy/confidence calibration 提供真实案例。
- 为 TASK7 的 transcript 与 direct multimodal 比较提供 Q8 已知困难案例。
- 为以后自建 skill optimization loop 提供可自动化的输入和验收标准。

**失败、限制与禁止性结论**

- 没有运行或读取测试集；不能报告测试集准确率。
- 官方 gold 没有逐题评语，9 个 rubric-gold 冲突只能定位，最终需课程负责人裁决。
- 逐案诊断由当前 Codex 会话完成，模型 ID 未由客户端暴露；22 例诊断为 high confidence，11 例为 medium confidence。
- 私有逐案材料不能提交到公开 GitHub 或直接贴进公开 Zulip 消息。

**证据**

- `experiments/records/DSAA3071-week5-candidate-v32-error-book/README.md`
- `experiments/records/DSAA3071-week5-candidate-v32-error-book/ERROR-ANALYSIS.md`
- `experiments/records/DSAA3071-week5-candidate-v32-error-book/MODIFICATION-SUGGESTIONS.md`
- `experiments/records/DSAA3071-week5-candidate-v32-error-book/public-summary.json`
- `experiments/records/DSAA3071-week5-candidate-v32-error-book/diagnosis-summary.json`
- 私有：`Data/.../error_book/C32-dev-reviewed-r1/`

**下一决策**

采用报告中的 A→C：先请课程负责人裁决 Q8 epsilon、Q6 满分条件和 Q10 分数网格；随后只针对确认的模型错误做 candidate-v3.3，再对 Q8 做 reviewed-transcript 与 direct-multimodal 配对。

## English

### TASK8: Candidate-v3.2 grading error book and defect audit

**What was done**

- Added a deterministic `build-error-book` command that accepts only explicit development, non-dry-run, validation-passed runs with matching packet provenance.
- Exhaustively extracted all 33 score discrepancies from 70 DSAA3071 Week 5 candidate-v3.2 development student-question pairs.
- Kept anonymous student IDs, question IDs, gold and predicted scores, evidence, rationales, confidence, and flags only in the gitignored private error book.
- Reviewed all 33 cases in the current Codex session with complete bilingual diagnoses; only privacy-safe cause aggregates are public.
- Added public privacy auditing, complete-diagnosis coverage gating, private-output Git-ignore gating, and 15 relevant tests.

**What improved**

- Replaced the vague statement “the model is inaccurate” with four actionable strata: 13 model grading errors, ten score-band calibration cases, nine rubric-gold mismatches, and one text-representation ambiguity.
- Located 10 of 16 severe discrepancies in Q8/Q9 and found Q6 wrong on 7/7 with systematic over-scoring.
- Found that ten of 16 severe discrepancies have no flag. Confidence is directionally useful, but high-confidence output still contains five severe discrepancies.
- Kept runtime failures separate from cognitive grading failures; this run has zero technical failures.

**Most important new knowledge**

All 33 discrepancies must not be used blindly for skill optimization. Q8 contains near-equivalent text answers with official scores of zero and full credit; Q6 has a contradiction between its full-credit gate and element weights; and Q10 official score 12 cannot be reconstructed from the discrete element grid. These benchmark-contract issues require adjudication before tuning. Direct model defects include Q6 keyword over-credit, Q8 rejection of valid indirect constructions and premature caps, and Q9 mechanical evidence-family counting plus automatic brevity downgrades.

**Project value**

The artifacts provide the main accuracy track with a complete error book, case causes, a protected regression zone, and pre-registered candidate-v3.3 gates. They ground TASK6 taxonomy/confidence work, provide difficult Q8 cases for TASK7 transcript/direct-multimodal comparison, and supply automated inputs and acceptance criteria for a future project-owned skill optimization loop.

**Failures, limits, and prohibited claims**

No held-out data was read or run, so no held-out accuracy claim is permitted. Official gold has no question-level comments, so nine rubric-gold conflicts require course-owner adjudication. Diagnoses were made in the current Codex session; the client did not expose a model ID. Twenty-two diagnoses are high-confidence and eleven medium-confidence. Private case material must not be committed to public GitHub or pasted into a public Zulip settlement.

**Evidence**

The public evidence paths are the five files under `experiments/records/DSAA3071-week5-candidate-v32-error-book/` listed in the Chinese section. Private case material remains under the gitignored `Data/.../error_book/C32-dev-reviewed-r1/`.

**Next decision**

Follow A→C from the recommendation report: adjudicate Q8 epsilon policy, the Q6 full-credit contract, and the Q10 scoring grid; then build candidate-v3.3 only from confirmed model errors and run a paired reviewed-transcript/direct-multimodal Q8 comparison.
