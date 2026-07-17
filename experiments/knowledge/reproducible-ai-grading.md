# Reproducible AI Grading Framework

This note records the reusable experiment structure for AI grading studies. It
is adapted from the reproducibility pattern observed in `quantum.harness`: keep
one structured source of truth, run cheap gates before expensive model calls,
and generate reports from recorded facts instead of from chat history.

## Source-Of-Truth Layers

1. `experiments/*`: public, privacy-safe experiment design records. These files
   define course specs, prompt templates, frozen skill versions, packet plans,
   readiness reports, metrics, and final notes.
2. `Data/*`: private and Git-ignored data. This may contain anonymous PDFs,
   prompt packets, model outputs, raw responses, and gold scores.
3. `run-metadata.json`: one record per model-packet run. This is the audit
   anchor for provider/model, command, prompt hash, packet hash, data snapshot,
   git commit, split, input mode, and generation parameters.
4. Typst/PDF reports: derived summaries. Reports should cite the structured
   records they summarize and should not introduce new untracked facts.

## Readiness Levels

`packet` ready means prompt packets, manifests, hashes, rubric consistency, and
baseline/candidate comparability have passed local checks. It does not mean a
model has been called.

`model-run` ready additionally requires the researcher to approve the provider,
model name, endpoint, API key source, command line, data privacy status, and
expected cost. This approval must happen before sending any student content to
an external model API.

`metrics` ready requires completed model outputs and filled gold scores for the
same anonymous student IDs and question IDs. Accuracy claims must not be made
before this level.

## Required Run Metadata

Every non-dry or dry model-packet run must produce `run-metadata.json` with:

- `schema_version` and `record_type`
- provider, model, endpoint, response format, temperature, top-p, max tokens,
  retry policy, and input mode
- exact command line and API key source, without storing the secret itself
- course ID, assessment ID, condition, task, split, packet ID, prompt template
  ID, and skill version ID
- git commit used for the run
- packet, prompt, rubric, text-source, and data-snapshot hashes
- anonymous student IDs included in the packet
- cost estimate fields, even when the estimate is unknown

These fields are validated in code so a run cannot silently omit a
reproducibility anchor.

## Negative Controls

Readiness checks must fail for known-bad cases, including:

- baseline and candidate grade prompts are identical
- grade packets use different rubric hashes
- manifest metadata differs from the experiment plan
- packet hashes no longer match local packet contents
- `Data/` is tracked by Git or not ignored

These controls prove that readiness is not a decorative checklist. It is a gate
that can actually stop unsafe or non-comparable experiments.

## Privacy Boundary

GitHub records may include aggregate counts, hashes, anonymous IDs, commands,
prompt text, rubrics, and metrics. They must not include raw student names,
student numbers, identity maps, or unredacted submissions.

Private HKUST-GZ GitLab data may store the anonymous data snapshot and outputs
needed for supervisor reproduction. Identity maps should remain outside prompt
packets and outside public records.
