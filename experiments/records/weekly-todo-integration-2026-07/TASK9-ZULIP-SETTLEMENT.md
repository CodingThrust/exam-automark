# TASK9 Zulip 结算（待发送） / TASK9 Zulip Settlement (Prepared, Not Posted)

## 中文

TASK9 完成了一次预注册、单机制的 candidate-v3.3 开发集实验。目标是修复
`full_credit_rule` 与 evidence-family 加和冲突，以及“答案简短就自动降档”的
规则优先级错误。

运行结果：DeepSeek `deepseek-v4-pro`、text-only、同一 7 名开发集学生、
rubric-v2、1 次重复；7/7 schema validation 通过，0 个技术失败，118,551
tokens。Q9 MAE `9.0→7.0`，全体 question MAE
`2.557143→2.185714`，错误对 `33→31`，但严重错误 `16→17`。

预注册的五项门槛有四项通过，严重错误不得增加这一项失败，因此 candidate-v3.3
被拒绝，active skill 恢复并保持 v3.2。没有看结果后改 prompt 重跑，也没有读取
held-out/test。

错题生命周期已完整更新：31/31 当前错误完成逐案诊断；3 resolved、1 regression、
12 persistent improved、10 unchanged、8 worsened；另有 12 个完整可读典型案例和
31 例索引保存在 gitignored private Data 中。公开材料只包含聚合、哈希和方法限制。

最重要认知：Q9 有改善但 full-credit override 仍未稳定执行；4 个规则优先级错误
仍存在，其中 3 个严重且全部无 flag。下一步不应立即继续 prompt 追跑，而应先把
Q9 正向回归、Q6 防过度给分负向回归、Q8 多模态配对以及需导师裁决的合同问题变成
机器可检查约束。

状态：**内容已准备，尚未代替本人发送到 Zulip。**

## English

TASK9 completes one pre-registered, single-mechanism candidate-v3.3
development experiment targeting conflict between holistic
`full_credit_rule` behavior and evidence-family addition, plus automatic
brevity downgrades.

The run uses DeepSeek `deepseek-v4-pro`, text-only input, the same seven
development students, rubric-v2, and one repetition. All seven outputs pass
schema validation with zero technical failures and 118,551 tokens. Q9 MAE
improves from 9 to 7, all-pair question MAE from 2.557143 to 2.185714, and
error pairs from 33 to 31, but severe errors increase from 16 to 17.

Four of five pre-registered gates pass. The severe-error non-increase gate
fails, so candidate-v3.3 is rejected and the active skill is restored to v3.2.
There is no post-result prompt edit/rerun and no held-out/test access.

The error-book lifecycle is complete: all 31 current errors are diagnosed;
the delta contains three resolved, one regression, twelve persistent improved,
ten unchanged, and eight worsened cases. A private readable report contains 12
full typical cases plus the complete 31-case index. Public artifacts contain
only aggregates, hashes, and methodological limits.

The main finding is that Q9 improves but the full-credit override is not stable:
four rule-precedence errors remain, three are severe, and none is flagged. The
next step should convert Q9 positive regressions, Q6 anti-overcredit negative
regressions, Q8 multimodal pairs, and course-owner contract adjudications into
machine-checkable constraints before another optimization run.

Status: **prepared, not posted to Zulip on the user's behalf.**
