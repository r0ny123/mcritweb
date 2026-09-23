Title: Memoize the unique blocks cover and make its first render deterministic

## Summary
Fixes #184.

The Unique Blocks result page no longer rebuilds the YARA block cover on every render. The cover is memoized per job and rule parameters, so paging the block table, filtering, following a tab link or reloading reuses it. The first view of a freshly fetched unique blocks job is also now the same as every view after it, which it was not before.

## What changed
- `mcritweb/views/memo.py` (new): the shared bounded memo.
  - `BoundedMemo` is a least-recently-used store bounded by weight (entry count by default) and guarded by a lock.
  - `app_memo(app, name, bound)` returns a named memo kept per app; `clear_app_memos(app)` empties all of them.
  - The branches for #186 and #187 carry this file byte for byte, and `tests/testMemo.py` too, so the three PRs merge in any order.
- `mcritweb/views/data.py`:
  - `build_yara_rule` takes the cover from `app_memo(current_app, "unique_blocks_cover", 32)`, keyed by the job id and the five parameters `generateBlockCover` reads, after clamping. `condition_required` only affects the rendered rule, so it shares the cover.
  - The stored cover is a read-only mapping (`types.MappingProxyType`) with a tuple of block hashes, because every request for those parameters is handed the same object.
  - The rule text itself is still rendered on every request.
  - `result_unique_blocks` puts `unique_blocks` in pichash order before building the rule. This is the order the cached copy has.
  - As a guard, the block table breaks score ties by pichash (`(-score, pichash)`). With the blocks already in pichash order this changes nothing today; it keeps the table from depending on that order in future.
- `mcritweb/views/administration.py`: `reset_server` calls `clear_app_memos(current_app)` in place of `# TODO also clean all locally cached data.` A reset restarts the backend's id counters, so anything memoized by job id would be stale.

## Why
- **Where the time goes.** Measured on the live 3- and 4-sample reports:
  - `generateBlockCover`: 50-100 ms at the default parameters, and 1.3-2 s at `required_per_sample=100`. It ran on every request, although a page shows 100 rows.
  - `renderRule`: a few milliseconds.
  - Sorting the ~3.5k blocks: about 1 ms.
  So only the cover is memoized, and the block table keeps a plain sort of the filtered blocks.
- **The rule text is not memoized.** `renderRule` stamps today's date into it, so a memoized rule would be copied out with a stale date. The copy button still copies exactly what is shown.
- **A memo needs a deterministic input.**
  - `generateBlockCover` and `renderRule` break ties by the order they meet the blocks in. A report fetched from the backend on this request has them in the backend's order, while every later render reads `cache_result`'s copy, whose keys are sorted. So on master the first view of a job could show a different rule than every later view.
  - Sorting `unique_blocks` by key on this path (about 1 ms) removes that. It is the only part of the report whose order reaches the cover or the rule: `statistics["by_sample_id"]` only seeds per-sample counters, and each block's `samples` list is turned into a set.
  - The normalisation is deliberately limited to this page. Doing it for every result type would change other pages' first render, for example which tab the cross-compare page opens on. It would also cost a JSON round trip on large reports.
- **Memory, not disk.** The rule parameters come from the query string, so the memo is bounded by entry count and least-recently-used eviction: a visitor can churn it but not grow it. Storing artifacts beside the cached result on disk was rejected because that cache is never cleaned up, and #145 is rewriting it.

## Validation
- **Tests.**
  - `tests/testUniqueBlocksMemo.py` covers:
    - the cover is built once across pages, tabs, filters and reloads;
    - each of the five cover parameters leads to a new cover, and switching back reuses the old one;
    - a changed parameter changes the rule;
    - `condition_required` shares the cover but still changes the rule;
    - the cover the route used is shared across requests and cannot be mutated;
    - the rule carries the current date;
    - a report fetched from the backend renders identically three times, which fails on master and also fails on this branch with the ordering line removed;
    - the table is ordered by score, then pichash;
    - the route keeps the memo within its bound;
    - `reset_server` clears the memo.
  - 11 of its 14 cases fail against master.
  - `tests/testMemo.py` covers the memo itself, including concurrent use.
  - `ruff check .` is clean and the full suite passes (984 passed, 23 skipped).
- **Live run** against an MCRIT 1.9.0 backend, jobs `6ab3b4131eeeb027e04b57b1` (samples 7, 8, 9), `6ab3b4131eeeb027e04b57b3` (family 1) and the cross-compare job `6ab3b4131eeeb027e04b57ae`:
  - With the result cache warm, the same 15-request sequence per unique blocks job renders identically on master and on this branch: tabs, block pages 1-3, filters, rule parameters, an empty cover. Only the session CSRF token differs; the rule text, cover summary and block table are byte-identical.
  - With the cached reports removed:
    - master's first render of …57b1 differed from its second and third;
    - this branch's first render equals its later renders and master's cached render;
    - the cross-compare page's first, second and third renders are identical to master's, including its own first-render difference, which this change leaves alone.
  - Thread CPU time inside the unique blocks handler (first request → median of later ones):

    | Request | master | this branch |
    |---|---|---|
    | Any tab or page | 165-195 ms on every request | 10-15 ms after the first request for a job and parameter set |
    | `required_per_sample=100` | 1.5-1.8 s every time | 15-20 ms on repeats |

    Wall-clock times over HTTP moved the same way but were too noisy on the shared test machine to quote.
  - 64 concurrent mixed-parameter requests over 12 threads all matched the sequential renders. No 500s in the server log.

**Checked again on a second instance** (mcrit 1.9.0, 66 samples), on all five unique blocks jobs there. One is an 11,598-function sample with a 35 MB result.
- Across 17 variants per job (tabs, block pages, page size, filters, each rule parameter, and an empty cover), the rule text, cover summary and block table were byte-identical to master.
- On the large job, a request took 4.6-7.0 s on master every time. Here a repeat takes 1.6-2.5 s.
- `required_per_sample=100` took 36-52 s on master every time. Here a repeat takes 1.9 s.
- One job no build had fetched before showed the first-render difference live. Master's first render started its block table at another pichash than its later renders did. This branch's first render already matched master's later ones.

## Limitations
- **Only the unique blocks first render changes.** It now matches every later render, where before it could show a different, equally valid cover. Renders from the cached copy are unchanged.
- **Still differs on the first view:** the per-sample statistics table follows `by_sample_id`'s order, and that order still differs between the first view and later ones, as on master (the cached copy sorts sample ids as strings, e.g. "10" before "7"). It doesn't feed the cover or the rule, so it is left as it was.
- **Per process:** the memo is per process, so each worker pays for the first view of a job and parameter set.
- **Reading the cached report JSON is still paid on every request.** That belongs to the result-cache work in #145.
- **Merging with #145:** two trivial import-line conflicts at the top of `data.py` (`import types` next to `import uuid`, and the `memo` import next to #145's extended `MatchReportRenderer` import). Keep both sides.

## Merge conflicts
- **#132, #145, #149**: import lines at the top of `data.py`. Keep both sides.
- **#147** (`result_unique_blocks`): this PR's ordering of `unique_blocks` and #147's `sample_versions` line are adjacent. Keep both.
- Every other open PR merges cleanly.
