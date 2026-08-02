# TASK9B: DSAA3071 Week 5 Error Regression Suite

Status / 状态：**retired after human adjudication / 经人工裁决后退役**

The active target count is zero. The six historical targets and their 0/6
negative control are retained only as an audit trail; they must not gate or
tune future grading-skill versions. See HUMAN-ADJUDICATION.md and
human-adjudication-summary.json.

当前活动目标为 0。六个历史目标及其 0/6 负对照只作为审计记录保留，不得继续
阻止或驱动未来评分 skill。详细裁决见 HUMAN-ADJUDICATION.md 和
human-adjudication-summary.json。

## 中文

以下“目的、硬门禁与使用方法”是 2026-08-02 人工裁决前的历史设计，现已停用。

### 目的

该套件把 TASK9 中已经确认的高价值典型错误转成机器可检查的开发集回归门禁。以后每次修改主评分 skill，都必须重新运行同一批完整开发数据，并用本套件检查这些错误是否真正消失。

它包含六个私有目标案例：

- Q6：两个严重的 `unsupported_evidence_credit` 案例。模型不能因为出现关键词、多个 tape 或含糊的步骤描述，就推断答案已经给出公平遍历、分支寻址、接受条件或复杂度意识。
- Q9：四个 `rule_precedence_or_gate_error` 案例。当答案已经提供足够的整体证据时，模型必须执行整体满分规则，不能机械地累加示例性证据家族，也不能只因为答案简短而降档。

学生编号、答案文字、逐例分数和可关联的案例键只保存在 gitignored 的 `Data/` 中。GitHub 只保存选择规则、聚合数量、哈希和门禁结果。

### 硬门禁与观察指标

- Q6 与 Q9 都使用 `nonsevere_and_improved` 硬门禁：绝对误差必须比 v3.3 严格减小，并且不得再达到 5 分严重错误阈值。
- `exact_gold` 作为观察指标单独汇总，不决定套件是否通过。只有经课程负责人确认的标准案例，才适合在未来升级为精确一致硬门禁。

`expected_case_count` 是防漂移检查。如果源错误册或诊断标签意外变化，使选择器不再严格匹配 2 个 Q6 案例和 4 个 Q9 案例，套件构建会直接失败。

### 如何使用

构建私有套件和公开摘要：

```powershell
python -m benchmark.core.cli build-error-regression-suite `
  --private-book Data/DSAA3071/week5-benchmark-redaction-v3/error_book/C33-dev-reviewed-r1/error-book.private.json `
  --diagnoses Data/DSAA3071/week5-benchmark-redaction-v3/error_book/C33-dev-reviewed-r1/case-diagnoses.private.json `
  --policy experiments/records/DSAA3071-week5-error-regression-suite/regression-policy.json `
  --private-output Data/DSAA3071/week5-benchmark-redaction-v3/error_regressions/task9b-q6-q9-v1/suite.private.json `
  --public-output experiments/records/DSAA3071-week5-error-regression-suite/public-suite-summary.json
```

候选模型运行结束并生成完整私有错误册后：

```powershell
python -m benchmark.core.cli evaluate-error-regressions `
  --suite Data/DSAA3071/week5-benchmark-redaction-v3/error_regressions/task9b-q6-q9-v1/suite.private.json `
  --current-private-book Data/DSAA3071/week5-benchmark-redaction-v3/error_book/CANDIDATE-RUN/error-book.private.json `
  --private-output Data/DSAA3071/week5-benchmark-redaction-v3/error_regressions/CANDIDATE-RUN/evaluation.private.json `
  --public-output experiments/records/CANDIDATE-RECORD/error-regression-evaluation.json
```

命令在全部六例通过时返回退出码 `0`，否则返回 `1`，因此可以直接接入 CI 或 autoresearch acceptance gate。

### 不能怎样解释

六例全部通过只是候选 skill 的必要条件，不是充分条件。仍然必须检查完整 70 对开发数据的总体 MAE、严重错误数量、Q1–Q4 regression 和所有新错误。该套件没有使用 held-out/test 数据，也没有运行新模型。

## English

### Purpose

This suite converts the high-value typical errors confirmed in TASK9 into machine-checkable development regressions. Every future main grading-skill change must rerun the complete comparable development condition and evaluate these targets.

It contains six private targets:

- Q6: two severe `unsupported_evidence_credit` cases. Keywords, multiple tapes, or vague step descriptions must not be treated as evidence of fair exploration, branch addressing, acceptance, or overhead awareness.
- Q9: four `rule_precedence_or_gate_error` cases. When an answer supplies sufficient holistic evidence, the grader must execute the holistic full-credit rule instead of mechanically adding illustrative evidence families or downgrading brevity.

Student identifiers, answer text, case-level scores, and linkable keys remain under gitignored `Data/`. GitHub stores only selectors, aggregate counts, hashes, and gate results.

### Hard gate and observation

- Both Q6 and Q9 use the `nonsevere_and_improved` hard gate: absolute error must strictly improve over v3.3 and remain below the five-point severe-error threshold.
- Exact gold agreement is reported as a separate observation and does not decide suite passage. It should become a hard gate only for a course-owner-adjudicated exemplar.

`expected_case_count` is a drift guard. Suite construction fails if source records or diagnosis labels no longer select exactly two Q6 and four Q9 cases.

### Usage

Use the PowerShell commands in the Chinese section; all paths are repository-relative and work from the repository root. The evaluator exits `0` only when all six targets pass, so it can be wired into CI or an autoresearch acceptance gate.

### Interpretation limit

Passing all six targets is necessary, not sufficient. The complete 70-pair development run must still satisfy aggregate MAE, severe-error, Q1–Q4 regression, and new-error gates. No held-out/test data or new model run is used here.
