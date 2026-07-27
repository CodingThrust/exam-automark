# Candidate-v3.3 Run Protocol / Candidate-v3.3 运行协议

## 中文

本协议只运行预注册的 candidate-v3.3 开发集文本评分实验。API key 不写入
仓库或日志。运行前必须先提交 skill、prompt、快照、packet provenance 与门槛，
然后把该提交的短 SHA 记录为 `run_commit`。

固定输入：

- Packet：`C33-dev-reviewed-r1`
- Skill：`skill_candidate_v3_3`
- Prompt：`grade_candidate_v3_3_strict_schema`
- Rubric：`DSAA3071-week5-v2`
- Students：`S017`, `S021`, `S002`, `S015`, `S020`, `S016`, `S022`
- Split：`development`
- Provider/model：`deepseek` / `deepseek-v4-pro`
- Input mode：`text-only`
- Repetition：1

PowerShell 运行命令：

```powershell
$runCommit = git rev-parse --short HEAD

python -m benchmark.core.cli run-model-packet `
  --provider deepseek `
  --model deepseek-v4-pro `
  --input-mode text-only `
  --packet Data\DSAA3071\week5-benchmark-redaction-v3\text_grading_packets\DSAA3071-week5-C33-v2-reviewed-dev\C33-dev-reviewed-r1 `
  --output Data\DSAA3071\week5-benchmark-redaction-v3\runs\deepseek-C33-q9-precedence-text-dev-reviewed-r1 `
  --max-retries 4 `
  --run-commit $runCommit
```

运行后必须生成完整错题册、逐案诊断、可读典型案例、confidence/taxonomy
审计，以及 v3.2→v3.3 的 resolved/persistent/regression 对比，再按
`acceptance-gate.json` 做一次性接受/拒绝判断。

## English

This protocol runs only the pre-registered candidate-v3.3 development
text-grading experiment. The API key must not enter the repository or logs.
Commit the skill, prompt, snapshot, packet provenance, and gate before the run,
then record that commit's short SHA as `run_commit`.

The frozen inputs and command are listed above. After the run, produce the
complete error book, complete case diagnoses, readable typical cases,
confidence/taxonomy audit, and v3.2→v3.3
resolved/persistent/regression comparison. Make exactly one accept/reject
decision against `acceptance-gate.json`.
