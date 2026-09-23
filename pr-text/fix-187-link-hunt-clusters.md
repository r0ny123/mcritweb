Title: Reuse link hunt clusters across paging and link score changes

## Summary

Fixes #187.

On every request, the link hunt fetched every function of the reference sample, control flow graphs included, and clustered again. That included turning a page of the individual links and changing the link score filter, and neither of those changes what gets clustered. This PR memoizes the clustering and reuses it. The rendered output is unchanged.

## What changed

- **`views/data.py`, `linkhunt_for_sample_or_query`:** the fetch, `clusterLinkHuntResult` and sort now run inside a `compute` function, through `app_memo(current_app, "linkhunt_clusters", 32).get(cluster_key, compute)`. The clustering code itself is unchanged.
  - **The key** is the job id plus every argument passed to `getLinkHuntResults`.
  - **The link score filter** still runs after clustering, as before. It builds a new list, so the memoized clusters stay unfiltered.
  - **Exclusion lists** are keyed as sorted sets, and an empty list is keyed like None. That is the only difference between the default view and a submitted copy of its form. Nothing else is normalised, and the code comment says why: the checkbox always parses to a bool, and a threshold of 0 only matches "no filter" if the report has no negative values, which mcrit doesn't check.
- **`views/memo.py` (new, shared):** a bounded, thread-safe, least-recently-used memo kept per app (`app_memo`, `clear_app_memos`). The same file is carried byte-for-byte by the unique-blocks (#184) and function-diff (#186) branches, so the three PRs merge in any order.
- **`views/administration.py`, `reset_server`:** calls `clear_app_memos(current_app)` in place of the "TODO also clean all locally cached data". A reset restarts the backend's id counters, so a job id can come back meaning a different job.

## Why

The issue suggests clustering depends only on the cached result. It doesn't: `clusterLinkHuntResult` clusters the output of `getLinkHuntResults`, so the score, lib score, size, offset, family-count, exclusion and strongest-per-family filters all change what it sees. Only the link score filter is applied afterwards. Keying on exactly those arguments keeps the output identical to today and makes paging and link score changes free.

The memo is in memory rather than next to the cached report. The clusters are `MatchedFunctionEntry` objects, not JSON, and #145 is reworking the result cache.

## Validation

**Tests**
- `tests/testLinkHuntClusters.py`, 16 tests on the captured corpus:
  - one function fetch across the default view, page 2, a form submit and a link score change (4 fetches on master);
  - a second clustering for a changed value of each of the 9 `getLinkHuntResults` arguments. Removing any one argument from the key fails exactly its own case, checked for all 9;
  - cached and fresh cluster tables are identical for four filter sets;
  - the link score filter still applies to cached clusters and doesn't change the stored copy;
  - `reset_server` clears the memo; this fails without the hook.
  - Six fail on master. The re-clustering and reset tests pass there by design, because master caches nothing.
- `tests/testMemo.py` covers the shared helper.
- The full suite and `ruff check .` pass.

**Live run**

1vsN jobs of samples 7 and 8 (coreutils ls and cp), with 7 filter sets each and 3 requests each, through a proxy that counts backend calls:

| | master | this branch |
|---|---|---|
| Function fetch | on every request: 1,507,432 B (sample 7) / 1,715,692 B (sample 8) | only the first request for each filter set |
| Time per request | about 0.5–1.6 s | first request 0.68–0.85 s, the same work as master; after that 20–100 ms |
| Backend traffic after the first request | as above | 2 calls, 840 B |

The cluster rows and links extracted from all 14 pages are identical to master's.

## Limitations

- The first request for each filter set costs the same as today. The memo is per process, so each worker warms its own.
- Entries are evicted, never invalidated, apart from a server reset. That is the same assumption the result cache makes: a job's result doesn't change.
- A threshold of 0 and an empty threshold are keyed separately. They may miss each other's entry, but they never share a wrong one.
- Merging with #145 gives a one-line conflict in the imports. #145 extends the `MatchReportRenderer` import, and the `memo` import that isort requires sits on the next line. Keep both lines.
- Not fixed here, and it already happens on master: an empty `filter_unpenalized_family_count` in a non-default filter request, for example `/data/linkhunt/<job>?filter_min_score=65`, returns a 500 from `getLinkHuntResults` (`int < None`).
- The clusters hold the reference sample's function entries as they were when first clustered. If a function is renamed while an entry lives, the cluster table shows the old name until the entry is evicted or the process restarts.
- This branch carries `mcritweb/views/memo.py` and `tests/testMemo.py` byte-identical with the #184 and #186 PRs, plus the same `reset_server` hunk, so the three merge cleanly in any order.

## Merge conflicts
- **#130**: #130 wraps `getFunctionsBySampleId` in `require_result(...)`, and this PR moves that call into the clustering closure. Keep the closure and put `require_result` around the call inside it.
- **#145**: import lines. Keep both.
- Every other open PR merges cleanly.
