Title: Let /jobs select jobs by sample id and by job id

## Summary
Fixes #SELECTOR.

`GET /jobs` gains two optional, comma-separated selectors, `sample_ids` and `job_ids`. They are applied in the query, so `start` and `limit` page the selection rather than the whole method. MCRITweb can then read the matching jobs of a page of samples, and a cross compare's dependencies, in one request each.

## What changed
- **`MongoQueue.get_jobs`** takes `sample_ids` and `job_ids`, and a new `_get_jobs_filter` builds the query:
  - `sample_ids` selects the jobs of `method` whose first positional argument is one of the ids. It matches `payload.descriptor` with two anchored regexes per id, in an `$in`; Why has the reason. Without `method`, or with no id left, it selects nothing.
  - `job_ids` becomes `{"_id": {"$in": [...]}}`, of the ids that parse as `ObjectId`.
  - Both apply before the `state` branch and before paging.
- **`LocalQueue.get_jobs`** takes the same two and applies them in Python: the first argument from `payload.params`' `"0"` key, and set membership on the job id.
- **`QueueRemoteCalls.getQueueData`** forwards both, by keyword, because the two queues' `get_jobs` order their positional parameters differently.
- **`JobResource.on_get_collection`** parses `sample_ids` as comma-separated ints and `job_ids` as comma-separated strings, and drops the items that don't parse. `sample_ids` without `method` answers 400.
- **`McritClient.getQueueData`** takes `sample_ids` and `job_ids` after the existing parameters, whose order is unchanged, and sends them as comma-separated values.
- `MongoQueue.get_jobs` is annotated `List["Job"]` instead of `Optional[List["Job"]]`. It never returned None, and `ty` flagged the new tests' iteration over its result.
- **Tests**:
  - `testMongoQueue.py`, 12:
    - first argument only, and `getMatchesForSample` never picking up `getMatchesForSampleVs`;
    - negative ids, paging after the selection, the `state` branch;
    - empty and invalid selectors selecting nothing, and both selectors combined;
    - the index keys a selection reads.
  - New `testLocalQueue.py`, 10: the same rules on LocalQueue.
  - `testJobResource.py`, 7: the 400, parsing, empty selectors forwarded as empty, and both together with `state` and `filter`.
  - `testClientErrors.py`, 4: what the client sends, an empty list included, and raw mode.

## Why
- **Nothing else narrows the query.** `filter` is one substring, tested in Python after `get_jobs` has paged. `state` is also decided in Python, over the whole method. Selecting a page of 25 samples would take 50 requests today.
- **The descriptor is the field to match.** `rearrange_params` stores positional arguments under `"0"`, `"1"`, …, and `get_descriptor` writes `json.dumps((method, params, file_params), sort_keys=True)`. So `"0"` always follows the method name: `["getMatchesForSample", {"0": 16}, {}]`. `payload.params` isn't key-sorted.
- **Index bounds.** An anchored regex bounds an index scan only by its literal prefix, and a regex with an alternation got no bounds at all. With the index forced, `(16|17)[,}]` read every key.
  - So each id becomes two regexes that are literal to their end: `^\["getMatchesForSample", \{"0": 16,` and `^\["getMatchesForSample", \{"0": 16\}`.
  - The `$in` of them bounds one range of the existing `payload.descriptor` index per regex. The terminator is part of the prefix, so id 1 doesn't also read 10-19 and 100-199.
  - `payload.method` isn't queried as well, because the literal prefix already pins it.
- **First argument only.** `getMatchesForSampleVs`'s second argument is not matched. MCRITweb counts a sample's own jobs, as the issue describes.
- **Unparsable items are dropped**, as `start` and `limit` treat unparsable values. A selector that is present but keeps no valid id selects nothing, never everything.
- **`job_ids` is validated in `MongoQueue`**, not in the resource, because LocalQueue's ids are uuid strings. What counts as valid depends on the queue.

## Validation
- **Without the change** (the five non-test files as on main), 31 of the 33 new tests fail. The other two check that nothing changes when neither selector is given.
- **Full suite** against MongoDB 8.0: 352 passed, 49 subtests (main at 2ac8d7b: 319 passed, 49 subtests). `ruff format --check`, `ruff check` and `ty check` are clean.
- **At scale**, on a synthetic queue of 60,000 jobs for 6,000 samples on MongoDB 8.0, with `get_jobs`'s own `_id` sort, median of 5:

  | selection | jobs | this change | one regex with an alternation | one regex per id, ending in `[,}]` |
  |---|---:|---|---|---|
  | 25 consecutive sample ids | 99 | 102 index keys, 1.3 ms | all 60,000 documents through `_id`, 114.5 ms | 102 keys, 1.6 ms |
  | 25 ids including 1, 10 and 100 | 98 | 124 keys, 1.7 ms | all 60,000 documents, 103.8 ms | 4,645 keys, 80.2 ms |
  | 2 sample ids | 7 | 10 keys, 0.5 ms | all 60,000 documents, 97.4 ms | 898 keys, 1.8 ms |

  Every form answered the same jobs, in the same order, as a Python check over the queue. The last column is why the terminator is part of each literal prefix.

- **Live**, read-only, through a server on this branch in front of a 1.9.0 queue with 210 `getMatchesForSample` and 4 `getMatchesForSampleVs` jobs:
  - For seven id sets per method (1-25, 0-24, 16 and 17, 24-60 in steps of 4, 1, -1/1/10, 0-65), `sample_ids` answered exactly the jobs of the whole method filtered in Python, in the same order and with the same content.
  - `job_ids` with the dependencies of three cross compares (20, 15 and 13 jobs) answered each job exactly as `GET /jobs/{id}` does.
  - The 25-sample query read 116 index keys for 110 jobs, through `payload.descriptor_1`. Median of 7: 10.8 ms and 82,133 bytes, against 12.9 ms and 156,686 bytes for the whole method. Two samples took 2.8 ms and 8,242 bytes.
  - `sample_ids` without `method` answered 400, and `sample_ids=x,y` answered no jobs.
  - MCRITweb's follow-up changes ran against a server with this and danielplohmann/mcrit#BATCHPR, and every page they touch rendered the same HTML as before.

## Limitations
- `sample_ids` matches the first positional argument only, as described above.
- On MongoQueue, `job_ids` that aren't valid ObjectId hex are dropped without a per-id error.
- `LocalQueue.get_jobs` slices with `limit` even when it is 0, so without a `limit` it answers no jobs, with or without these selectors. That is how it behaves today, and it is left alone here.
- The `mcrit client` console gets nothing new: its `queue` command exposes only `--filter`.

## Changelog
A proposed `[Unreleased]` entry. It isn't in the branch, so that this PR and the other open ones don't conflict in the same section:

> ### Added
> - `GET /jobs` takes `sample_ids` (with `method`) and `job_ids`, applied in the query before paging, and `McritClient.getQueueData` passes them on. On a 60,000-job queue, selecting the jobs of 25 samples read 102-124 index keys in under 2 ms ([#SELECTOR]).

## Merge conflicts
- 20 of the 22 open PRs merge cleanly.
- **#183** rewrites every client method's signature and docstring. The conflict is in `getQueueData`'s signature and docstring only. Keep the two new parameters, typed `Optional[List[int]]` and `Optional[List[str]]` in #183's style, and mention them in its one-line docstring. #183's `_passthrough` change merges in on its own.
- **#168** moves `filter` and `state` into the query, through a `_job_query` helper, and adds `/jobs/count`. It conflicts in the five files both change. To resolve:
  - add this change's two conditions to #168's `_job_query` (MongoQueue) and `_matching_jobs` (LocalQueue), and the two parameters to `get_jobs` and `get_job_count`;
  - forward them through its `getQueueData` and `getQueueCount`;
  - parse them in its shared `_selection(req)` helper, which then answers the same 400 for `sample_ids` without `method` on both routes;
  - pass them through its client query builder.

  Two test details change once #168 is in. `_matching_jobs` sorts by `number`, which the hand-built jobs in `testLocalQueue.py` then need. And #168's `urlencode` percent-encodes the commas, which `testClientErrors.py` then decodes.
