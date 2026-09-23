Title: Fetch a page's missing entries and a job's dependencies in one request

## Summary
The rest of #191, on top of #221. Draft until mcrit ships danielplohmann/mcrit#BATCHPR and danielplohmann/mcrit#SELECTORPR: this needs them, and raises the `mcrit` floor to that release once it exists.

#221 made each sample and family entry cost at most one lookup per request, but still one lookup per id, since mcrit had no batch read. With mcrit's new batch lookups and `/jobs` selectors, a page asks for everything it is missing in one request:

| page (live, 1.9.0 corpus plus the two mcrit PRs) | backend calls: master | #221 | this | load time: master | this |
|---|---:|---:|---:|---:|---:|
| job page of the 40-sample cross compare | 82 | 82 | 4 | 306 ms | 30 ms |
| job page of the 66-sample cross compare | 134 | 134 | 4 | 506 ms | 35 ms |
| cross result, 40 samples | 42 | 42 | 3 | 454 ms | 251 ms |
| cross result, 66 samples | 68 | 68 | 3 | 1,026 ms | 879 ms |
| `/` | 7 | 7 | 3 | 32 ms | 22 ms |
| `/analyze/cross_compare?samples=0,11,20,30` | 6 | 5 | 3 | 32 ms | 21 ms |

Every one of these pages renders the same HTML as master.

This is based on #221's branch, so its base here is `fix/191-serial-entry-fetches`.

## What changed
- **`views/client.py`**: `get_sample_entries` and `get_family_entries` send the ids a call is missing in one `getSamplesByIds` / `getFamiliesByIds` request.
  - An id the backend has no entry for is absent from its answer and maps to None, as a single lookup answered.
  - A failed request answers `{}`, which does the same.
  - What the request already knows still costs nothing.
- **`data.job_by_id`** reads its dependencies with one `getQueueData(job_ids=...)` instead of one `getJobData` each.
  - A dependency that is gone is simply not in the answer and is counted as missing, as before. A failed read counts all of them as missing, rather than failing the page.
  - The answer is kept to the ids asked for, because a backend that doesn't know `job_ids` ignores it and answers the whole queue.
  - The dependencies' samples and families go through the helper, one request each.
- **`views/api.py`**: the passthrough forwards `POST /samples/ids` and `/families/ids`, as AGENTS.md asks for new client methods.
  - The body check is the one `/functions` uses, with negative sample ids allowed.
  - A body that isn't an id list answers 400 without the backend, which is what the backend itself answers.
- **Tests**:
  - The `testEntryLookups.py` helper counts ids asked for singly or in a batch, and the tests now also pin how many requests a call makes.
  - New: a failed batch answers None for each id; the job page reads its dependencies and their families in one request each; a gone dependency is counted; a backend that ignores the selector adds no jobs; a failed read counts every dependency as missing.
  - `testJobOverview.py`'s backend answers the new reads.
  - New `testApiBatchLookups.py` covers the passthrough.
  - The corpus fake answers the batch reads and both selectors, the way mcrit does.

## Why
The loops were serial because mcrit had no batch read, as #221 describes. The storage had one for samples (`getSampleEntriesByIds`); danielplohmann/mcrit#BATCHPR exposes it and adds families. The job page's dependencies are a set of job ids, which `/jobs` can select since danielplohmann/mcrit#SELECTORPR.

## Validation
- **Without the change**, 18 of the new and changed tests fail.
- **Full suite**: 1016 passed (#221: 1001 passed). `ruff check .` is clean.
- **Live**, the table above. It was measured through a request-counting proxy in front of an mcrit server with both mcrit PRs merged, on a 1.9.0 corpus of 66 samples. Each page was loaded once to warm the result cache; load time is the median of 3 more loads. Master, #221 and this branch ran side by side against the same server, and every page's HTML equals master's.

## Limitations
- **Not mergeable before the mcrit release.** mcrit 1.9.0's client has no `getSamplesByIds`, and its `getQueueData` takes no `job_ids`. When the release exists, the `mcrit` floor in `setup.py` and `requirements.txt` goes up to it, in this PR.
- The cross result pages still spend their time rendering; the lookups were a small share of it.

## Merge conflicts
Against the open PRs:
- **#221's own**, as its text describes: #115, #142, #159, #160 and #174, and the `data.py` import lines it shares with the #182 branch, which are #213's and #226's now (#226 is on #213's branch). In those import lines, keep both sides' names, and this branch's `get_family_entries` with them.
- **Four more**, all in `job_by_id`, next to the block this replaces: #133, #145, #149 and #214.
  - Keep this branch's two lines for the samples and families. They also cover #145's `not in families_by_id` guard, since the helper asks for each family once.
  - Keep the other PR's changes to the `render_template` call, and anything it adds after it, such as #214's `job_state`.
- Every other open PR merges cleanly, and so do the other two follow-ups.
