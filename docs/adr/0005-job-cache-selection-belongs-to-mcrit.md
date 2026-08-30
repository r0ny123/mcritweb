# The queue's job-cache selection belongs to mcrit

---
status: accepted — blocked upstream
---

Issue #47 reports that a force rematch destroys the usable result of an earlier job: the
finished report stops being reachable while the new job runs. **MCRITweb cannot fix
this**, and its own `force_recalculation` plumbing is not the cause.

The selection happens in `mcrit/libs/mongoqueue.py:490-501`:

```python
find_one({"attempts_left": {"$gt": 0}, "payload.descriptor": ..., "terminated": False},
         sort=[("created_at", pymongo.DESCENDING)])
```

The newest non-terminated job with attempts left wins, **regardless of whether it has
finished** — so a still-running force-rematch job shadows an older *finished* job with a
usable result. That is exactly the reported behaviour, and the issue's own proposed fix
(prefer finished, then by age; exclude failed and terminated) is a change to this one
query.

There is no MCRITweb-side half. The descriptor is derived backend-side from the method
and its parameters, so this application cannot look up the finished job and redirect to
it. Its own handling is already correct: `analyze.py:204/272/282` pass
`force_recalculation` only when asked, and the "raw string `false` is truthy" trap is
already fixed and commented at `analyze.py:184` and `:268`.

## Consequences

Do not attempt a workaround in this repository. Anything that tried to reach past the
descriptor cache would be guessing at a backend invariant, and guessing wrong here means
showing a user the wrong report.

There is a real user-facing workaround worth putting on the issue: deleting the running
job via `POST /data/jobs/<job_id>/delete` (`data.py:830`) removes it from the candidate
set, after which the finished job is selected again.

## Outcome

Ask `danielplohmann/mcrit` to change the cache-selection rule in
`mongoqueue.get_cached_job_id`. Nothing here changes.
