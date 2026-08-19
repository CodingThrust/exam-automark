# V5.3-r2 Human Calibration Worksheet / 人工协作校准表

## Purpose / 目的

This is a **course-owner decision worksheet**, not a model result, gold table,
or authorization to grade students. The owner decides the intended teaching and
partial-credit policy; the system turns those decisions into a separately
versioned executable rubric.

这是给课程负责人使用的**评分尺度决策表**，不是模型结果、gold 表，也不
授权任何学生评分。课程负责人决定教学与部分分尺度；系统只把该决定转成单独
版本化、可执行的 rubric。

The full machine-readable proposal is
`human_calibration_contract.json`. It contains no student identity, answer,
transcript, gold row, or raw model output.

## How to review / 如何审阅

1. Confirm a proposal with `confirm`, or write the replacement rule and point
   allocation.
2. Resolve every high-impact decision first; then confirm or amend each of the
   ten leaf rows.
3. If a rule changes, create a new V5.3 revision. Do not edit the already
   recorded V5.3-r2 candidate or its historical metrics.
4. Do not create gold, packets, or model runs during this review.

可直接按以下形式回复：`D01 confirm`、`Q2a: local sign error deduct 1;
retain carry-forward`。我会把你的决定转成下一版规则并进行结构校验。

## High-impact decisions / 高影响决策

| ID | Current proposal / 当前建议 | Owner decision / 你的决定 |
| --- | --- | --- |
| D01 Q2a local sign | A single local cofactor-sign error loses only the 1-point sign criterion; a direct final carry-forward remains creditable. / 单个局部余子式符号错误只扣 1 分，直接连带的最终结果仍保留对应分。 | Pending / 待定 |
| D02 Q2b equivalence | A factored, expanded, reordered, or otherwise algebraically equivalent symbolic result earns the equivalent-form credit. / 代数等价的因式分解、展开或重排形式均接受。 | Pending / 待定 |
| D03 Q3 complete derivation | Any valid complete route to the correct exceptional values and final condition earns 25. / 任何有效完整路线得到正确特殊值与结论时给 25 分。 | Pending / 待定 |
| D04 Q4 factor | An otherwise correct tetrahedron solution using a factor other than division by 6 loses the 4-point conversion criterion and keeps direct carry-forward final credit. / 其余正确但未除以 6 时扣转换因子 4 分，保留直接连带的最终结论分。 | Pending / 待定 |
| D05 answer-only caps | Correct answer but no required working earns at most 3 for Q2a, Q2b, Q3, and Q4. / 仅答案、无要求过程时，这四题最高各得 3 分。 | Pending / 待定 |
| D06 Q3 bonus | The 10-point bonus is independent and all-or-nothing; two methods must be genuinely distinct. / 10 分 bonus 独立且全有全无；两种方法必须实质不同。 | Pending / 待定 |

## Leaf review matrix / 最小计分叶子审阅表

| Leaf | Max | Current full-credit rule / 当前满分规则 | Confirm or amend / 确认或修改 |
| --- | ---: | --- | --- |
| Q1a | 5 | Unambiguous `T` selection only; no explanation or working required. / 只需明确选 `T`，不要求解释或过程。 | Pending |
| Q1b | 5 | Unambiguous `F` selection only; no explanation or working required. / 只需明确选 `F`，不要求解释或过程。 | Pending |
| Q1c | 5 | Unambiguous `T` selection only; no explanation or working required. / 只需明确选 `T`，不要求解释或过程。 | Pending |
| Q1d | 5 | Unambiguous `F` selection only; no explanation or working required. / 只需明确选 `F`，不要求解释或过程。 | Pending |
| Q1e | 5 | Unambiguous `F` selection only; no explanation or working required. / 只需明确选 `F`，不要求解释或过程。 | Pending |
| Q2a | 15 | Method 3 + structure 3 + sign 1 + arithmetic 2 + simplification 3 + final/carry-forward 3. / 方法 3 + 结构 3 + 符号 1 + 算术 2 + 化简 3 + 结论/连带 3。 | Pending |
| Q2b | 15 | Method 3 + structure 3 + term/sign 1 + symbolic combination 2 + equivalent form 3 + final/carry-forward 3. / 方法 3 + 结构 3 + 项/符号 1 + 符号合并 2 + 等价形式 3 + 结论/连带 3。 | Pending |
| Q3 | 25 | Principle 4 + setup 4 + derivation 6 + parameter algebra 2 + exceptional values/carry-forward 6 + final condition/carry-forward 3. / 原理 4 + 建立 4 + 推导 6 + 参数代数 2 + 特殊值/连带 6 + 最终条件/连带 3。 | Pending |
| Q3 bonus | 10 | Correct conclusion plus two genuinely distinct correct methods; independent, all-or-nothing. / 正确结论加两种实质不同的正确方法；独立、全有全无。 | Pending |
| Q4 | 20 | Vectors 4 + setup 4 + evaluation 3 + magnitude 1 + divide by 6 factor 4 + arithmetic 1 + final/carry-forward 3. / 向量 4 + 建立 4 + 计算 3 + 绝对值 1 + 除以 6 因子 4 + 算术 1 + 结论/连带 3。 | Pending |

## Future annotation rule / 后续卷面批注规则

- Red deduction mark / 红色扣分标记：circle the **first visible** incorrect
  or missing evidence for one declared criterion, with a short label such as
  `sign error (-1)`. Do not circle a later consequence as a separate error.
- Green acknowledgement / 绿色肯定标记：at most one mark for a meaningful
  correct method, valid equivalent form, or complete reasoning step; do not
  decorate every correct line.
- Yellow review mark / 黄色复核标记：use when the relevant symbol, page order,
  or location is unreadable or uncertain. It creates a TA review item rather
  than an invented deduction.
- The score, deduction trace, CSV review reason, and visual label must all
  reference the same criterion ID.

## Freeze gate / 冻结门槛

The candidate remains `prepared_pending_course_owner_decisions` until all ten
leaf rows and D01–D06 have a recorded owner decision. Only then may a new
V5.3 revision be created, followed by private development gold, one matched
G1 packet, and a separately authorized development run. Heldout remains
unseen throughout calibration.

在 10 个叶子项和 D01–D06 都有课程负责人决定前，本候选始终为待定状态。
之后才能创建新的 V5.3 版本、私有开发集 gold、同一份 G1 packet，并在单独
授权后进行开发集运行。校准期间始终不接触留出集。
