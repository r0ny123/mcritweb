Title: Confirm sample/family modifications instead of sleeping a fixed time

## Summary

Fixes #189.

`explore.modifySample` and `explore.modifyFamily` no longer sleep for a fixed time after a modify. They read the sample or family back until the change shows, for at most 0.3s, and then redirect and say what happened. 0.3s was master's old fixed delay; it is now the upper bound on every route, the cross compare redirect included. This is a bounded wait, not the removal of all waiting: on an idle backend it ends after about 0.1s, and on a busy one it is never longer than master.

## What changed

- `mcritweb/views/explore.py`
  - `await_modification()` polls every 0.05s up to `MODIFICATION_TIMEOUT` = 0.3s. If a request reading the change back fails (`requests.RequestException`), the failure is logged with the sample or family id and treated as not confirmed instead of becoming a 500. Any other exception still surfaces.
  - `is_sample_modified()` / `is_family_modified()` check the requested values. The family check follows `MongoDbStorage.modifyFamily`:
    - a rename deletes the family's row, also when it merges into an existing family of that name;
    - family 0 is the exception: it keeps its row and name, with zeroed counters;
    - `is_library` sets `num_library_samples` to `num_samples`, so a family without samples can never read as a library.
  - `flash_modification()` reports one of three outcomes:
    - "Sample modified." / "Family modified.";
    - "The ... modification was sent, but MCRIT has not confirmed it yet - reload in a moment to check.";
    - "MCRIT did not accept the ... modification.", which is not waited for.
  - The unconditional `time.sleep(0.3)` in both routes is removed, and so is the extra `time.sleep(1)` before redirecting to a cross compare. A form that changes nothing now says "Nothing to change." instead of claiming a job was scheduled.
- `tests/testModifyRoutes.py`: 19 tests.
  - The fake backend applies modifications a given number of reads late and mirrors mcrit's family semantics (family 0, merging, empty families).
  - A fake clock lets the tests measure the wait without actually waiting.
  - `caplog` pins the id in the read-back warning.

## Why

The delay covered a real gap. mcrit queues these changes as worker jobs:
- `SampleResource.on_put` / `FamilyResource.on_put` call the `@Remote` `Worker.modifySample` / `modifyFamily` and answer 202 with a message but no job id.
- Against a live 1.9.0 backend, a read right after the PUT was stale 10 times out of 10. The change showed up 95-115 ms later, which matches the worker's 0.1s idle poll.
- All three pages these routes redirect to read live data, so without any wait they show the old values.
- With no job id, redirecting to the job page (as the delete routes do) is not possible.

A fixed sleep costs its full length on an idle backend and is still too short on a busy one. Reading the change back ends the wait as soon as the change is there, and tells the user when it is not.

Responding at once and reloading from the client was considered and rejected. The first render would still be stale, and the cross compare page, the heaviest of the three, would be rendered twice.

## Validation

- `tests/testModifyRoutes.py`: 19 passed. The tests fail against master's `explore.py`.
- Full suite and `ruff check .` pass.
- Live, against mcrit 1.9.0. Each step toggled `is_library` on sample 3 and on family 3, and every change was restored afterwards. The table shows the POST time, median of 5 (max):

  | Case | master | this branch |
  |---|---|---|
  | sample, back to samples list | 594 ms (652) | 144 ms (153) |
  | sample, back to cross compare | 1476 ms (1598) | 146 ms (330) |
  | family, set library | 322 ms (531) | 89 ms (153) |
  | family, unset library | 390 ms (524) | 150 ms (261) |

  The page the user lands on showed the new value 5/5 in every case. With the wait removed entirely, the list pages were up to date only 0-2 times out of 5.
- No 500s in the server log.
- Repeated on a second instance, with 66 samples and 193 jobs. The table gives POST time, median of 5 (max):

  | Case | master | this branch |
  |---|---|---|
  | sample, back to samples list | 319 ms (323) | 76 ms (135) |
  | sample, back to cross compare | 1320 ms (1334) | 75 ms (135) |
  | family, set and unset library | 317 ms (322) | 78 ms (137) |

  - The landing page showed the new value in 5 of 5 cases on both builds.
  - A form that changes nothing took 1017 ms on master when it returned to a cross compare, because the extra second sat outside the change check, and master still flashed that a job was scheduled. Here it takes 16 ms and says "Nothing to change."
  - That instance also showed the new rejection message working. mcrit 1.9.0 refuses an empty version (`PUT /samples/<id>` with `version=` answers 400: its check requires at least one character, while its message says 0-64 are allowed). Master flashed "Job to modify sample was scheduled." and left the version unchanged. This branch says "MCRIT did not accept the sample modification."

## Limitations

- On a busy backend a modify still holds the request until the deadline, and then tells the user the change is not confirmed yet.
- The deadline is only checked between reads. The worst case is therefore 0.3s plus the duration of one read, not exactly 0.3s.
- Waiting on the job itself would need mcrit's `on_put` to return the job id.
- Family renames (including family 0), a busy worker and a failing read-back are covered by the offline tests only. A live rename changes family ids and cannot be undone exactly, so it was not run against the shared backend.

## Merge conflicts
- **#130, `explore.modifyFamily`.** #130 wraps `client.modifyFamily(...)` in `require_result(...)` and keeps the fixed sleep. This PR replaces both with its own handling of an answer that is not a 200/202. Keep this PR's version: `require_result`'s docstring says a view with its own handling keeps it. #130 does not touch `modifySample`'s call, so that merges cleanly.
- Every other open PR merges cleanly.
