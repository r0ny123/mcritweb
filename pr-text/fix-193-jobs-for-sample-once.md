Title: Ask getJobsForSample once per row instead of four times

## Summary
Fixes #193.

## What changed
Both `sample_row.html`'s row macro and `single_sample.html` called `JobCollection.getJobsForSample` four times per row:
- twice for the job badge (`matching_only=True`);
- twice for the "Last 1:N Job" link (`method="getMatchesForSample", finished_only=True`).

In each pair, the same query was asked once in an `{% if %}` and again in the body it guards. Each query is now computed once per row with `{% set %}` and read in both places.

## Why
`getJobsForSample` has no index. Every call is a linear scan of the page's whole job list, so a 25-row samples page did 100 scans where 50 are enough. The badge and the link ask different questions, so they stay as two cached values rather than being folded into one.

## Validation
- A new test, `tests/testJobsForSampleScans.py`, wraps `JobCollection.getJobsForSample` and counts calls by `(sample_id, method, matching_only, finished_only)` while it renders `/explore/samples` and `/explore/samples/<id>`. It asserts that each distinct query runs once per row. On master all three tests fail, because each query runs twice on rows that have jobs.
- Full suite and `ruff check .` pass.
- Live against mcrit 1.9.0 (66 samples, 193 jobs): 17 pages are byte-identical to master, whitespace included, once CSRF tokens are blanked. The new `{% set %}` lines use trailing whitespace control, so they add no blank lines. The pages:
  - four views of the samples listing, including its last page and the descending sort;
  - five family pages, one of them the empty family 0;
  - the sample pages of samples 0, 7, 8, 23 (11.6k functions) and 64;
  - query sample -1;
  - an unknown sample id;
  - a search.

  Between them, these cover both templates the change touches. `sample_row` gets a job collection only on the samples listing and the family pages, and `single_sample.html` is the sample page.
- The two callers that pass a job collection both show the analyze dropdown, so the `{% set %}` at the top of the row runs no query that the row didn't already run.

## Limitations
This reduces in-process filtering only, not backend calls. Bounding the backend fetch is #192.

## Merge conflicts
- **#160, `single_sample.html` and `table/sample_row.html`, the job badge.** #160 recolours the flask icon with `var(--status-yes)`, and this PR replaces the two `getJobsForSample` calls on the same lines with `matching_jobs`. Keep both: `{% if ... matching_jobs %}<i style="color:var(--status-yes);" ...>&nbsp;{{ matching_jobs | length}}`.
- Every other open PR merges cleanly.
