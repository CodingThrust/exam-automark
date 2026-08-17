# Rubric execution contract v1

`execution_contract_v1.template.json` is a course-generic starting structure
for a detailed rubric. Copy it into a new course-specific, versioned rubric and
replace every placeholder before packet creation.

The contract separates two levels:

- `global_scoring_rules` are invariant across questions: score only declared
  criteria, accept valid alternative methods, make deductions local to the
  first material error, and ignore unrelated extra content unless it directly
  contradicts a declared criterion.
- Every declared scoring leaf separately specifies its maximum, exact
  point-bearing criteria, award and withhold conditions, and whether
  simplification, explanation, or visible working is required.

The validator rejects incomplete point totals, missing answer-form rules, and
discretionary terms such as “normally” or “as appropriate”. This does not make
a rubric correct by itself: the course owner must still approve the subject
matter and partial-credit policy before the rubric is frozen.

Every criterion is a complete award-or-withhold unit. Its `points` is the exact
amount withheld when that criterion is not met, so authors should split a
criterion into smaller point-bearing units wherever a smaller deduction is
legitimate. A non-full `deduction_trace` therefore cites each affected
criterion at most once and deducts exactly that criterion's points.
