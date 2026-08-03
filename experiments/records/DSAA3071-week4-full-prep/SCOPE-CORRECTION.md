# Week 4 Scope Correction / Week 4 范围纠正

## Decision / 决定

Week 4 is a **full Q1--Q10, 130-point** benchmark. Only Week 3 has the
missing-page limitation and therefore uses the Q1--Q4/Q9/Q10 partial scope.

Week 4 的正确范围是 **Q1--Q10、130 分**。只有 Week 3 存在缺页，因此只有
Week 3 使用 Q1--Q4/Q9/Q10 的部分范围。

## Evidence / 依据

- The approved W4 anonymous artifact contains 22 students x `p01,p02,p03` =
  66 pages; every page passed final anonymization review.
- The former W4 partial preparation used only `p01,p03` (44 pages) because the
  Week 3 limitation was incorrectly applied to Week 4.
- Its private 132-row partial gold table was entirely blank, and no W4 model
  output exists. No human score or experimental result is being discarded.

## Replacement / 替代版本

This directory and
[`DSAA3071_week4_full_q1_q10.json`](../../course_specs/DSAA3071_week4_full_q1_q10.json)
are the authoritative W4 preparation. They use the user-confirmed student-page
map `p01 -> Q1-Q4`, `p02 -> Q5-Q8`, `p03 -> Q9-Q10` and a fresh private
`v2-full-q1-q10` benchmark root.

The former `DSAA3071-week4-prep` artifacts remain preserved for audit only and
must not be run or compared. See its
[`SCOPE-SUPERSEDED.md`](../DSAA3071-week4-prep/SCOPE-SUPERSEDED.md).
