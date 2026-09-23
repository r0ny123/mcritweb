Title: Ask the job queue only for the jobs of the samples on the page

## Summary
The rest of #192, on top of #222. Draft until mcrit ships danielplohmann/mcrit#SELECTORPR: this needs it, and raises the `mcrit` floor to that release once it exists.

The sample listings annotate each row with its matching jobs. To find them, each view read the whole `getMatchesForSample` and `getMatchesForSampleVs` queues, every matching job the installation ever ran, to keep the few whose sample is on the page. With the `sample_ids` selector on mcrit's `/jobs`, each of the two requests names the page's sample ids, and mcrit selects their jobs in its own query:

| page (live, 1.9.0 corpus with 214 matching jobs) | queue data read: #222 | this | load time: #222 | this |
|---|---:|---:|---:|---:|
| `/explore/samples`, first page (25 samples) | 159,714 bytes | 85,161 bytes | 76 ms | 70 ms |
| `/explore/samples?query=variants` (25 samples) | 159,714 bytes | 52,278 bytes | 61 ms | 56 ms |
| `/explore/families/10` (10 samples) | 159,714 bytes | 18,717 bytes | 45 ms | 32 ms |
| `/explore/families/5` (2 samples) | 159,714 bytes | 8,278 bytes | 39 ms | 27 ms |

Every one of these pages renders the same HTML as on #222, with the same backend calls. What each read costs now scales with the jobs of the samples on the page, not with the installation's matching history.

This is based on #222's branch, so its base here is `fix/192-bounded-collections`.

## What changed
- **`views/explore.py`**, `sample_row_job_collection`: both `getQueueData` calls pass `sample_ids`, the ids of the samples on the page.
  - `filterToSampleIds` stays as the exact check. It also keeps a backend that doesn't know `sample_ids` correct: that one ignores the parameter and answers the whole method, as before.
  - The docstring says so, and #222's note that `/jobs` has no selector to bound the reads with goes.
- **`views/api.py`**: the `/api` passthrough forwards `sample_ids` and `job_ids` on `/jobs` as the lists `getQueueData` takes, as AGENTS.md asks for new client parameters.
  - An item that isn't an id is dropped, as the backend drops it.
  - A present but empty list stays empty, which selects nothing rather than everything.
- **Tests**:
  - `testExplorePageCalls.py`: each of the two queue reads names exactly the samples on the page, for the listing and a search.
  - New `testApiJobSelectors.py`: the passthrough forwards both selectors, drops what isn't an id, keeps an empty list empty, sends neither when the request has none, and forwards the other parameters as before.
  - The corpus fake applies both selectors the way mcrit does: in the query, before `start` and `limit`, with `sample_ids` refused without a method.

## Why
#222 explains why these reads can't be bounded from MCRITweb alone. A newest-N `limit` undercounts the badges and drops the "Last 1:N Job" link for older samples, and `filter` is one substring per request. danielplohmann/mcrit#SELECTOR asks for the selector, and danielplohmann/mcrit#SELECTORPR adds it. It is applied in the query, bounded by the `payload.descriptor` index, so `start` and `limit` page the selection rather than the method.

## Validation
- **Without the change**, 7 of the 9 new tests fail. The other two pass either way by design: a request that names no selector sends none, and the other parameters are forwarded as before.
- **Full suite**: 1007 passed (#222: 998 passed). `ruff check .` is clean.
- **Live**, the table above. It was measured through a request-counting proxy in front of an mcrit server with danielplohmann/mcrit#SELECTORPR, on a 1.9.0 corpus of 66 samples. Each page was loaded once to warm it; the load time is the median of 3 more loads. #222 and this branch ran side by side against the same server. The byte counts are the two `/jobs` answers each view reads.
- The selector itself was checked against the same queue in danielplohmann/mcrit#SELECTORPR: for every id set tried, it answers the same jobs, in the same order, as the whole method filtered in Python.

## Limitations
- **Not mergeable before the mcrit release.** mcrit 1.9.0's `getQueueData` has no `sample_ids`. When the release exists, the `mcrit` floor in `setup.py` and `requirements.txt` goes up to it, in this PR.
- On this corpus, over half the matching jobs (114 of 214) belong to the first 25 samples, so the first listing page still reads about half of what it did. Those are its own jobs.

## Merge conflicts
- One: #115, in `sample_row_job_collection`, where #115 wraps the jobs in `describable_jobs()`. Keep #115's comment and `JobCollection(describable_jobs(jobs))`, and this branch's `filterToSampleIds(sample_ids)`.
- #222's own conflicts, #126 and #130, carry over as its text describes.
