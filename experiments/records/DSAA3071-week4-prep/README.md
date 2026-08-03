# DSAA3071 Week 4 Partial Benchmark Preparation

> **Superseded / 已废弃：** Only Week 3 has the missing-page limitation. This
> unrun W4 partial scope has been replaced by the full Q1--Q10 preparation at
> [`DSAA3071-week4-full-prep`](../DSAA3071-week4-full-prep/). Do not run it.

Status: preparation only. No model call, prediction, gold score, or accuracy
claim has been made from this record.

## English

This record prepares a **60-point partial** DSAA3071 Week 4 benchmark. Its
frozen question scope is Q1-Q4, Q9, and Q10. Q5-Q8 are excluded from gold,
transcripts, packets, predictions, and metrics.

The course owner declared the student-packet mapping as follows:

| Anonymous input page | Questions in scope |
| --- | --- |
| `p01` | Q1-Q4 |
| `p03` | Q9-Q10 |

This is a user-declared mapping for the anonymized student-submission packets;
it is not inferred from the pagination of the official question-plus-solution
reference PDF. The distinction prevents an accidental mismatch between the
reference document and the input pages used in a model packet.

Tracked, privacy-safe preparation artifacts:

- [Course specification](../../course_specs/DSAA3071_week4_partial_q1_q4_q9_q10.json)
- [Bilingual preparation contract](PREPARATION-CONTRACT.md)
- [Official-solution-derived rubric v0](rubric_v0.json)
- [Frozen anonymous split](split.json) — 7 development / 15 held-out students
- [All anonymous IDs](students-all.txt), [development IDs](students-development.txt), and [held-out IDs](students-heldout.txt)
- [Standard direct-grading prompt](prompts/grade_standard_v1_strict_schema.txt) and [standard transcription prompt](prompts/transcribe_standard_v1.txt)
- [Machine-readable pre-run status](PRE-RUN-STATUS.json)
- [Gold-reviewer source-snapshot binding](gold-reviewer-binding.json)
- [Bilingual future run matrix and activation protocol](RUN-MATRIX-AND-PROTOCOL.md)
- [Deliberately blocked workflow configuration](advisor-workflow-development.blocked.json)
- [Course-generic aggregate metrics guide](../../../docs/course-generic-metrics.md) —
  a model-free comparison command for completed runs; it does not remove the
  gold, lineage, or explicit-approval gates.
- [Local visual gold reviewer](../../../scripts/review_question_gold.py) — when the gold-review gate begins, Codex starts this local page and the reviewer only inspects images and enters scores.

The final anonymization approval is one completed gate, but it does not make a
model run ready. Before any model call, the team must freeze an anonymous
development/held-out split, create a manually reviewed per-question gold table,
prepare fresh automatic transcripts, create matched direct-multimodal and
transcript-first packets, audit those packets, and approve run readiness. The
primary transcript-first route uses each engine's own automatic transcript
unchanged; any human transcription-quality audit is a separate, post-run
artifact.

The course-generic aggregate metrics command is implemented and model-free. It
is used only after authorized completed grading runs and the relevant
question-level gold exist; it cannot authorize a model run or bypass lineage
and approval gates.

The split is now frozen and a **private, blank 132-row gold template** has been
created locally for the 22 anonymous students × 6 in-scope questions. It has no
scores yet, so the benchmark remains intentionally blocked until human gold
review and the remaining packet gates are complete.

The local gold reviewer also requires the tracked source-snapshot binding. It
pins the unchanged partial course specification to the exact approved private
snapshot; an unrelated snapshot or a modified course file is rejected.

No raw scan, student answer, identity map, gold row, or model output is tracked
in this directory.

## 中文

本目录只记录 DSAA3071 Week 4 的**运行前准备**，并不代表已经运行模型、
得到预测、建立 gold 分数，或得到任何准确率结论。

本次冻结的是一个 **60 分的部分 benchmark**：只包含 Q1-Q4、Q9、Q10；
Q5-Q8 不得进入 gold、转录文本、prompt packet、模型预测或指标计算。

课程负责人已明确说明匿名学生答卷包中的页面对应关系：

| 匿名输入页 | 本次题目 |
| --- | --- |
| `p01` | Q1-Q4 |
| `p03` | Q9-Q10 |

该关系是对学生答卷包的人工声明，**不能**根据官方题目/答案 PDF 的页码去推断。
这样可以避免参考答案文档与实际模型输入页发生错配。

当前已完成的匿名化终审只是一个前置门槛。模型运行前仍必须完成：冻结匿名
development/held-out 划分、人工填写并复核逐题 gold、生成并结构校验自动转录、从同一批
匿名学生构造直接多模态与先转录后评分两种匹配 packet、进行 packet audit，并
获得独立的 run-readiness 批准。

主先转录后评分路线会使用每个 engine 自己生成且**未改写**的自动转录；如需人工检查
转录质量，会作为运行后的独立审计，而不替换主路线文本。

课程通用的汇总指标命令已经实现，且**不会调用模型**。它只会在获得授权的评分运行完成、
并具备相关逐题 gold 后用于比较；它不能授权模型运行，也不能跳过 lineage 或显式批准门槛。

现在已经冻结了 anonymous split，并在本机私有目录建立了一个**空白的 132 行
gold 模板**（22 名匿名学生 × 6 道题）。其中尚未填写任何分数，因此 benchmark
仍会被有意阻断；必须完成 gold 人工复核以及其余 packet 门槛后才能运行模型。

本地 gold reviewer 还会要求读取 tracked 的 source-snapshot binding。该文件把未改动
的部分课程规范精确绑定到已批准的私有 snapshot；任何无关 snapshot 或被改动的课程文件
都会被拒绝。

[Gold reviewer binding](gold-reviewer-binding.json) 会将未改动的课程规范精确
绑定到唯一一份私有 scope 图片快照；本地 gold 页面只有在该绑定的哈希与 assessment
ID 都匹配时才会启动，它不是模型运行授权。

本目录不提交原始扫描件、学生作答、身份映射、gold 行或模型输出。
