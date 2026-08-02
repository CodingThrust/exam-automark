# Blind anonymization workflow

This workflow prepares private assessment scans for direct multimodal grading
without allowing an existing human score, tick/cross, total, or comment to
leak into a model input. It does not make an assessment model-ready by itself.

## Why the extra workflow exists

The normal `anonymization_review.csv` is a review record for already-rendered
images. Editing its `grading_mark_mask_rectangles` column does not alter the
PNG or PDF. Never use that CSV to propose a new redaction rectangle.

Instead, use this sequence:

1. Create an explicit private page layout and render a base, identity-masked
   output. Keep every result under ignored `Data/`.
2. Run `propose-grading-masks`. It produces a candidate manifest, a
   candidate-decision CSV, and a mandatory page-sweep CSV. The detector is a
   high-recall red-ink proposal only; it cannot reliably find grayscale marks.
3. A private reviewer resolves every candidate as `accepted`, `rejected`, or
   `adjusted`, and completes a full-page sweep for every page. A reviewer can
   add a normalized rectangle during that sweep for a grayscale or missed mark.
4. Run `compile-approved-masks` to create a new versioned layout. It never
   edits the base layout.
5. Re-run `prepare` with the compiled layout and a new versioned output root.
   The renderer records a hash of the layout, identity masks, scale, and every
   generated image/PDF.
6. Conduct the final three per-page approvals: privacy, blindness to existing
   grading evidence, and in-scope answer-content preservation. Then run
   `validate-review` with the exact base layout, candidate manifest, decisions,
   and page sweeps.

Every layout or mask change requires a fresh render and fresh final approvals.
The final approval CSV is cryptographically bound to that render specification
and its image/PDF manifest; a CSV approved for an earlier render cannot be
reused.

## Commands

All arguments below are private local paths. Do not place raw scans, page
layouts, candidate manifests, decisions, sweeps, outputs, or review CSVs in
Git.

```powershell
python scripts/prepare_anonymized_assessment.py propose-grading-masks `
  --source-pdf <private-source.pdf> `
  --layout <private-base-layout.json> `
  --output-root <private-mask-review-dir> `
  --identity-redaction-rect LEFT,TOP,RIGHT,BOTTOM

# Complete candidate-decisions.csv and page-sweeps.csv privately first.
python scripts/prepare_anonymized_assessment.py compile-approved-masks `
  --base-layout <private-base-layout.json> `
  --candidate-manifest <private-mask-review-dir/candidate-manifest.json> `
  --candidate-decisions <private-mask-review-dir/candidate-decisions.csv> `
  --page-sweeps <private-mask-review-dir/page-sweeps.csv> `
  --output-layout <private-new-version-layout.json>

python scripts/prepare_anonymized_assessment.py prepare `
  --source-pdf <private-source.pdf> `
  --layout <private-new-version-layout.json> `
  --output-root <private-new-version-output-dir> `
  --identity-redaction-rect LEFT,TOP,RIGHT,BOTTOM

# Complete the three final approvals in the new anonymization_review.csv.
python scripts/prepare_anonymized_assessment.py validate-review `
  --layout <private-new-version-layout.json> `
  --prep-metadata <private-new-version-output-dir/manifest/prep-metadata.json> `
  --review <private-new-version-output-dir/manifest/anonymization_review.csv> `
  --base-layout <private-base-layout.json> `
  --candidate-manifest <private-mask-review-dir/candidate-manifest.json> `
  --candidate-decisions <private-mask-review-dir/candidate-decisions.csv> `
  --page-sweeps <private-mask-review-dir/page-sweeps.csv> `
  --output <private-new-version-output-dir/manifest/readiness.json>
```

`validate-review` returns a nonzero exit code while any safety gate is pending.
That is expected readiness behavior, not a model or experiment failure.

## Local reviewer page

To avoid hand-editing normalized rectangle coordinates, run the local reviewer
against the existing identity-masked artifact. It binds to `127.0.0.1` only,
never uploads an image, and saves decisions into the same private CSVs.

```powershell
# Standard per-week private layout:
python scripts/review_grading_masks.py --week 2 --version v1

# Or supply every private path explicitly for a custom layout.
python scripts/review_grading_masks.py `
  --layout <private-base-layout.json> `
  --artifact-root <private-identity-masked-artifact-dir> `
  --prep-metadata <private-identity-masked-artifact-dir/manifest/prep-metadata.json> `
  --candidate-manifest <private-mask-review-dir/candidate-manifest.json> `
  --candidate-decisions <private-mask-review-dir/candidate-decisions.csv> `
  --page-sweeps <private-mask-review-dir/page-sweeps.csv>
```

The command prints a single-session `127.0.0.1` URL with a random access token;
open that exact URL locally. The reviewer refuses a mismatched layout, candidate
pack, or prepared artifact. It shows only already identity-masked page PNGs;
it never uploads images and cannot browse other files in the artifact directory.
Orange boxes are detector proposals; drag to add a manual rectangle, then
complete the page sweep. Saving a candidate or sweep is not final approval and
does not alter the model-facing artifact until the compile-and-rerender steps
are run.
