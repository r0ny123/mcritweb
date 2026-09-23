Title: Aggregate only the current page of the function match table

## Summary

Part of #194. This PR covers the part of #194 that PR #145 / #185 doesn't. That PR already turns the two `len(getAggregatedFunctionMatches(...))` calls in the view into counts. The remaining full rebuild was the template's own `getAggregatedFunctionMatches(funp.start_index, funp.limit)`, which aggregates the whole filtered report just to slice out one page. After this PR, only the page gets aggregated. The rendered HTML is byte-identical to master.

## What changed

- `mcritweb/views/data.py`: new `aggregate_function_matches_page(matching_result, pagination)`.
  - It takes the sorted distinct function ids of the filtered report and keeps the ones on the current page.
  - It hands only those functions' matches to mcrit's own `getAggregatedFunctionMatches()`, on a `copy.copy` of the result, so the view's `filtered_function_matches` is untouched.
  - The 1-vs-N and `?famid=` branches pass its result to the template as `function_rows`.
- `result_compare_all.html`, `result_compare_family.html`: the function table loops over `function_rows`.
- `tests/testFunctionTableRows.py` (new), see Validation.

## Why

A row of this table is the aggregate of one function's matches, and rows are ordered by function_id. So a page consists of exactly the matches of the page's function ids, and aggregating those gives the same rows as aggregating everything and slicing. I reused mcrit's aggregation instead of rewriting it here, so any change upstream carries over.

What I left alone, and why:
- **The row count behind the pagination and the `filtered:` figure.** This is #185. PR #145 replaces those calls with `count_aggregated_function_matches`, and redoing it here would just conflict.
- **The sample-match passes the issue lists** (`getBestSampleMatchesPerFamily` twice, `num_family_matches` / `num_library_matches`, `num_original_*`, and the single calls on the sample and family pages).
  - Each of these computes a different value exactly once; nothing is computed twice. Measured on a2, all six together take about 5 µs.
  - The only way to merge them would be to paginate the ranked lists by their own length. That changes the output: `getBestSampleMatchesPerFamily` groups by family name, while the counts group by family_id. The captured corpus report has family_id 4 under both `''` and `MSVC`, so the library table would say "total: 2 … (filtered: -1)" where master says "total: 1 … (filtered: 0)".
  - The mismatch between the count and the rows drawn already exists and is its own bug. It's out of scope here.

## Validation

**Tests.** `tests/testFunctionTableRows.py` (13 tests):
- For both aggregated corpus reports, unfiltered, narrowed to each matched family, and under two function filters, every page at `funl` 10, 100 and 250 (plus one page past the end) equals `getAggregatedFunctionMatches(start, limit)`.
- The view's filtered list is left untouched.
- The whole rendered page (plain, `funp=3`, `filter_exclude_pic`, and each `famid`) is byte-identical to the page rendered with the old aggregate-then-slice call patched back in.
- While a page renders, no aggregation runs with `start`/`limit`, and the rows come from an aggregation over exactly the page's 10 functions.
- On master, the 4 cases of `test_the_table_rows_are_aggregated_from_the_page_alone` fail for the real reason: `assert [(10, 10)] == []`, the template's aggregate-then-slice call. The other 9 are equivalence guards; they fail on master only because the helper doesn't exist there.

Other checks:
- `ruff check .` is clean.
- `testRoutePolicy`, `testCsrf`, `testScriptEscaping`, `testResultPages`, `testResultTemplateCoverage`, `testQueryResults`, `testPromoteQuery`, `testUserFilters`: 219 passed.
- The full suite passed.

**Live, against the mcrit 1.9.0 backend.** Pages covered: the 1vsN jobs …a0 and …a2 (plain, `famid`, `samid`, `funid`, a filter, a later page), the query job …c217 (plain, `famid`, `funid`), and the 1vs1 job …ac (two pages).
- In process: all 16 pages are byte-identical to master.
- Over HTTP from `flask run`, master checkout and branch on the same port: all 11 pages byte-identical, and no errors in either log.
- The live reports are small (a2 has 172 function matches), so render time is the same within noise (8–17 ms per page either way).
- Same pages on a synthetic report: a2's summaries repeated 200 times, 34,400 matches over 85,600 functions. Matches fed to the aggregation per render, and median in-process CPU time over 8 renders:

| page | master | this PR | #145 | #145 + this PR |
|---|---|---|---|---|
| plain | 103,200 / 1462 ms | 68,964 / 1219 ms | 34,400 / 1027 ms | 164 / 788 ms |
| `famid=1` | 96,000 / 1423 ms | 65,346 / 1217 ms | 30,800 / 1013 ms | 146 / 812 ms |
| `funl=10&funp=5` | 103,200 / 1510 ms | 68,815 / 1179 ms | 34,400 / 992 ms | 15 / 749 ms |

- In isolation on that report, the table's aggregation drops from 112 ms to 3.3 ms per render.
- What's left (about 750 ms, the same as the `funid` page, which aggregates nothing) is `MatchingResult.fromDict` and the JSON load.

**Checked again on a second instance** (mcrit 1.9.0, 66 samples):
- 45 result pages are byte-identical to master, whitespace included.
- They come from five jobs: an 11.6k-function sample's 1vsN, three other 1vsN jobs, and a query job.
- Each job was taken plain, on pages 2 and 3, at `funl` 10 and 250, with `famid`, with `samid`, with `filter_exclude_pic`, and on a page past the end.
- The largest page took 130 ms instead of 174 ms (median of 5, warm cache).

## Limitations

- This conflicts with PR #145 on two lines: the `render_template(...)` calls of the family and unfiltered branches, since both PRs add a keyword argument there. The fix is to take #145's line and add `function_rows=aggregate_function_matches_page(matching_result, function_pagination)`. I merged the two that way and re-ran everything above.
- The helper uses a shallow copy of `MatchingResult`, so it depends on `getAggregatedFunctionMatches` reading only `filtered_function_matches` and the family-name map. That holds in mcrit 1.9.0, and the equality test fails if it stops holding.

## Why this doesn't close #194
- The two `len(getAggregatedFunctionMatches(...))` passes the issue names are #185's, and PR #145 removes them.
- The sample-match passes the issue lists each compute a different value, once: two ranked lists with different filters, and four counts over filtered and original data. Together they take about 0.005 ms on the live 1vsN report. They can't be merged without changing output. The counts group by family_id and the ranked lists by family name, and the captured corpus has family_id 4 under both `''` and `MSVC`.
- #194 can be closed once #145 and this PR are in, unless the sample-match side should be pursued anyway.
- Found along the way, not fixed here: on the unfiltered 1vsN page, the library table header counts by family_id while its rows are drawn by family name. With a family_id that carries two names, the header says 1 and the table shows 2 rows.

## Merge conflicts
- **#145**: the two `render_template(...)` lines, as described under Limitations.
- **#148**: adjacent helper definitions in `data.py`. Keep both.
- **#152**: a conflict in meaning, not only in text. #152 also passes `function_rows` to these templates: it sorts the whole aggregated list by the column the user picks, then pages it. This PR aggregates a page alone, which is only equivalent while the table is in function-id order. Whichever lands second has to reconcile them. Keep this PR's helper for the default order, and aggregate everything for any other sort key.
- Every other open PR merges cleanly.
