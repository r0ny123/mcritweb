Title: List the unnamed family's samples in a cross compare's job row

## Summary
Fixes #NNN (the issue in `pr-text/issue-new-cross-job-unnamed-family.md`, once it is filed).

A cross compare's row in the jobs table left out every sample of family 0, the unnamed family, although the count above the list includes them. They are now listed under "Unnamed", as every other job description shows family 0.

## What changed
- `templates/table/job_row.html`, in the cross compare branch of `job_description`: the grouping skips a sample only when its `family_id` is None. It used to skip any falsy `family_id`, and family 0 is falsy.
- New `tests/testCrossJobUnnamedFamily.py`, rendering the macro directly, since the corpus's family 0 holds no samples:
  - samples of family 0 are listed under "Unnamed", before or after the named families, in job order;
  - a sample the backend no longer has is still left out;
  - a sample entry without a `family_id` is still left out, the case the check was written for.

## Why
Every mcrit storage keeps family 0 as the unnamed family, and a sample submitted without a family lands in it. `format_family_name` already renders family 0 as a link titled "Unnamed", and the other descriptions in the template pass family 0 to it. Only this grouping filtered it out first.

## Validation
- The two family-0 tests fail on master: the row lists only the named family's sample. The third passes on both.
- Live, against mcrit 1.9.0: I submitted an overlay variant of distlib's `t32.exe` without a family, so it landed in family 0 as sample 66, and cross-compared it with sample 16 (fastlist).
  - Master's jobs page shows that row as "CrossCompare | 2 samples" followed by `fastlist | 16` alone.
  - This branch shows `Unnamed | 66`, then `fastlist | 16`.
  - The sample and the jobs were deleted afterwards.
- On the same instance, whose family 0 holds no samples, these pages are byte-identical on master and here, whitespace included: `/data/jobs?active=combineMatchesToCross&plimit=250`, `/data/jobs?plimit=250`, `/`, and two cross compares' `/data/jobs/<id>`.
- Full suite: 988 passed with Chromium available. `ruff check .` is clean.

## Limitations
- mcrit's API cannot move a sample into family 0: `SampleResource.on_put` refuses a family name shorter than two characters. So the samples there are the ones submitted without a family.
- Family 0 takes its place among the families like any other: in the order the job first names one of its samples.

## Merge conflicts
- None. This merges cleanly with every open PR and every other branch of this set. That includes the #198 branch, which rewrites the grouping line two lines below this one.
