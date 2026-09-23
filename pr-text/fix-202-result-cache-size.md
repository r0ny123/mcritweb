Title: Bound the result cache and write cached reports as compact JSON

## Summary

Part of #202. This PR bounds the result cache and makes cached reports and downloads compact.
- The atomic write is in #145.
- Export streaming is still open. It needs a raw mode for `getExportData` in mcrit first.

**This must merge after #145, or together with it.** On its own it widens a read race that #145 closes (see Limitations).

## What changed

- **`mcritweb/views/data.py`**
  - **Compact JSON.** `cache_result` writes with `separators=(",", ":")` instead of `indent=1`. `download_result` serialises a cache miss the same way, so a miss and a later hit still serve identical bytes.
  - **New `trim_result_cache(app)`**, called after each write where the TODO was.
    - It does one `os.scandir` pass, sorts files by mtime (oldest first), and removes files until the cache is within both bounds.
    - It keeps no state in memory, so it is correct across threads and worker processes.
    - A victim that a concurrent trim already removed still counts as evicted. A file that cannot be removed is logged and skipped. Windows refuses to delete a file that is open for reading.
    - `cache_result` wraps the call. A trim that fails, for example with a `PermissionError` from `scandir`, is logged and never fails the page. The report is already written and the page renders from memory.
  - **Download fallback.** `download_result` catches `NotFound` and `FileNotFoundError` from `send_from_directory` and fetches from the backend instead. These cover a report evicted between the lookup and the open, on either side of Werkzeug's `isfile` check.
  - **Comment fix.** The "never invalidated" comment in `download_result` now says that nothing is evicted for being stale, only for size.
- **`mcritweb/__init__.py`**: two new config keys, overridable from `instance/config.py`.
  - `RESULT_CACHE_MAX_BYTES`, default 1 GiB.
  - `RESULT_CACHE_MAX_FILES`, default 1000.
  - `create_app` validates both the way it validates `TRUSTED_PROXY_COUNT`.
    - Accepted: a non-negative int (not a bool), a string of digits, or `None`. `None` removes that bound.
    - Anything else logs a warning and uses the default.
    - Without this check, `"1000"` raised a `TypeError` after the write, which meant a 500 on every first view and a cache that never trimmed.
- **`AGENTS.md`**
  - The "Result caching" bullet and the testing note now say that results are evicted for size, oldest-written first, and never for staleness.
  - A new bullet next to the other operator keys documents both keys, the validation, and the rule that a failing trim never fails a page.
- **`tests/testResultCacheBounds.py`** (new): 30 tests.

## Why

- **Compact JSON.** `indent=1` made reports about 1.5× larger on disk and in every download. Every reader parses these files with `json.load`: `MatchingResult.fromDict`, `MatchReportRenderer.load_cached_result` and mcrit's console. `/data/import` takes exports, not results, so it is unaffected. Reports cached before this change stay indented and keep working.
- **Two bounds.** The byte bound is the disk budget. The file bound caps how many reports the directory holds, whatever their size. It is not a performance fix: listing 1000 names takes under a millisecond.
- **Eviction order.** Oldest-written first, by mtime.
  - The timestamp in the filename carries the same information to the second. Mtime also breaks ties within a second, and orders files that `cache_result` did not name.
  - It is not LRU, because a cache hit does not touch the file. Evicting a popular report costs one refetch.
- **Diagrams cache left out.** It is small: 13 PNGs, 41 KB in total, next to 4.4 MB of reports. On master a diagram is only rendered during the result page request, so an evicted diagram would break the `<img>` that follows. #145 makes `diagram_file` render a missing diagram on demand, and after that the same trim can safely be applied to diagrams.
- **Exports unchanged.**
  - mcrit 1.9.0's `McritClient.getExportData` ignores `raw_responses` and always goes through `handle_response`, so there is no raw path to stream from.
  - The backend also wraps the body as `{"status":..,"data":..}`. Passing it through would change the file users import unless it were parsed anyway.
  - The pages never inspect the export, so once mcrit adds a raw mode the passthrough is simple.

## Validation

**Tests.** `tests/testResultCacheBounds.py` has 30 tests. The full suite passes (992 passed, 23 skipped) and `ruff check .` is clean.
- **Fail on master because the behaviour is missing:**
  - the compact-file and identical-bytes tests;
  - the file and byte bounds enforced through page views;
  - an evicted report being fetched again;
  - both download fallbacks: a 404 on master for `NotFound`, and a 500 for `FileNotFoundError`.
- **Guards on the new code.** These fail on master only because the code does not exist yet: the `trim_result_cache` unit tests, the failing-trim test, and the configuration tests.
- **Pass on master:** three accepted-value configuration cases (0, 5, `None`), because master stores the value unchanged.
- **Fail on the previous revision of this branch:** the invalid-value, digit-string, text-bound and failing-trim tests.

**Live** (mcrit 1.9.0, all 17 finished jobs, cache cleared first)

| | master | this branch |
|---|---|---|
| cache, all 17 reports | 7,039,735 B | 4,434,021 B (-37%) |
| unique blocks, samples 7-9 | 3,147,796 B | 1,981,825 B |
| unique blocks, family 1 | 3,379,421 B | 2,122,343 B |
| 1vsN sample 8 | 68,590 B | 42,200 B |

- **Downloads.** Every download was byte-identical to its cache file and parsed to the same object as master's. The 1vs1 and 1vsN reports load with `MatchingResult.fromDict`. A download on a cache miss equals the file it cached.
- **Bounds, set as strings.** `RESULT_CACHE_MAX_FILES = "3"` was honoured. `RESULT_CACHE_MAX_BYTES = "lots"` logged the warning and fell back to 1 GiB.
  - Viewing seven results in turn always kept the three newest.
  - Viewing an evicted report again returned 200 and cached it anew.
- **Concurrency.** 60 page-plus-download pairs across 13 reports from 16 threads: 59 fully 200. One page view returned a 500. It was a `FileNotFoundError` in `load_cached_result`, which is the read race described below. An earlier run with integer bounds had 60 of 60.
- **Exports** (routes unchanged). Family 1 (1,386,619 B), sample 12 (376,709 B) and the full export (2,498,987 B) are semantically equal to master's after decompressing `function_entries`. The raw bytes differ between any two exports, master included, because the compressed blobs carry a timestamp.

**Checked again on a second instance** (mcrit 1.9.0, 66 samples), with an empty cache:
- Six reports, among them a 35 MB unique blocks result, took 33.7 MB on disk instead of 51.8 MB (-35%). The unique blocks result alone went from 49.6 MB to 32.3 MB.
- Every download parsed to the same object as master's, and was byte-identical to its cache file.
- With `RESULT_CACHE_MAX_FILES = 3`, the first new write trimmed the cache to three files, and it stayed at three. An evicted report viewed again returned 200 and was cached anew. There were no 500s in the log.

## Limitations

- **Merge after or with #145.**
  - On this branch alone, a request that has listed the cache but not yet opened a report can lose it to a concurrent eviction and return a 500. I reproduced this once in 60 under a 3-file bound. A review reproduced it under a tight bound (5 × 500 requests).
  - The same review also saw torn reads from master's non-atomic write.
  - #145 fixes both: `load_cached_result` skips unreadable files, and `write_atomically` makes the write atomic.
  - I left `load_cached_result` alone here so that this PR does not add a second conflict with #145.
- **Conflicts with #145.** `git merge-tree` reports two conflicts.
  - `cache_result`: take #145's version, change `indent=1` to `separators=(",", ":")` in its `write_atomically` call, drop the TODO, and add the wrapped `trim_result_cache(app)` call after the write.
  - `AGENTS.md`, the "Result caching" bullet: keep #145's `write_atomically` sentence and this PR's eviction sentences.
  - With both resolved, this PR's tests together with #145's cache, atomic-write, diagram and result-page tests pass (217 passed). #145's temporary files live in `cache/incomplete/`, outside the directory the trim scans.
- **Upgrading.** A deployment with more than 1000 cached reports, or more than 1 GiB of them, is trimmed on its first cache write after the upgrade. All of that deletion happens inside that one request. This belongs in the next release entry. No version bump here.
- A single report larger than the byte bound is evicted as soon as it is written. The page is still rendered from memory.

## Merge conflicts
- **#145**: as described under Limitations.
- **#114** (`mcritweb/__init__.py`): both add a config default in the same place, the result cache bounds here and `MCRIT_SERVER_PROBE_TTL` there. Keep both.
- **#148, #211** (`AGENTS.md`): adjacent edits to the testing note and to the uploads bullet. Keep both.
- Every other open PR merges cleanly.
