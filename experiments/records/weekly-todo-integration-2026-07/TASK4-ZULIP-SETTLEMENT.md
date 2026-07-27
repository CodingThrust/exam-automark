# TASK4 Zulip 结算稿：sci-brain 调研讲解与来源链

> 状态：已准备，尚未实际发送到 Zulip。
>
> Status: prepared, not yet posted to Zulip.
>
> Draft PR / 草稿 PR: https://github.com/CodingThrust/exam-automark/pull/34

## 中文

### TASK4 做了什么

TASK4 补完了上周 sci-brain survey 的两个缺口。

第一，知识讲解已经完成并合并：

- 解释了自动 prompt/skill 优化、textual gradient、DSPy/MIPRO、
  TextGrad/GEPA、反思式 skill library；
- 解释了 AES、ASAG、LLM rubric grader、LLM-as-a-judge 偏差、
  human-in-the-loop 和手写多模态评分；
- 明确区分了 agreement/validity、总分/逐题正确、confidence/calibration、
  marks/feedback；
- 将 Physics SkillOpt R4 的失败定位为相反误差方向被合并成一条全局规则，
  而不是泛泛地说 candidate 没通过。

第二，调研来源链已经工程化：

- 将 2026-07-19 的旧运行诚实标记为 `legacy_incomplete`；
- 明确记录旧运行缺失的三个字段：
  `tool.source_commit`、`discovery.queries`、
  `discovery.selection_log`；
- 没有用当前本机 sci-brain checkout 的 commit 冒充旧运行证据；
- 唯一 legacy exception 被写死到 2026-07-19 和这三个缺失字段，
  未来运行不能复用；
- 未来运行必须记录真实工具 commit、原始检索 query，以及逐来源的
  include/exclude 决定和原因；
- 两份报告声明了各自 14 和 18 个 scoped cite keys。

### 自动检查了什么

`benchmark.core.research_records` 现在可以审计 literature survey：

- manifest schema 和来源状态；
- 未来运行是否记录 40 位 Git commit；
- 是否保存 query 和纳入/排除日志；
- 旧运行是否只使用批准的历史例外；
- UTF-8、常见乱码和浮动 GitHub `main` 链接；
- `.knowledge` 与报告目录 BibTeX 的一致性；
- NOTES 和两份 Typst 报告是否存在未解析引用；
- 报告声明的 cite-key scope 是否和正文实际引用一致；
- 两份报告引用 union 是否覆盖 32 条 bibliography；
- PDF 是否存在且非空；
- arXiv ID 是否有效、是否跨 topic 重复。

### 改善了什么

以前的 manifest 能说明“调研跑过、用了 32 篇来源”，但无法回答：

- 当时到底用了哪个 sci-brain 版本？
- 实际搜索了什么？
- 为什么纳入这篇、排除另一篇？
- 报告删掉一个引用后，谁会发现？

现在旧记录不会伪装成完整可复现；未来记录则必须在运行时保存这些证据。
这提高的是调研可信度和可追踪性，不直接提高评分准确率。

### 如何帮助 exam-automark

1. 导师追问某个结论的来源时，可以定位到报告的 cite-key scope。
2. 工具升级后，可以区分代码变化和文献结论变化。
3. 后续 TASK5 接入 GitHub Actions 后，PR 不能静默删除引用或弱化来源记录。
4. TASK6–TASK8 使用调研建议设计错误 taxonomy、多模态比较和 candidate gate
   时，可以说明这些设计依据来自哪里。

### 验证

- committed literature manifest audit：通过，但明确显示批准的 legacy gap；
- committed tooling-survey manifest audit：通过；
- research-record 单元测试：9 项通过；
- core 回归测试：217 项通过；
- `git diff origin/main...HEAD --check`：通过。

### 限制与诚实边界

- 旧运行的准确 sci-brain commit、query 和 selection log 无法事后恢复；
- 原始 PDF 与全文缓存仍按版权和仓库体积要求保持 gitignored；
- 本 TASK 没有运行评分模型，也没有产生 accuracy 改善；
- 本文件是 Zulip 可粘贴结算稿，当前环境没有 Zulip connector，因此尚未发送；
- Draft PR #34 已创建，等待 review 和 merge。

### 下一步

TASK5：把 literature/tooling survey audit、隐私测试和 meaningful negative
controls 接入 GitHub Actions，作为 PR 自动质量门槛。

## English

### What TASK4 did

TASK4 closed two gaps in the previous sci-brain survey work.

First, the knowledge explanation was completed and merged. It explains automated
prompt and skill optimization, textual gradients, program optimizers,
reflection-based skill libraries, AES, ASAG, rubric-conditioned LLM grading,
LLM-judge bias, human-in-the-loop workflows, and multimodal handwritten
grading. It also connects the Physics SkillOpt R4 rejection to a concrete
failure: opposite error directions were collapsed into one global rule.

Second, the survey provenance was engineered:

- the 2026-07-19 run is honestly marked `legacy_incomplete`;
- the missing run-time commit, literal queries, and selection log are explicit;
- the current sci-brain checkout is not used as retroactive evidence;
- the only legacy exception is bound to the exact historical date and fields;
- future runs must record the real tool commit, queries, and per-source
  include/exclude decisions with reasons;
- the two reports declare scoped sets of 14 and 18 cite keys.

### What is now checked automatically

The research-record audit validates provenance status, future commit/query/
selection evidence, the historical exception, UTF-8 and mojibake, floating
GitHub references, bibliography equality, unresolved citations, declared versus
actual report scopes, full 32-source coverage, non-empty PDFs, and valid,
non-duplicated arXiv identifiers.

### What improved

The old record showed that the survey ran and used 32 sources, but could not
answer which exact tool revision and queries were used or why each source was
included or excluded. The new design does not pretend that the old record is
complete and prevents future runs from omitting the same evidence.

This improves research trustworthiness and traceability; it does not directly
improve grading accuracy.

### Project value

The project can trace advisor-facing claims to report-specific source scopes,
distinguish tool drift from evidence changes, and—after TASK5—prevent pull
requests from silently weakening the evidence record. TASK6–TASK8 can also cite
the research basis for the error taxonomy, multimodal comparison, and candidate
promotion gate.

### Validation

- committed literature manifest audit: passed with the approved legacy gap
  shown explicitly;
- committed tooling-survey manifest audit: passed;
- research-record unit tests: 9 passed;
- full core regression tests: 217 passed;
- `git diff origin/main...HEAD --check`: passed.

### Limitations and honesty boundary

- The original sci-brain commit, queries, and selection log cannot be recovered
  after the fact.
- Raw PDFs and rendered full-text caches remain gitignored for copyright and
  repository-size reasons.
- No grading model was run and no accuracy improvement is claimed.
- This is a Zulip-ready settlement draft. No Zulip connector is available in
  the current environment, so it has not been posted.
- Draft PR #34 is open for review and merge.

### Next

TASK5 will connect literature/tooling survey audits, privacy tests, and
meaningful negative controls to GitHub Actions as automatic pull-request gates.
