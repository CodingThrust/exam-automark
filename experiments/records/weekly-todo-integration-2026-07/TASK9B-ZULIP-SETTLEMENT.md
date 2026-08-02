# TASK9B Settlement: Machine-Checkable Typical-Error Regressions

## 2026-08-02 correction / 2026-08-02 更正

After human adjudication, zero of the six targets remained confirmed model
errors. This suite is now retired with zero active targets. Its historical
outputs remain auditable but no longer constrain future skill versions. Use
TASK8A-HUMAN-ADJUDICATION-ZULIP-SETTLEMENT.md as the current settlement.

人工查看原始作答和评分合同后，六例中没有一例能继续确认为模型错误。本套件
现已退役，活动目标为 0；历史输出保留审计，但不再约束未来 skill。当前结算
以 TASK8A-HUMAN-ADJUDICATION-ZULIP-SETTLEMENT.md 为准。

## 中文

### 做了什么

将 TASK9 的六个高价值开发集错误固化为可执行回归套件：

- Q6 两个严重的“无明确证据却给高分”负向案例；
- Q9 四个“整体证据充分但未执行满分规则”正向案例。

新增两个自动化命令：

- `build-error-regression-suite`：从完整私有错误册、完整诊断和公开选择策略构建私有套件及隐私安全汇总；
- `evaluate-error-regressions`：用候选版本的完整私有错误册逐例执行冻结门禁，并用退出码支持 CI/autoresearch。

套件加入评分 skill 错题册注册表。以后新增正式 skill 版本时，注册表要求提供每个已登记套件的公开通过结果；否则验证失败。

Q6 与 Q9 都使用“非严重且严格改善”的硬门禁。与人工 gold 精确一致只作为观察指标；只有经课程负责人裁决确认的标准案例，才应升级为精确一致硬门禁。

### 改善了什么

以前的典型错题主要用于人工阅读和版本对比，现在它们还能自动阻止已知错误复发。选择器带固定案例数量，源记录或标签漂移会使构建失败。v3.3 负对照结果为 `0/6` 通过，证明门禁能够识别全部目标错误，而不是形式检查。

### 有什么不足

- 没有运行新模型，所以尚无候选版本通过该套件。
- 六例只覆盖 Q6 与 Q9 的两个已确认机制，不代表全部 31 个现存错误。
- Q8 两个输入表示歧义仍需 reviewed-transcript 与 direct-multimodal 配对实验。
- 通过六例只是必要条件；全体 70 对的 MAE、严重错误和新 regression 仍必须单独通过。

### 下一步

不要只为通过六例而写过拟合规则。下一次 candidate 必须在完整开发集上运行，并同时满足回归套件与全局门禁。导师返回 Kimi/Claude 结果后，原 TASK10 仍用于匹配条件的跨模型整合。

## English

### What was done

Six high-value TASK9 development errors were frozen as an executable regression suite:

- two Q6 negative-credit cases involving severe unsupported evidence credit;
- four Q9 positive-credit cases where sufficient holistic evidence did not trigger the full-credit rule.

Two automation commands were added:

- `build-error-regression-suite` builds a private suite and privacy-safe aggregate from the complete private error book, diagnoses, and public selection policy;
- `evaluate-error-regressions` applies frozen case gates to a candidate's complete private error book and exposes a CI/autoresearch-compatible exit code.

The suite is registered in the grading-skill error-book registry. Every future formal skill entry must supply a passing public evaluation for each registered suite.

Both Q6 and Q9 use a non-severe-and-strictly-improved hard gate. Exact gold agreement remains a reported observation rather than a universal hard requirement; it can be promoted only after course-owner adjudication.

### What improved

Typical cases were previously human-readable evidence and version-comparison inputs. They can now automatically block recurrence of known errors. Fixed expected counts detect selector drift. The v3.3 negative control passes `0/6`, demonstrating that the gate rejects all known target failures.

### Limitations

- No new model was run, so no candidate has passed the suite.
- Six cases cover only two confirmed Q6/Q9 mechanisms, not all 31 current discrepancies.
- Two Q8 representation ambiguities still require paired reviewed-transcript and direct-multimodal experiments.
- Passing six cases is necessary, not sufficient; full-set MAE, severe errors, and new regressions remain mandatory.

### Next

The next candidate must run the complete development condition and pass both targeted regressions and global gates. The original TASK10 remains reserved for matched Kimi/Claude result integration after the advisor returns outputs.
