# DSAA3071 Next-Instance Selection / DSAA3071 下一批数据选择

## 中文

### 决定

下一批先做 Week 3，Week 2 作为第二批扩量。该决定来自对 Week 2、3、4、6 原始合并 PDF 与官方解答的只读抽样，不代表已经运行模型或查看 held-out 结果。

| 候选 | 学生卷页数 | 估计完整作答数 | 主要题型 | 判断 |
|---|---:|---:|---|---|
| Week 2 | 92 | 约 30 | 正则语言、pumping lemma、GNFA、闭包证明 | 样本最多，适合第二批扩量；证明题较多，首次准备成本较高。 |
| Week 3 | 46 | 约 15 | CFG、歧义推导、PDA 构造与轨迹、非确定性 | **第一推荐**：规模较小、官方解答具体、技术条件明确，并包含图与栈记号。 |
| Week 4 | 90 | 约 29 | CFL pumping、TM 构造、可判定性 | 很有价值，但长证明和实现层描述带来更多分档主观性。 |
| Week 6 | 86 | 约 28 | 对角化、不可判定性、语言层级 | 概念重要，但证明开放度最高，gold 口径更需人工裁决。 |

### 为什么先做 Week 3

1. **快速形成第二个 instance。** 46 页约为其他候选的一半，可以先验证匿名化、转录、gold 提取、双输入评分和错题筛选整条流水线。
2. **更容易找到非主观错误。** CFG 是否生成目标结构、推导是否真的不同、PDA 的栈动作与接受条件、轨迹中的状态和栈内容，都有可核对的技术条件。
3. **适合多模态对照。** 状态图、箭头、epsilon 转移、上下标和栈表格都可能在纯文字转录中丢失，能直接检验输入模式差异。
4. **官方解答较具体。** 十道题均有答案或步骤，比只给最终分数更容易先检查评分合同。

### 预处理顺序

1. 删除或遮盖姓名、学号和成绩总表，生成新的匿名映射；映射只留在私有 Data。
2. 在模型运行前冻结 development/holdout 划分；holdout 不用于改 skill。
3. 从红色人工批注提取逐题 gold，并人工抽查官方解答与 gold 是否可复现。
4. 对同一批 development 作答生成 reviewed transcript 和原图多模态两种输入。
5. 用当前最新模型完整评分，不先挑“看起来会错”的题。
6. 只把通过“原图完整性、合同一致性、非平凡性、人工确认”四道门的案例加入新错题集。

## English

### Decision

Use Week 3 as the next instance and Week 2 as the second expansion batch. This decision follows read-only sampling of the combined submissions and official solutions for Weeks 2, 3, 4, and 6. No new model or held-out result was inspected.

| Candidate | Submission pages | Estimated complete submissions | Main content | Assessment |
|---|---:|---:|---|---|
| Week 2 | 92 | about 30 | regular languages, pumping lemma, GNFA, closure proofs | Largest sample and best second expansion batch; proof-heavy preparation is more expensive. |
| Week 3 | 46 | about 15 | CFGs, ambiguity derivations, PDA design and traces, nondeterminism | **First choice**: smaller, concrete official solutions, objective technical conditions, and visual stack/state notation. |
| Week 4 | 90 | about 29 | CFL pumping, TM construction, decidability | Valuable, but long proofs and implementation-level descriptions introduce more score-band subjectivity. |
| Week 6 | 86 | about 28 | diagonalization, undecidability, language hierarchy | Important concepts, but the most open-ended proofs and greatest need for gold-policy adjudication. |

### Why Week 3 first

1. Its 46 pages make it the fastest way to validate the complete second-instance pipeline.
2. CFG generation, distinct derivations, stack actions, acceptance conditions, and trace states provide objective technical checks.
3. State diagrams, arrows, epsilon transitions, superscripts, and stack tables create meaningful transcript-versus-multimodal cases.
4. Every question has a concrete official answer or procedure, making scoring-contract validation easier.

### Preparation order

1. Remove names, identifiers, and grade sheets; keep the anonymous mapping only in private Data.
2. Freeze development and holdout before model runs; never tune on holdout.
3. Extract question-level gold from human marks and audit whether the official solution reproduces it.
4. Build matched reviewed-transcript and direct-multimodal inputs for the development set.
5. Run the latest model on the complete set rather than selecting likely failures in advance.
6. Admit a case to the new error book only after input-integrity, contract-consistency, nontriviality, and explicit human-confirmation gates.
