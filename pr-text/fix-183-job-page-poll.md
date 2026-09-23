Title: Poll a job's status instead of re-rendering its dependencies

## Summary
Part of #183. The issue asks for two things. The family guard on the jobs pages is already in #145, which
makes that one-line change on both pages. The job page's refresh loop is this PR. With both merged, #183 can be closed.

## Problem, measured on master (e4bfa55, live mcrit 1.9.0 stack)

Backend calls are counted from the mcrit server log by username. The reachability probe (one per request, logged as `mcritweb`) is left out of every count below.

| page | backend calls | median of 5 | size |
|---|---|---|---|
| `/data/jobs` (default tab) | 27 | 123 ms | 61.7 KB |
| `/data/jobs?active=combineMatchesToCross` | 52 | 190 ms | 36.9 KB |
| `/data/jobs/<id>`, 40-sample cross compare | 81 (41 `getJobData`, 40 `getSampleById`) | 296 ms | 76.4 KB |
| `/data/jobs/<id>`, 10-sample cross compare | 21 | 89 ms | 34.2 KB |

The jobs list is not auto-refreshed. The part of it the issue points at, the unguarded family loop, is fixed by #145, so this PR does not touch `data.jobs`. On this corpus no page of the list repeats a family: the `getUniqueBlocks` tab asks for families 2 and 6 once each.

The job page is where the cost repeats. Every job submitter redirects to it with `?refresh=3`, and until the job finishes it meta-refreshes. Each refresh is a full render: 1 + N `getJobData` plus one `getSampleById` per sample, for a cross compare over N samples.

I watched a forced cross compare over four samples (16, 17, 18 and the ripgrep PE) in Chromium on master for the 19 seconds it ran. That was 7 page loads and 63 backend calls, 9 per tick. Five of those ticks fell during the 15 seconds the ripgrep 1vN job ran, and the parent job's status (start, progress, finish, unfinished dependencies) did not change once in that time.

## What changed

- `data.job_status(job_info)` answers what the page is waiting on, all of it read from the job's own document:
  - `started_at`, `finished_at`, `failed` and `progress`;
  - the length of `unfinished_dependencies`, which the queue shrinks as each dependency finishes or finally fails.

  It is also registered as a template filter, so the page and the endpoint share one definition.
- `GET /data/jobs/<job_id>/status` (`data.job_status_by_id`) answers `{"status": ...}` from one `getJobData`, or a 404 for a job the backend no longer has. It is visitor-only and read-only, with a row in `tests/routePolicy.py`.
- `job_overview.html`: for an unfinished job with dependencies opened with `?refresh=N`, the meta refresh becomes a poll of that endpoint every N seconds. The page reloads when the answer differs from the one it was rendered from, or when the answer is not a 200 with JSON. The reload is the same full render as before, so the outcomes are unchanged:
  - a finished job still forwards to its result or shows "Results available";
  - a failed one still shows "The job failed!" and stops;
  - a deleted one still lands on `job_invalid.html`;
  - an expired session still ends on the login page.
- Three cases keep the meta refresh:
  - a job without dependencies, whose page renders from the same single call a poll would make;
  - a page without JavaScript, through a `<noscript>` copy;
  - a job document that carries no `unfinished_dependencies` list.
- README: one `* unreleased:` line, because anyone watching a cross compare will see the change.

The only rendered difference is in the `<head>` of that one case: the meta tag moves into `<noscript>` and the script follows it, adding 1,051 bytes. The body is identical.

Why this option and not the other two:
- **Batching:** the 1.9.0 client has no batch job call. `getQueueData(filter=...)` is a substring test over `Job.parameters`, applied after paging, so it cannot select a job's dependencies.
- **Reusing data across ticks:** keeping the meta refresh and reusing data would take a cross-request cache of samples and finished dependencies. That cache would show renamed families and deleted dependencies late, and it would still fetch every running dependency on every tick. The poll needs no cache at all.

`Job` exposes `all_dependencies` but has no accessor for `unfinished_dependencies`, so `job_status` reads that field off `job_info._data`, the document the client has already fetched. This is the first use of `_data` in mcritweb, and #149 avoided it on purpose. That PR, though, had every dependency in hand already, and here not fetching them is the whole point. The public alternatives are both worse:
- Raw mode would fetch the same document a second time.
- Counting from the rendered dependencies cannot agree with the queue's field once a dependency has been deleted. The mismatch would make the page reload on every poll.

An `unfinished_dependencies` property on mcrit's `Job` would remove the private access.

## Validation

- `tests/testJobPolling.py`, 15 tests. With the two code files reverted to master, 11 fail. The 4 that still pass are the equivalence guards (a finished job, a failed job, no `refresh`, a document without the field). The tests pin:
  - one `getJobData` per poll for a job with 40 dependencies;
  - the page polls and keeps a `<noscript>` refresh;
  - the poll answers exactly what the page was rendered from;
  - the answer changes when a dependency finishes or fails, and when the job starts, progresses, finishes or fails;
  - a job that is gone gets a JSON 404;
  - a job without dependencies keeps its meta refresh.
- Full suite: 1000 passed, and `ruff check .` is clean. The single warning is the `testCsrf.py` parametrize deprecation, which master has too.
- Rendered against master, with CSRF tokens blanked, every page is identical:
  - the 52 job pages of the live instance;
  - both cross compares above, with `?refresh=3` and `forward=1`;
  - the jobs list tabs.
- Live, with a second forced cross compare over the same four samples, watched in Chromium by both builds at once for its 20 seconds:

  | build | page loads | polls | backend calls |
  |---|---|---|---|
  | master | 7 | 0 | 63 |
  | this branch | 2 | 6 | 24 |
  | this branch, JavaScript disabled | 7 | 0 | 63 |

  All three ended on the same finished page. The branch reloaded into it 0.9 s before master's next tick.
- Per request, on the 40-sample cross compare: a render costs 81 calls, about 300 ms and 76 KB; a poll costs 1 call, about 20 ms and 188 bytes.

  With a synthetic in-memory backend at 4 / 40 / 200 dependencies, a render costs 9 / 81 / 401 calls and 25 / 69 / 268 KB. The poll stays at 1 call and 108 bytes throughout.
- The poll's JavaScript was driven in Chromium against a scripted backend, with master run through the same scenarios:
  - nothing changes: it polls and never reloads;
  - a dependency finishes: one reload, then polling resumes;
  - the job finishes, fails or is deleted: a reload into the same page master reaches, then polling stops;
  - the probe fails, or the session is cleared: it ends where master does;
  - JavaScript is disabled: the meta refresh reloads every second, as on master;
  - `refresh=3000000`: it waits, because the delay is clamped to setTimeout's range.

## Limitations

- A running dependency's own progress is not on the parent's document. The percentage and start time in its row now update when the job's status next changes, not every tick.

  In the live run the ripgrep row read 0.00% until the job finished; master showed 66.67, 75, 83.33, 91.67 and 100. Making that live again without the per-dependency calls would need the poll to read the unfinished dependencies (1 + unfinished calls per poll) and update that cell in place. That is left for later.
- A dependency deleted while the job waits does not touch the parent's document either. The "no longer in the system" notice therefore appears at the next reload rather than the next tick. The page itself is unchanged, so the earlier sub-job 500 does not come back.
- A render costs what it did before; the change is only in how often it happens. `/data/jobs` is untouched.

## Conflicts with open PRs

- #160, #208, #211 and #212 each add an `* unreleased:` line at the top of README's version history too. Each pair conflicts textually; keep every line.
- #176 moves that version history into `CHANGELOG.md`. If it lands first, this PR's line moves to `CHANGELOG.md` under `[Unreleased]`.
- #149: merges cleanly and its tests pass, but the two overlap in behaviour. Its "Total (since queued) ... and counting" row and its progress averaged over the dependencies are both computed at render time. On a polled cross compare they will advance when the page reloads, not every three seconds.
- #107, #115, #122, #132, #133 and #145 merge cleanly. With each one merged into this branch, that PR's changed test files pass together with `testJobPolling.py`, `testRoutePolicy.py`, `testJobOverview.py`, `testScriptEscaping.py` and `testJavascriptScoping.py`. #133 adds its route-policy row directly after `data.job_by_id`, so this PR's row goes just before it.
