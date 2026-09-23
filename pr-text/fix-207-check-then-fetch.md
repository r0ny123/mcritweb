Title: Drop the existence probes in front of fetches that already answer for an unknown id

## Summary
Part of #207.

Three of the check-then-fetch pairs in #207 were a second round trip to learn something the fetch that follows already reports. Each of those fetches answers `None` for an unknown id, so the probe added nothing. The other two instances the issue names stay, for the reasons under Limitations.

## What changed
- `data.match_functions` calls `getMatchFunctionVs` directly and branches on `None`. Before, it asked `isFunctionId(a) and isFunctionId(b)` first, and mcrit's `MatchResource` runs those same checks again inside the call, answering 404 for an unknown id.
- The `samid` filter in `data.result_matches_for_sample_or_query` now reads the sample once with `getSampleById` and keeps the entry. Before, it called `isSampleId` and then `getSampleById` two lines later, on the same endpoint.
- `MatchReportRenderer.processReport` calls `getFunctionsBySampleId` for the reference sample directly, and falls back to `{}` when it answers `None`. That is the same fallback the `isSampleId` guard selected. `/samples/<id>/functions` answers 404 for an unknown sample.
- `AGENTS.md` says to check `is*Id` before acting on a user-supplied id. It gains the exception: when the call you need answers `None` for an unknown id itself, that `None` is the check.
- The `tests/conftest.py` docstring that described `match_functions`' old guard is brought up to date.

## Why
Every one of these pairs asked the backend the same question twice, back to back, on pages that are already backend-bound.

Backend calls per view, counted in-process against the captured corpus. The first three rows were also counted live, from mcrit 1.9.0's request log, with the same numbers:

| View | master | this branch |
|---|---|---|
| function comparison, `/data/matches/function/<a>/<b>` | 8 | 6 |
| the same with an unknown id | 3 | 2, same flash |
| sample-filtered result page (`?samid=`), drawing its diagram | 7 | 5 |
| the same page once the diagram is cached | 5 | 4 |

## Behaviour change
The mcrit client answers `None` for a backend error as well as for a 404 (`handle_response`). Where master then indexed that `None`, it raised a `TypeError`:
- **Two existing functions whose comparison the backend fails to produce:** master answered 500. This branch shows the page's existing "One of the function_ids is not valid." flash, which blames the ids for what was a backend failure.
- **A sample whose function list the backend fails to return:** master answered 500. This branch draws the diagram without function data.

The other failures injected at these calls end as they did on master, or better: an unreachable `/samples/<id>` behind the diagram was a 500 and now draws it. None raises here that did not raise on master.

## Validation
- New `tests/testCheckThenFetch.py`, five tests. All five fail on master and pass here. They pin that:
  - the comparison page makes no `isFunctionId` call and exactly one `getMatchFunctionVs`;
  - a `samid` page makes no `isSampleId` call and one `getSampleById`, for a 1vN report and for a query report;
  - the comparison survives `getMatchFunctionVs` answering `None` for two valid ids;
  - the diagram survives `getFunctionsBySampleId` answering `None`.
- The existing unknown-id test in `tests/testFunctionPages.py` still lands on the same flash.
- Full suite and `ruff check .` pass.
- Live against mcrit 1.9.0 (66 samples, including an 11.6k-function sample), with CSRF tokens blanked, the rendered HTML is identical to master:
  - on the function comparison pages;
  - on 1vN and query result pages, plain and with `samid`, including negative (query) sample ids and an unknown `samid`.

  With their cached diagrams cleared first, the regenerated PNGs are md5-identical to master's.

## Limitations
- **The single-sample export (`specific_export`) is left alone.** Its `getSampleById` is what tells an unknown id apart there. Without it the route would call `getExportData([])`, which asks the backend for `/export/` and gets the whole corpus back. That bug is fixed in its own PR, which keeps the lookup deliberately.
- **`unique_blocks`' per-id `isSampleId` validation is deliberate**, as the issue says. mcrit 1.9.0 has no batch sample lookup to replace it with.
- **`explore.fetchCombinedDotGraph` has the same pair** (`isFunctionId` twice before `getFunctionById` twice). A test pins that route's validate-first behaviour, so it is not changed here.

## Merge conflicts
- **#145, `data.py`, the `samid` branch.** #145 drops that branch's `create_match_diagram` call, and this PR drops its second `getSampleById`. The two edits are on adjacent lines. Whichever lands second deletes both lines and keeps this PR's walrus lookup.
- **#130, `data.py`, `match_functions`.** #130 wraps `getMatchFunctionVs` in `require_result(...)` behind the `isFunctionId` pre-check. That turns a `None` into its backend-failure page. Here `None` also means "unknown id", so a plain merge would show the failure page for a mistyped id.
  - If this lands second, keep this PR's `match_functions`.
  - If this lands first, #130 should keep it too.
  - Either way, the comparison's backend failure keeps the misleading flash described under "Behaviour change". The fix for that is a message that names both possibilities, and it fits better in #130.
