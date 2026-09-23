Title: Let /jobs select jobs by sample id and by job id

## Problem

MCRITweb needs two sets of jobs that `GET /jobs` can't select.

**The matching jobs of the samples on a page.** MCRITweb annotates each row of its sample listings (`/explore/samples` and `/explore/families/<id>`, 25 rows a page) with two things taken from the job queue:
- a badge counting that sample's matching jobs;
- a "Last 1:N Job" link to its newest finished `getMatchesForSample` job.

`GET /jobs` can only give it those by returning the whole `getMatchesForSample` and `getMatchesForSampleVs` queues. MCRITweb reads both on every page view and keeps the jobs whose first argument is on the page (`sample_row_job_collection` in `mcritweb/views/explore.py`). On a 1.9.0 instance with 214 such jobs, that is 159,714 bytes of queue data per page view, plus a `Job` built for each of those jobs on both ends. It grows with the installation's matching history, not with the page.

**The dependencies of a job.** A job's page fetches each dependency with its own `GET /jobs/{id}` (`job_by_id` in `mcritweb/views/data.py`), one request after another. For a cross compare that is one request per sample.

`/jobs` has no way to narrow either:
- `method` is already used.
- `start`/`limit` don't fit: a newest-N window undercounts the badge and drops the link for any sample whose jobs are older than the window.
- `filter` is one substring, tested in Python against `Job.parameters` after `get_jobs` has paged. Selecting 25 samples would take 50 requests, each reading a whole method.
- `state` is also applied in Python over the whole method.

Open PR #168 moves `filter` and `state` into the mongo query, which fixes the paging. `filter` still takes one substring, though, matched as an unanchored regex against either `payload.method` or `payload.params`. So it would still be one request per sample, and it can't name jobs by id.

## Proposal

Two optional parameters on `GET /jobs`, each a comma-separated list, applied in the query so that `start`/`limit` page the selection:

```
GET /jobs?method=getMatchesForSample&sample_ids=7,8,9
GET /jobs?job_ids=6ab3b4455ccfc2538ffea9bf,6ab3b4455ccfc2538ffea9c0
```

- `sample_ids` selects the jobs whose first argument (`Job.sample_id`) is one of the ids. `method` is required with it.
- `job_ids` selects the jobs with those ids.
- Both combine with the other parameters. Items that don't parse are ignored, as `start` and `limit` ignore values that don't parse, but a parameter that leaves no id selects nothing rather than everything.

In `MongoQueue.get_jobs`, `sample_ids` becomes an anchored regex on `payload.descriptor`, and `job_ids` an `$in` on `_id`:

```python
ids = "|".join(str(int(sample_id)) for sample_id in sample_ids)
# the literal prefix pins the method, so payload.method isn't needed next to it
query_filter = {"payload.descriptor": {"$regex": '^\\["%s", \\{"0": (%s)[,}]' % (re.escape(method), ids)}}
```

Why the pattern works:
- The descriptor is `get_descriptor(...)`, `json.dumps((method, params, file_params), sort_keys=True)`. `rearrange_params` stores positional arguments under `"0"`, `"1"`, …, and keyword names are identifiers, which sort after digits, so `"0"` always comes first.
- The routes queue the sample id positionally: `MatchResource` calls `index.getMatchesForSample(sample_id, ...)` and `getMatchesForSampleVs(sample_id, sample_id_b, ...)`.
- Descriptors from a 1.9.0 queue, with and without keyword arguments:

  ```
  ["getMatchesForSample", {"0": 8}, {}]
  ["getMatchesForSample", {"0": 8, "band_matches_required": 2}, {}]
  ["getMatchesForSampleVs", {"0": 8, "1": 12}, {}]
  ```

- The id is followed by `}` when it is the only argument and by `,` otherwise. `[,}]` accepts both, and keeps `1` from matching `12`. The quote after the method name keeps `getMatchesForSample` from matching `getMatchesForSampleVs`.

Checked against that queue for a page of 25 ids, the pattern selects exactly the jobs MCRITweb keeps today: 106 of 210 `getMatchesForSample` jobs and 4 of 4 `getMatchesForSampleVs` jobs.

`payload.descriptor` is already indexed. On MongoDB 8.0, a query on the descriptor pattern alone used that index (`payload.descriptor_1`). With `payload.method` in the query too, the planner picked `payload.method_1` and applied the pattern to the fetched documents instead. Since the prefix already pins the method, the query can leave `payload.method` out when `sample_ids` is given.

Also needed:
- `McritClient.getQueueData(..., sample_ids=None, job_ids=None)` forwards both.
- `JobResource.on_get_collection` parses them.
- `LocalQueue.get_jobs` gets the same selection in Python.

A caller that also wants the `...Vs` jobs naming a sample as their second argument would need a second clause (`"1": (ids)[,}]`). MCRITweb doesn't: its badge counts only jobs whose own `sample_id` is on the page.

## What MCRITweb would do with it

- `sample_row_job_collection` would pass the page's sample ids with each of its two requests, and keep `JobCollection.filterToSampleIds` as the exact check. The transfer would scale with the jobs of 25 samples, and the badges and links would stay as they are. This is the half of familiary/mcritweb#192 that MCRITweb can't fix on its own.
- `job_by_id` would fetch a job's dependencies in one request instead of one per dependency, which is part of what remains of familiary/mcritweb#191.
