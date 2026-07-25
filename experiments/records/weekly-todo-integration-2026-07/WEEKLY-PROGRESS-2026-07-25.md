# Weekly TODO Progress

Date: 2026-07-25

This file is the live, public-safe status ledger for the current advisor TODOs.
It records deliverables and evidence links, not raw student data, private model
responses, credentials, or case-level Sxxx/Qx analysis.

## Status meanings

- `pending`: scoped but not started.
- `running`: active work with a named next checkpoint.
- `blocked`: cannot continue without a named external decision or dependency.
- `implemented_waiting_external_validation`: code is merged, but a required
  real external run has not returned.
- `completed`: deliverables, checks, project impact, and Zulip settlement are
  all ready.

## Current order

| Priority | Work item | Status | Current evidence | Next checkpoint | Zulip |
| ---: | --- | --- | --- | --- | --- |
| P0 | Advisor run-and-submit skill | `implemented_waiting_external_validation` | PR #29 merged as `0255f5a`; offline development/test dry-runs passed | Review the advisor's real Kimi/Claude result PRs | Pending real-run settlement |
| P1 | TODO1 failure retrospective, starting with SkillOpt R4 | `running` | R4 failure analysis and Zulip-ready negative-result settlement complete | Audit the remaining failed/negative experiments, then settle TODO1 as a whole | R4 settlement ready to post |
| P2 | quantum.harness / beginner-training explanation | `pending` | Existing methodology review | Explain reused ideas and present selectable project changes | Pending |
| P3 | sci-brain survey explanation | `pending` | Two committed survey PDFs and knowledge notes | Teach key concepts and present selectable project changes | Pending |
| P4 | GitHub Actions CI quality gate | `pending` | Local test commands exist; no required test check on `main` | Add core/Physics/skill/privacy checks | Pending |
| P5 | Objective error taxonomy and confidence calibration | `pending` | Existing metrics contain accuracy and some confidence fields | Freeze schema and calibration metrics before new runs | Pending |
| P6 | Automated Codex CLI versus Claude Code multimodal comparison | `pending` | Claude route is in the advisor skill; matched Codex multimodal evidence is missing | Freeze matched development config and dry-run | Pending |
| P7 | Mainline candidate-v3.2 defect audit | `pending` | DSAA3071 Week 5 development evidence | Produce private case-level and public aggregate diagnosis before editing the skill | Pending |
| P8 | Grading-decision skill refinement | `pending` | Advisor execution/submission skill is complete | Convert evidence-backed grading decisions into deterministic branches | Pending |
| P9 | Four-model result integration | `blocked` | DeepSeek/Codex committed; Kimi/Claude real results pending | Validate and integrate the advisor result PRs | Pending |
| P10 | Full live autoresearch loop | `pending` | Deterministic dry-run MVP only | Run one real dev-only candidate/metric/accept-reject loop | Pending |

## Required update points for every TODO

Update this ledger when:

1. work starts;
2. a material artifact or experiment checkpoint completes;
3. a blocker appears or clears;
4. the deliverables and checks pass;
5. the Zulip settlement is posted.

## Definition of done

A TODO is not `completed` until its record states:

- what was done;
- what changed or improved;
- how it helps `exam-automark`;
- failures and their causes;
- limitations and prohibited claims;
- evidence paths or PR links;
- the next decision;
- a Zulip-ready settlement.
