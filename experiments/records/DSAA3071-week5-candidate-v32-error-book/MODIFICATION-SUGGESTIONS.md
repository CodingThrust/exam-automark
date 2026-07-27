# 修改建议与下一步决策 / Modification Suggestions and Next Decision

## 中文版

### 推荐方案：A，然后 C

我建议先执行 **A：修正评分合同并做 candidate-v3.3 的一次可解释改进**，随后执行 **C：对 Q8 表示歧义做直接多模态对照**。不建议把 33 个差异全部塞进 prompt 里追求表面 MAE。

### A. 先裁决合同，再修改确认的模型错误（推荐）

先由课程负责人回答三个封闭问题：

1. Q8：epsilon 作为空白带初始化是否算实际输出？如果答案真的输出 epsilon，官方应是 0、上限 5，还是只小扣分？
2. Q6：满分是否需要 overhead/supporting element？如果不需要，element 总分如何从 17 映射到 20？
3. Q10：两项正确、一项错误时，官方 12 分如何由 rubric 的 `0/1/3/5` 档位复现？

裁决后只做一批有证据的 candidate-v3.3 改动：

- Q6：关键词不等于 demonstrated；每个要素必须引用明确动作或逻辑。不得因出现 BFS/tree 自动补出 address、acceptance 或 overhead。
- Q7：明确一个完整构造的保底分；两个构造均正确时，允许官方风格省略非成员说明。
- Q8：接受“先构造 recognizer、再引用 Q7 得到 enumerator”的有效间接路径；触发 invalid-extra-output cap 前必须先区分初始化与实际输出。
- Q9：`full_credit_rule` 优先于逐 evidence-family 相加；答案简短不能自动把正确语义从 demonstrated 降成 mentioned。
- Q10：加入与官方风格一致的三小问锚点。
- Q1-Q4：禁止改规则，作为零回归区。

### B. 直接把全部 33 个差异用于 prompt 优化（不推荐）

好处是操作快，可能迅速降低开发集 MAE。问题是至少 9 例属于 rubric-gold 不一致、1 例属于 text-only 无法裁决；照单全收会把相互冲突的监督信号写进 skill，得到不可解释的过拟合。

### C. 对 Q8 做 transcript 与直接多模态配对（A 后执行）

同一案例运行两条输入路径：

- reviewed transcript → grading；
- original page/image → direct multimodal grading。

保持模型、rubric、温度、输出 schema 和案例集合一致。重点判断：

- `2n` 是否是丢失的 `2^n`；
- epsilon 是空带初始化标记还是被实际打印；
- 直接多模态能否减少 Q8 的 5 个严重差异。

这会给后续 TASK7 的 Codex CLI/Claude Code 多模态比较提供真实、已知困难的案例，而不是随机样本。

### candidate-v3.3 的预注册通过门槛

仍在同一开发集上做 paired 比较，不读取测试集。建议同时满足：

1. question MAE `< 2.557143`；
2. student-total MAE `< 14.428571`；
3. severe-error rate `<= 0.228571`，且严重错误数不得高于 16；
4. exact agreement `> 0.528571`；
5. Q1-Q4 继续 100% 完全一致；
6. Q6 的平均高估明显下降；
7. Q8/Q9 的严重错误合计低于 10；
8. 公开报告同时给出全体 70 对指标和经裁决原因分层，不能只报挑选后的 13 例。

### flags 与人工复核门

下一版不能只靠 confidence：

- medium/low 自动进入复核；
- Q8/Q9 的非满分或高影响扣分自动进入复核；
- 触发 material-error cap、使用间接构造、或 full-credit-rule 与要素加和冲突时必须输出机器可检查的 flag；
- 没有 flag 不代表安全，因为当前 62.5% 的严重差异没有 flag。

### 对项目的实际帮助

这套顺序把“提升正确率”拆成可验证的因果链：先保证 benchmark 合同可解释，再修模型确定缺陷，再用同一开发集做配对改进，最后才进入多模态与测试集。它也为之后自建 skill optimization loop 提供了真正可自动化的输入：完整错题集、根因标签、允许修改的目标案例、不可触碰的回归区和明确通过门槛。

## English Version

### Recommended path: A, then C

Run **A: adjudicate the scoring contract and make one interpretable candidate-v3.3 improvement**, followed by **C: a direct-multimodal comparison for Q8 representation ambiguity**. Do not push all 33 discrepancies into a prompt simply to optimize surface MAE.

### A. Adjudicate the contract, then fix confirmed model errors (recommended)

The course owner should first answer three closed questions:

1. Q8: Does epsilon as blank-tape initialization count as an actual output? If epsilon is printed, should official scoring be zero, capped at five, or only slightly reduced?
2. Q6: Is overhead/the supporting element required for full credit? If it is not, how do essential-element weights totaling 17 map to 20?
3. Q10: How is official score 12 reconstructed from the `0/1/3/5` grid when two subparts are correct and one is wrong?

Candidate-v3.3 should then make only evidence-backed changes: require explicit Q6 evidence rather than keyword completion; anchor Q7 construction credit and official-style tolerance; accept valid indirect Q8 recognizer-to-enumerator constructions and disambiguate initialization before applying a cap; make the Q9 full-credit rule override mechanical family counting and prohibit automatic brevity downgrades; add an official-style Q10 anchor; and freeze Q1-Q4 as a zero-regression zone.

### B. Optimize on all 33 discrepancies immediately (not recommended)

This is fast and may reduce development MAE, but at least nine cases are rubric-gold mismatches and one cannot be settled from text-only input. Treating all discrepancies as model errors would inject contradictory supervision into the skill and produce uninterpretable overfitting.

### C. Pair reviewed-transcript and direct-multimodal Q8 runs (after A)

Run the same cases through reviewed-transcript grading and original-page direct multimodal grading while holding the model, rubric, temperature, output schema, and case set constant. Test whether `2n` is a lost `2^n`, whether epsilon is initialization or actual output, and whether multimodal input reduces the five severe Q8 discrepancies. This also supplies TASK7's Codex CLI versus Claude Code comparison with grounded difficult cases rather than random samples.

### Pre-registered candidate-v3.3 gate

Use the same development split for a paired comparison and do not read held-out data. Require question MAE below `2.557143`, student-total MAE below `14.428571`, severe-error rate at or below `0.228571` with no more than 16 severe cases, exact agreement above `0.528571`, continued 100% agreement on Q1-Q4, a material reduction in Q6 over-scoring, fewer than ten combined severe Q8/Q9 errors, and reporting of both all-70 metrics and adjudicated cause strata rather than only the selected 13 model-error cases.

### Flags and review gates

Medium and low confidence should trigger review, but confidence is insufficient. Non-full-credit or high-impact Q8/Q9 decisions, material-error caps, indirect constructions, and full-credit-rule/element-sum conflicts need machine-checkable flags. Absence of a flag cannot mean safe because 62.5% of current severe discrepancies have no flag.

### Project value

This sequence converts “improve accuracy” into an auditable causal chain: make the benchmark contract interpretable, fix confirmed model defects, run a paired development improvement, and only then proceed to multimodal and held-out evaluation. It also creates the right automated inputs for a future project-owned skill optimization loop: a complete error book, cause labels, allowed optimization targets, protected regression zones, and explicit acceptance gates.
