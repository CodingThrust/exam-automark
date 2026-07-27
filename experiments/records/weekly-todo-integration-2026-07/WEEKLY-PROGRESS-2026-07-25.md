# Weekly TASK Progress and Advisor TODO Mapping

Started: 2026-07-25

Last updated: 2026-07-27

This file is the live, public-safe execution ledger for the project. `TODO<N>`
refers only to the advisor's numbering. `TASK<N>` refers to our implementation
order, which may combine, split, or reorder advisor TODOs. It records
deliverables and evidence links, not raw student data, private model responses,
credentials, or case-level Sxxx/Qx analysis.

## Status meanings

- `pending`: scoped but not started.
- `running`: active work with a named next checkpoint.
- `blocked`: cannot continue without a named external decision or dependency.
- `implemented_waiting_external_validation`: code is merged, but a required
  real external run has not returned.
- `completed`: deliverables, checks, project impact, and Zulip settlement are
  all ready.

## Current TASK order

| TASK | Work item | Advisor mapping | Status | Current evidence | Next checkpoint | Zulip |
| ---: | --- | --- | --- | --- | --- | --- |
| TASK1 | Advisor run-and-submit skill | This-week TODO6; prerequisite for TODO2 | `implemented_waiting_external_validation` | PR #29 merged as `0255f5a`; offline development/test dry-runs passed | Review the advisor's real Kimi/Claude result PRs | Pending real-run settlement |
| TASK2 | Meaningful negative-result retrospective | This-week TODO1 | `completed` | SkillOpt R4 plus DSAA3071 candidate-v3/v3.1/v3.2 diagnosis, machine-readable metrics, scope exclusions, and bilingual reports | Carry the diagnosed Q6/Q8/Q9 defects into advisor TODO3; do not reopen operational errors as experiment findings | TODO1 settlement ready to post |
| TASK3 | quantum.harness / beginner-training explanation | Previous-week carry-over | `completed` | PR #31 and oral-briefing PR #32 merged; source commit pinned; 27 relevant tests passed | Post the prepared settlement to Zulip; B/C remain assigned to TASK5/TASK7 rather than being claimed as TASK3 implementation | Bilingual settlement ready, not posted |
| TASK4 | sci-brain survey explanation | Previous-week carry-over | `running` | Teaching/options PR #33 merged; draft PR #34 adds an explicit legacy gap, future provenance requirements, citation-scope audit, 217 passing core tests, and a bilingual settlement draft | Review and merge PR #34, then post the prepared settlement to Zulip | Bilingual settlement draft links PR #34; not posted |
| TASK5 | GitHub Actions CI quality gate | Project infrastructure | `pending` | User accepted option B; local negative controls and research-record health checks exist, but no required test check runs on `main` | Add required core/Physics/skill/privacy/research-record negative-control checks | Pending |
| TASK6 | Objective error taxonomy and confidence calibration | This-week TODO4 + TODO5 | `pending` | Existing metrics contain accuracy and some confidence fields | Freeze schema and calibration metrics before new runs | Pending |
| TASK7 | Automated Codex CLI versus Claude Code multimodal comparison | This-week TODO2 | `pending` | User accepted option C; Claude route is in the advisor skill, but matched Codex multimodal evidence and a unified lineage contract are missing | Freeze the minimum run-to-report lineage schema before the matched development config and dry-run | Pending |
| TASK8 | Mainline candidate-v3.2 defect audit | This-week TODO3 | `pending` | DSAA3071 Week 5 development evidence | Produce private case-level and public aggregate diagnosis before editing the skill | Pending |
| TASK9 | Grading-decision skill refinement | This-week TODO6 | `pending` | Advisor execution/submission skill is complete | Convert evidence-backed grading decisions into deterministic branches | Pending |
| TASK10 | Four-model result integration | This-week TODO2 follow-up | `blocked` | DeepSeek/Codex committed; Kimi/Claude real results pending | Validate and integrate the advisor result PRs | Pending |
| TASK11 | Full live autoresearch loop | Previous-week TODO8 carry-over | `pending` | Deterministic dry-run MVP only | Run one real dev-only candidate/metric/accept-reject loop | Pending |

## Required update points for every TASK

Update this ledger when:

1. work starts;
2. a material artifact or experiment checkpoint completes;
3. a blocker appears or clears;
4. the deliverables and checks pass;
5. the Zulip settlement is posted.

## TASK definition of done

A TASK is not `completed` until its record states:

- what was done;
- what changed or improved;
- how it helps `exam-automark`;
- failures and their causes;
- limitations and prohibited claims;
- evidence paths or PR links;
- the next decision;
- a Zulip-ready settlement.

All failure analyses and meaningful negative-result reports must contain a
complete Chinese version and a complete English version. A translated title or
short abstract alone does not satisfy this reporting requirement.
