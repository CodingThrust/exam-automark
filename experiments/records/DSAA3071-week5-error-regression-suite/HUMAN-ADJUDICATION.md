# TASK8A Human Adjudication / TASK8A 人工裁决

## 中文

### 结论

人工对照原始作答、人工复核 transcript、题目和官方解答后，旧回归套件中的六例都不能继续当作“已确认的模型错误”。本套件因此退役，活动硬门禁从 6 例改为 0 例。历史选择器、公开摘要和 v3.3 负对照保留，用于说明我们曾经如何得出判断以及为什么后来修正。

这不是说模型一定正确，而是说现有证据不能把“模型评分错误”与“gold/评分口径问题”可靠分开。未经人工确认的分差不应驱动 skill 调参。

### 六例复核

| 题目 | 复核数 | 确认模型错误 | 处理 |
|---|---:|---:|---|
| Q6 | 2 | 0 | 一例的技术方法有效但官方分数可疑；另一例属于普通评分宽松度差异。两例均退出硬门禁。 |
| Q9 | 4 | 0 | 对循环论证、证据不具体或不明确的扣分均有可辩护性；另有一例只有三分差。四例均退出硬门禁。 |

因此，旧负对照的 0/6 只能说明 v3.3 没有满足当时按 gold 定义的门槛，不能再解释为“它重现了六个真实模型错误”。Candidate-v3.3 仍因原预注册总体安全门槛未通过而保持 rejected；本次裁决不会倒推接受它。

### Q8 输入与评分合同复核

另外复核了三个 Q8 差异：

- 一例原图写的是 2^n，人工 transcript 丢失上标后变成 2n。模型依据损坏文本扣分，根因属于转录/输入管线。
- 题面公式 0^(2^n), n >= 0 产生长度 1、2、4……，不含 epsilon；但题面示例和官方解答又列出 epsilon。这是题目与解答内部的评分合同冲突。
- 因为上述冲突，其余两例无法安全归类为评分模型错误，应该用于“reviewed transcript 对 direct multimodal”的输入模式对照，而不是直接改评分 skill。

### 今后的准入规则

典型错题进入硬回归门禁前必须依次满足：

1. 人工查看原始作答，确认 transcript 没有丢失数学符号、版面关系或图像信息；
2. 核对题目、rubric、官方解答和 gold 没有互相矛盾；
3. 排除导师允许的普通评分宽松度，优先关注非平凡、非主观、可复现的错误；
4. 人工明确确认“这是模型错误”，再冻结为机器可检查的回归目标。

## English

### Conclusion

After human review of the original submissions, reviewed transcripts, task statement, and official solution, none of the six historical targets can remain a confirmed model error. The suite is retired and its active hard-gate count changes from six to zero. The historical selectors, public summary, and v3.3 negative control remain for auditability.

This does not prove that the model was correct. It means the available evidence cannot reliably separate a grading-model error from a gold or scoring-policy problem. Unadjudicated disagreement must not drive skill tuning.

### Review of the six targets

| Question | Reviewed | Confirmed model errors | Disposition |
|---|---:|---:|---|
| Q6 | 2 | 0 | One answer used a technically valid method despite a questionable official score; the other was ordinary scoring leniency. Both leave the hard gate. |
| Q9 | 4 | 0 | Deductions for circularity, weak specificity, or unclear evidence were defensible; another case differed by only three points. All four leave the hard gate. |

The historical 0/6 negative control now means only that v3.3 did not satisfy the gold-derived gates defined at the time. It no longer demonstrates six real model defects. Candidate-v3.3 remains rejected because it failed its original pre-registered global safety gate; this adjudication does not retroactively accept it.

### Q8 input and scoring-contract review

Three additional Q8 disagreements were reviewed:

- One original response contains 2^n, but superscript loss changed the reviewed transcript to 2n. A model deduction based on the corrupted text is a transcription/input-pipeline error.
- The formula 0^(2^n), n >= 0 yields lengths 1, 2, 4, and so on, excluding epsilon, while the printed example and official solution include epsilon. This is an internal task/solution contract conflict.
- Because of that conflict, the other two cases cannot safely become grading-model targets. They should be used in a reviewed-transcript versus direct-multimodal comparison.

### Admission rule for future targets

Before a typical case becomes a hard regression target:

1. inspect the original response and rule out lost notation, layout, or image information;
2. verify that the question, rubric, official solution, and gold are mutually consistent;
3. exclude ordinary scoring leniency tolerated by the advisor and prioritize nontrivial, objective, reproducible failures;
4. require an explicit human decision that the case is a model error, then freeze it as a machine-checkable target.
