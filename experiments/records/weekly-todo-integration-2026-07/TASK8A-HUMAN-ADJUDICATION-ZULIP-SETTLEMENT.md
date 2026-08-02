# TASK8A Settlement: Human-Adjudicated Typical Cases

## 中文

### 做了什么

人工复核 Week 5 旧回归套件的六个 Q6/Q9 目标，以及三个 Q8 输入/评分合同案例。复核使用原始作答、人工复核 transcript、题目和官方解答，而不是只比较模型分数与 gold。

### 得到了什么新认知

- 六个旧目标中，确认的评分模型错误是 0 个。Q6 涉及有效技术方法与可疑 gold、普通评分宽松度；Q9 的循环论证/证据不具体判断有可辩护性，且包含导师允许的三分差。
- Q8 发现一个明确的转录错误：2^n 的上标丢失成 2n。
- Q8 还发现题面公式与题面示例/官方解答对 epsilon 的包含关系互相矛盾。

### 改善了什么

旧六例已从活动硬回归门禁中退役，避免未来 skill 为迎合不可靠 gold 而过拟合。代码现在区分 active 与 human-adjudicated retired 套件；退役套件仍保留历史产物，但不会要求未来版本必须通过。

### 有什么不足

本次只复核九个高优先级案例，没有证明其余 Week 5 分差或其他 week 的数据质量。当前活动硬回归目标是 0，需要从更多 instance 中重新收集真正经人工确认的非平凡错题。

### 下一步

先扩展 Week 3，构建 anonymized transcript、gold 和完整模型运行；再按“原图完整性 → 评分合同一致性 → 非平凡性 → 人工确认”的顺序筛选新错题。Week 2 作为第二批扩量，Q8 同时进入 reviewed-transcript 与 direct-multimodal 配对实验。

## English

### What was done

The six historical Q6/Q9 regression targets and three Q8 input/contract cases were human-reviewed against original submissions, reviewed transcripts, the task statement, and the official solution—not merely model scores versus gold.

### New knowledge

- Zero of the six historical targets are confirmed grading-model errors. Q6 involves a valid method with questionable gold and ordinary leniency; Q9 deductions for circularity or weak specificity are defensible, and one difference is within the advisor's three-point tolerance.
- Q8 contains a concrete transcription error: superscript loss changed 2^n into 2n.
- Q8 also contains an internal contradiction about whether epsilon belongs in the target output sequence.

### What improved

All six historical targets are retired from the active hard gate, preventing future skill versions from overfitting unreliable gold. The code now distinguishes active suites from human-adjudicated retired suites. Historical outputs remain auditable, but future versions need not pass them.

### Limitations

Only nine high-priority cases were reviewed. This does not validate every remaining Week 5 disagreement or any additional week. There are currently zero active hard-regression targets, so new human-confirmed nontrivial cases must be collected from more instances.

### Next

Expand Week 3 first, build anonymized transcripts, gold, and a complete model run, then screen errors in this order: original-input integrity, contract consistency, nontriviality, and explicit human confirmation. Use Week 2 as the second expansion batch, and run Q8 in a paired reviewed-transcript versus direct-multimodal experiment.
