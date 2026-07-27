# Candidate-v3.2 错题与缺陷分析 / Candidate-v3.2 Error and Defect Analysis

## 中文版

### 结论

candidate-v3.2 在本次 7 人开发集上共有 70 个学生-题目对，其中 37 个与官方分数完全一致，33 个不一致；16 个差异达到“单题绝对分差至少 5 分”的严重错误标准。逐案复核表明，这 33 个差异不能全部叫作“模型判错”：

| 当前根因标签 | 案例数 | 含义 |
|---|---:|---|
| `model_grading_error` | 13 | 现有文字证据和规则足以支持官方方向，但模型误识别证据、误用门槛或错误加减分 |
| `score_band_calibration` | 10 | 概念方向接近，主要差在部分理解、证明完整度或官方风格容忍度对应多少分 |
| `rubric_gold_misalignment` | 9 | candidate-v3.2 的明示 rubric 无法复现官方 gold，需先裁决评分合同 |
| `input_representation_ambiguity` | 1 | text-only 无法可靠表达数学记号或初始化/输出区别，需查看原图 |

因此，直接用全部 33 个差异修改 skill 会把 benchmark 的不一致也学进去。下一次改进应优先处理 13 个较可信的模型评分错误，同时先裁决 9 个 rubric-gold 冲突。

### 去哪里看具体典型错题

公开 GitHub 不能展示学生逐题证据。可直接阅读的私有报告是 `Data/DSAA3071/week5-benchmark-redaction-v3/error_book/C32-dev-reviewed-r1/TYPICAL-ERROR-CASES.private.md`。它完整展开 12 个典型案例：匿名学生编号、题号、答案证据、模型评分理由、gold、预测分、根因、入选原因和建议动作；文末还有全部 33 个差异的索引。

典型案例包括 Q6 关键词 “dovetailing” 导致无证据高分、Q6 rubric 内部矛盾、Q7 完整构造被机械扣分、Q8 两个 epsilon 答案对应 0 分与满分的冲突对、Q9 三类语义证据只识别一类，以及 Q10 官方风格容忍度缺失。该文件在 gitignored `Data/` 中，不能提交到公开 GitHub。

### 错误集中在哪里

整体指标：

- 单题完全一致率：`0.528571`（37/70）。
- 单题 MAE：`2.557143`。
- 严重错误率：`0.228571`（16/70）。
- 学生总分 MAE：`14.428571`。
- 低估 22 例，高估 11 例，主要偏差方向是低估。
- 技术运行错误：0；因此这里的 33 例都是评分差异，不是 API、解析或文件错误。

题目层面：

| 题目 | 差异数 | 严重差异数 | MAE | 平均有符号误差 | 主要问题 |
|---|---:|---:|---:|---:|---|
| Q1-Q4 | 0 | 0 | 0 | 0 | 当前稳定区，后续修改必须防回归 |
| Q5 | 5 | 1 | 2.714286 | -2.142857 | 官方整体容忍度与逐要素门槛不完全一致 |
| Q6 | 7 | 2 | 4.428571 | +4.142857 | 全部案例不一致，且系统性高估；关键词/隐含证据给分过多，rubric 还有内部矛盾 |
| Q7 | 5 | 2 | 2.428571 | +0.142857 | 双向证明的局部给分档位不稳 |
| Q8 | 7 | 5 | 5.571429 | -4.142857 | 严重低估、间接构造识别不足、epsilon 与幂记号无法仅靠文字稳定裁决 |
| Q9 | 6 | 5 | 9.0 | -9.0 | 最大 MAE；模型机械数“证据族”，没有执行 broad-valid-evidence 的满分规则 |
| Q10 | 3 | 1 | 1.428571 | -1.428571 | 官方分数无法由离散要素分值复现，另有官方风格容忍度问题 |

Q8 与 Q9 合计贡献 10/16 个严重差异（62.5%），是第一优先级。Q6 虽然严重差异较少，但 7/7 全错且平均高估 4.14 分，说明方向性机制有问题。

### 三个最重要的典型发现

1. **Q8 的 gold/rubric 不能直接用于盲调。** 两个文字上都明确输出 epsilon 的答案，官方分数却分别出现 0 分和满分；同时 `2n` 可能是上标/幂号丢失。这里必须由课程负责人对照原图裁决“epsilon 是初始化还是实际输出”“2n 是否是 2^n”，然后再决定 skill 规则。

2. **Q6 同时存在模型高估和 rubric 内部冲突。** 模型会把“tree/BFS”等词当作完整机制，为未展示的 branch address、acceptance 或 overhead 给分。另一方面，rubric 又说三个 essential element 足以满分，但它们的分值只合计 17，supporting element 不是满分必需却占 3 分。先修合同，才能判断 17、20 或官方分数谁正确。

3. **Q9 的模型没有服从最高层规则。** Q9 明确说 broad valid evidence 足以得高分，不要求逐一覆盖列出的证据族；模型仍机械按三个族相加，并因答案简短自动降档。这是可直接修改的模型评分错误。

### Confidence 与 flags 说明了什么

confidence 有方向信息，但不能当正确性证明：

| Confidence | 对数 | 差异数 | 严重差异数 | 完全一致率 | MAE |
|---|---:|---:|---:|---:|---:|
| high | 47 | 13 | 5 | 0.723404 | 1.212766 |
| medium | 22 | 19 | 10 | 0.136364 | 5.136364 |
| low | 1 | 1 | 1 | 0 | 9.0 |

medium/low 确实更危险，但 high 仍有 5 个严重差异。因此“只人工复核低 confidence”会漏错。

flags 的覆盖更差：33 个差异中 19 个没有任何 flag，16 个严重差异中 10 个没有 flag。也就是说，现有 flags 漏掉 62.5% 的严重差异，不能作为唯一的人工复核入口。

### 限制

- 这是同一 7 人开发集上的诊断，不是测试集结果。
- 逐案根因由当前 Codex 会话依据 official gold、candidate-v3.2 rubric、reviewed transcript 和模型理由给出；22 例为 high confidence、11 例为 medium confidence，仍需课程负责人裁决 benchmark 合同。
- 官方 gold 没有逐题评语，所以 rubric-gold 冲突只能定位，不能由模型单方面最终裁决。
- text-only 无法回答的表示问题必须放到直接多模态对照中解决。

## English Version

### Conclusion

Candidate-v3.2 produced 70 student-question pairs on this seven-student development split. Thirty-seven exactly match official scores and 33 disagree; 16 meet the severe-error definition of an absolute question-score error of at least five points. Case-by-case review shows that the 33 discrepancies are not all model grading failures:

| Provisional primary cause | Cases | Meaning |
|---|---:|---|
| `model_grading_error` | 13 | The text and scoring contract support the official direction, but the model misreads evidence, misapplies a gate, or awards/deducts unsupported credit |
| `score_band_calibration` | 10 | The conceptual direction is close, but partial understanding, proof completeness, or official-style tolerance maps to a different score band |
| `rubric_gold_misalignment` | 9 | The explicit candidate-v3.2 rubric cannot reproduce official gold and requires contract adjudication |
| `input_representation_ambiguity` | 1 | Text-only input cannot reliably preserve notation or distinguish initialization from output |

Blindly tuning on all 33 discrepancies would teach benchmark inconsistencies to the skill. The next improvement should target the 13 better-supported model errors and adjudicate the nine rubric-gold conflicts first.

### Where to read the concrete typical cases

Public GitHub cannot expose student-level answer evidence. The readable private report is `Data/DSAA3071/week5-benchmark-redaction-v3/error_book/C32-dev-reviewed-r1/TYPICAL-ERROR-CASES.private.md`. It expands 12 cases with anonymous student ID, question, answer evidence, model rationale, gold, prediction, cause, selection reason, and recommended action, followed by an index of all 33 discrepancies.

The selected cases include unsupported Q6 keyword credit for “dovetailing,” an internally contradictory Q6 rubric, mechanical under-scoring of a complete Q7 construction, the conflicting Q8 epsilon pair receiving official zero and full credit, failure to recognize three semantic evidence types in Q9, and missing official-style tolerance in Q10. The file remains in gitignored `Data/` and must not be committed to public GitHub.

### Error concentration

Overall exact agreement is `0.528571` (37/70), question MAE is `2.557143`, severe-error rate is `0.228571` (16/70), and student-total MAE is `14.428571`. There are 22 under-scores and 11 over-scores, so the dominant bias is under-scoring. Technical failure count is zero; all 33 cases are scoring disagreements, not API, parsing, or file failures.

Q1-Q4 are stable with zero discrepancies and must be protected from regression. Q5 has five discrepancies and mainly exposes holistic-tolerance versus element-gate differences. Q6 is wrong on all seven cases, has a +4.142857 signed bias, and combines implicit-evidence over-credit with an internally inconsistent rubric. Q7 has unstable proof-locality bands. Q8 has seven discrepancies, five severe errors, a 5.571429 MAE, indirect-construction failures, and unresolved epsilon/notation ambiguity. Q9 has the largest MAE at 9.0, with five severe errors caused largely by mechanical evidence-family counting. Q10 combines one model tolerance issue with official scores that cannot be reconstructed from the discrete scoring grid.

Q8 and Q9 contribute 10 of 16 severe errors (62.5%) and are the first priority. Q6 has fewer severe cases but is wrong on 7/7 and systematically over-scores, which indicates a directional mechanism defect.

### Three most important case-derived findings

1. **Q8 gold and rubric are unsafe for blind tuning.** Two text answers that both explicitly output epsilon receive official scores of zero and full credit, respectively. In addition, `2n` may reflect lost superscript notation. A course owner must compare the original image and adjudicate epsilon and exponent policy before a skill change.

2. **Q6 combines model over-credit with a rubric contradiction.** The model treats terms such as “tree” and “BFS” as a complete mechanism and credits branch addressing, acceptance, or overhead that was not demonstrated. Meanwhile, the rubric says the three essential elements suffice for full credit although their weights sum to 17, while the three-point supporting element is declared unnecessary for full credit. The contract must be repaired before deciding which score is correct.

3. **Q9 does not obey its top-level rule.** The rule explicitly permits broad valid evidence without exact coverage of every listed family. The model still performs additive family counting and automatically downgrades concise claims. This is a directly actionable model grading error.

### Confidence and flags

Confidence is directionally informative but not proof of correctness. High-confidence outputs have 72.34% exact agreement, but still contain 13 discrepancies and five severe errors. Medium outputs have 13.64% exact agreement, 19 discrepancies, and ten severe errors. The single low-confidence output is severe. Reviewing only low-confidence work would therefore miss important errors.

Flags are weaker still. Nineteen of 33 discrepancies have no flag, including ten of 16 severe errors. The current flag system misses 62.5% of severe discrepancies and cannot be the sole manual-review gate.

### Limitations

This is development-split diagnosis, not held-out performance. Root causes were assigned by the current Codex session using official gold, the candidate-v3.2 rubric, reviewed transcripts, and model rationales. Twenty-two diagnoses are high-confidence and eleven medium-confidence, but course-owner adjudication remains necessary. Official gold provides no per-question comments, so rubric-gold conflicts can be located but not finally resolved by the model alone. Representation questions that text cannot settle must be tested through the direct multimodal path.
