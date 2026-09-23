Title: Poll a running job's status instead of reloading its overview

## Summary

Part of #183: the job page now polls a small status endpoint. The missing family guard on the jobs pages is in #145; with both merged, #183 can be closed.

While a job runs, its overview page reloaded itself with a meta refresh, and every reload ran the whole page again. For a cross compare over 13 samples that is 28 backend calls every 3 seconds, and nearly all of them fetch things the previous reload already had. The page now polls a small JSON endpoint that reads only the job itself, and reloads only when something it shows has changed.

The other half of the issue is the missing `not in families_by_id` guard on the family loops in `data.jobs` and `data.job_by_id`. #145 already adds that guard, so this PR leaves it alone.

## What changed

- **`data.job_status`** (new, `GET /data/jobs/<job_id>/status`)
  - It makes one `getJobData` call and answers `{started, finished, failed, progress, unfinished_sub_jobs}`. An unknown job gets a JSON 404.
  - It uses `visitor_required` and then `mcrit_server_required`, like `data.job_by_id`, and has its own row in `tests/routePolicy.py` (`VISITOR, READ_ONLY`).
- **`job_overview_state(job_info)`** builds that answer.
  - `job_by_id` builds it the same way, so the page and the endpoint describe the job identically. It only builds it when the page will emit the polling script (`refresh` > 0 and the job not finished), so a finished job's page never reads it.
  - `unfinished_sub_jobs` comes from the job document's `unfinished_dependencies`. The queue drops a sub-job from that list when it finishes. It also drops it when it fails for good: `Job.error` calls `_notify_dependent_jobs` once `attempts_left` reaches 0, and so does `release_orphaned_jobs`. So the parent job alone shows how many sub-jobs are still unfinished, and a sub-job that fails for good triggers a reload just as a finished one does.
  - mcrit 1.9.0's `Job` has no property for that field, so it is read with `getattr(job_info, "_data", {})`. If a future `Job` drops the raw document, the count reads 0 and only that reload trigger is lost, rather than every job page failing.
- **`job_overview.html`**
  - The meta refresh now sits inside `<noscript>`, so without JavaScript the page behaves exactly as before.
  - With JavaScript, a small inline script polls `job_status` every `refresh` seconds. If `started`, `finished`, `failed` or `unfinished_sub_jobs` differs from what the page rendered, it reloads the page. Otherwise it only updates the progress cell in place.
  - A response that is not `ok`, which is what a job that no longer exists gets, is thrown into the failure path. So is an answer that is not JSON: for an expired session or an unreachable backend, the endpoint redirects, `fetch` follows the redirect to an HTML page, and reading that as JSON fails. The failure path reloads once, and the reload renders whatever the problem is. For a job that no longer exists, that is `job_invalid.html`, which has no script, so polling stops.
  - The poll interval is capped at 2^31-1 ms. `setTimeout` treats a larger delay as no delay, so an oversized `refresh=` would otherwise poll as fast as the backend answers.
  - Values reach the script only through `|tojson`. The request is a same-origin GET, so it needs no CSRF token.
- **`job_column_table`** takes an optional `progress_id` for the progress cell.
  - Only `job_overview.html` passes one (`job-progress`).
  - `job_in_progress.html` also renders the progress row, but it has no script, so it keeps the cell without an id rather than having a fixed id hardcoded in the macro.

## Why

The issue asks that the status the page waits on come from a small endpoint, rather than refetching the whole job tree on every tick. I considered two other ways to do this:

- **Reload only once the job finishes.** Each tick would cost one call, but the sub-job table would stay frozen for the whole run. A cross compare's parent job does not start until its sub-jobs are done, so the page would look stuck until the very end.
- **Skip the sample and family lookups on the server on refresh ticks.** The sub-job rows need those entries to render, so skipping them would mean caching entries across requests.

Reloading on a real change keeps what the old page showed about the job and its sub-jobs, apart from the gaps listed under Limitations. A tick where nothing changes now costs 2 backend calls (the reachability probe plus one `getJobData`) instead of 28.

## Validation

**Offline tests**

- `tests/testJobOverview.py`:
  - the status endpoint makes exactly one backend call and returns the expected fields;
  - an unknown job gets a JSON 404;
  - a running job's page polls, and its only meta refresh is the one inside `<noscript>`;
  - the state rendered into the page equals the endpoint's answer for an unchanged job, so an idle tick does not reload;
  - a finished job neither polls nor refreshes;
  - a page that will not poll never builds the poll state;
  - the state survives a `Job` without its raw document.
- `tests/testJobOverviewBrowser.py` (new) drives the script in Chromium. It is skipped when playwright or a Chromium is missing, like `testFunctionVsBrowser.py`, and honours `MCRITWEB_CHROMIUM`. It uses a loopback `live_server` over the fake backend, with `page.route` where a test needs one particular answer. It checks that:
  - an idle tick does not reload;
  - progress alone is updated in place;
  - a changed state reloads exactly once;
  - a job that has gone (a real 404 from the endpoint) reloads once, lands on the invalid-job page and stops polling.
- **Failing before this change**
  - On master, six of the offline tests fail. The finished-job test pins behaviour master already has.
  - The two robustness tests fail on the first version of this branch.
  - I checked the browser tests by mutation:
    - turning the meta refresh back into a plain one fails the idle and changed-state tests;
    - making the failure path a no-op fails the gone-job test.
- The full suite passes with Chromium available: 991 passed and 5 skipped on the first instance, 996 passed on the second, where every browser test ran. `ruff check .` is clean.

**Live**, against mcrit 1.9.0. I started a fresh cross compare over all 13 samples with `rematch=on` through `/analyze/start_cross_compare`, and queued three more identical cross compares ahead of it so the job had to wait. I watched the job page in headless Chromium, with a counting proxy between mcritweb and the backend that attributes each backend call to the browser request that caused it.

| | master | this branch, JS on | this branch, JS off |
|---|---|---|---|
| backend calls per reload | 28 (probe + 14 `getJobData` + 13 `getSampleById`) | 28 | 28 |
| backend calls per tick where nothing changed | 28 (every tick reloads) | 2 (probe + 1 `getJobData`) | 28 |
| whole run (about 16-19 s, refresh=3) | 5 loads, 142 calls | 1 load + 6 polls, 3 of which reloaded on a change: 124 calls | 6 loads, 170 calls |

- **Why the whole-run saving is small:** a cross compare over 13 small samples finishes within seconds, and a sub-job finishes on most ticks, so most ticks do have something new to show. The saving grows with the number of ticks where nothing changes, such as a job waiting in a long queue or a sub-job that runs for minutes. Those ticks now cost 2 calls instead of 28.
- **Rechecked after the review changes:**
  - A job opened with `forward=1` still ends on its result page (`/data/result/<id>`), with no JavaScript errors in Chromium.
  - A queued cross compare reloaded only when a poll saw a change.
  - A finished job's page (`?refresh=3`) carries neither the poller nor a meta refresh.
- The status endpoint answers a finished job, an unknown id, and a malformed id (`nonsense`, which gets a JSON 404). Without a session it redirects to `/login`.
- The flask log showed no 500s.

**Checked again on a second instance** (mcrit 1.9.0, 66 samples, one worker). Master and this branch each watched the same jobs at the same time, `?refresh=3`, in headless Chromium, each behind its own counting proxy:

| jobs watched | master | this branch |
|---|---|---|
| a forced cross compare over all 66 samples (41 s), and a forced 1vN on sample 16 queued behind it | cross compare page 9 loads; 1vN page 12 loads; 1,230 backend calls | cross compare page 6 loads and 9 polls; 1vN page 3 loads and 11 polls; 850 backend calls |
| a forced 1vN on the 11.6k-function sample and a forced 4-sample cross compare (14 s) | 5 loads each; 60 backend calls | 2 loads and 4 polls each; 40 backend calls |

- Every page ended on its finished state, with no console or page errors.
- On a forced 20-sample cross compare, the status endpoint counted `unfinished_sub_jobs` down from 11 to 0 before `finished` turned true, and an idle tick cost the probe and one `getJobData`.
- Also in Chromium, against the app with a stand-in backend:
  - with the session cookie cleared mid-poll, the page reloads once, lands on `/login` and stops;
  - with the backend reported down mid-poll, it reloads once, lands on the index and stops;
  - `?forward=1` still ends on `/data/result/<id>` once the job finishes;
  - with JavaScript disabled, the `<noscript>` refresh reloads at the configured interval.
- A job without sub-jobs costs the same two calls a tick either way (the probe and one `getJobData`), so there the gain is that the page is no longer reloaded while it waits.

## Limitations

**What does not trigger a reload**, because none of it changes the parent job's document. Between reloads, these stay as the page last rendered them:

- a sub-job going from queued to running, and a running sub-job's own progress percentage;
- a sub-job that errors but still has attempts left and is retried, which stays in `unfinished_dependencies`;
- a retried parent job's new `started_at`. `started` is still true, so the "Started:" cell keeps the first start time until the next reload.

The parent job's own progress is updated live.

**Other limitations:**

- `unfinished_sub_jobs` reads the raw job document. A `Job.unfinished_dependencies` property in mcrit would make that a public read; it is worth requesting upstream.
- The page still fetches the sample for each sub-job on every reload, one call per sample. #191 covers that.

## Merge conflicts
All three are mechanical, in lines both sides extend:
- **#115** (`data.py`): #115 rewrites the lookup loops just above the `render_template` line of `job_by_id`, so git puts the functions this PR adds after that line into the same conflict. Keep #115's loops, then everything this PR adds from its `job_state` line on.
- **#133** (`data.py`, `tests/routePolicy.py`): both add keyword arguments to the `render_template` line of `job_by_id`. Keep them all: `job_state=job_state` from here, `can_rerun=...` and `configuration_url=...` from #133. Keep both new rows in `routePolicy.py`.
- **#149** (`job_overview.html`, `column_table.html`, `data.py`): both add a keyword argument to `job_column_table` and to `render_template`. Keep both. #149 shows a job's sub-job average in the same progress cell while its sub-jobs run, and this PR's script writes the job's own progress into that cell once the job itself has started. To keep #149's number there, pass `progress_id="job-progress"` only when `child_progress is none`.
- The other 26 open PRs merge cleanly, and so does every other branch of this set.
