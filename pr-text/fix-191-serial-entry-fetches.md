Title: Look up each sample and family entry at most once per request

## Summary
Part of #191.

mcrit 1.9.0's client and REST API have no batched sample lookup, so each sample or family a page names costs its own `getSampleById` or `getFamily` call, made one after another. Several pages paid twice: once for an entry they already held, and again for the same id. This PR adds one per-request lookup helper and routes the sites the issue lists through it. None of the pages this PR touches asks for the same sample twice any more, and none fetches a sample it already has. The pages render the same HTML as before.

This does not close #191. The pages with the most lookups are unchanged:
- the cross result page still makes one call per sample of the cross compare;
- the job page still does too, and also makes its serial `getJobData` per dependency, which this PR does not touch;
- the sample page saves one call.

Collapsing those needs a batch lookup in mcrit, so #191 should stay open until mcrit has one (see Why). The mcrit issue asking for it still needs to be filed.

## What changed
**`mcritweb/views/client.py`** gets the helper, next to `get_client()`, whose client it uses:
- `get_sample_entries(ids)` and `get_family_entries(ids)` map the distinct ids to their entries, or to `None` as before when the backend has none.
- Everything fetched stays on `g` for the rest of the request, so no id is asked for twice.
- `remember_samples(entries)` lets a page hand over entries it already holds.

**Index (`/`)**:
- It asks for the five latest samples first and remembers them. The job rows then look up only samples that are not among those five; a sample that was just submitted is often the one that was just matched.
- The family lookup goes through `get_family_entries`. It had no `not in` guard before.
- `search_samples("", sort_by="sample_id", is_ascending=False, limit=5)` stays. It is already the cheapest bounded call: one query on the `sample_id` index, with the database limit set to six. `getSamples(start, limit)` pages by insertion position with `skip`, so reaching the newest five would first need a count (`getStatus`) and then a skip over the whole collection.

**`explore.sample_by_id`** remembers its own `sample_entry` before it builds the job table. Every job in that table names this sample, because that is the filter, and the page used to fetch it a second time.

**`analyze.cross_compare` and `analyze.unique_blocks`** now run their sample search before looking up the selection, and remember the rows it returns. A selected sample that the search table on the same page already shows needs no lookup of its own.
- The "search failed" flash is still emitted where it was: after the unknown-id redirect in `cross_compare`, and after the unresolved-id warning in `unique_blocks`. So the messages keep their order, and a redirect does not carry an extra one.
- One cost moved: on `cross_compare`'s unknown-id redirect path, the search now runs and its result is thrown away. Before, the redirect happened before the search. That path is one extra bounded query, and only for a URL naming a sample that does not exist.

**`data.result_matches_for_cross`** and the sample loop of **`data.job_by_id`** go through the same helper. Both already asked for each id once, so their call counts are unchanged.
- `result_matches_for_cross` now looks up the whole sequence before it checks for a missing sample. A deleted sample no longer stops the lookups early, but that path still renders `result_corrupted.html`.

## Why
I checked whether the backend can collapse these loops into one request. It can't, not yet.

- **`McritClient`** has `getFunctionsByIds` (`POST /functions`), but nothing like it for samples.
- **The server's sample routes** are only `/samples`, `/samples/{id}`, `/samples/sha256/{sha256}` and `/samples/{id}/functions`.
- **The storage layer already has the batch.** `StorageInterface.getSampleEntriesByIds` exists, with one `$in` per collection in `MongoDbStorage.getSampleEntriesByIds`, and `MatcherInterface` already uses it. Only a REST route and a client method are missing. Once they exist, `get_sample_entries` can send its miss list in one request, and no caller has to change.
- **`getSamples(start, limit)`** pages by position, not by id.
- **`search_samples` doesn't work as a batch API either:**
  - It can be made to return a set of ids: `sample_id:7 OR sample_id:8` works live.
  - But lowercase `or` silently returns nothing.
  - The grammar builds a nested OR per id.
  - Search never returns query samples, which have negative ids.
  - The offline corpus does not model the parser.

I also considered a small bounded concurrent fetch, and decided against it:
- It would be safe on the client side. `McritClient` shares no `requests.Session`: each call is a module-level `requests.get`, and it only reads `headers`.
- The cost lands on the backend. mcrit 1.9.0's own `runServer` serves with waitress at its default of 4 threads (`serve(wrapped_app, listen="*:8000")`, with gunicorn off by default). A page fanning out four lookups would take every backend thread for its duration.
- The gain is small: 13 serial `getSampleById` calls took about 87 ms locally.

## Validation
**Tests**: new file `tests/testEntryLookups.py`, using `corpus_mcrit` plus monkeypatches.

The helper:
- Repeated ids are asked for once.
- An unknown id maps to `None` and is asked for once.
- A remembered sample is not asked for.
- Families are deduplicated.
- Nothing is kept past the request.

The pages:
- `/explore/samples/0` asks for its own sample once, and for each job partner once.
- `/analyze/cross_compare` and `/analyze/unique_blocks`:
  - With a selection the search table shows, they make no lookups.
  - A selected sample the search table does not show is looked up once and shown.
  - When the search fails, every selected sample is looked up, and the messages come in the same order as before: the unconfirmed sample, then the failed search.
  - An unknown id in a cross compare selection is dropped with a redirect after one lookup. That redirect carries only its own warning, even when the search failed.
- A cross compare whose sequence names a deleted sample still renders `result_corrupted.html`, and asks for each sample once.
- The job page resolves its sub-jobs' samples through the per-request lookup: two sub-jobs naming one sample cost one call, and a sample the request already holds costs none.
- The index asks once for a sample that two jobs name, and not at all for one that is among the latest samples. Both still render.

Against master's views (keeping only the helper module), 8 of the page tests fail. The rest pin behaviour the reordering could have broken: message order on a failed search, the corrupted cross result, and the redirect's messages.

The full suite passes: 978 passed and 23 skipped without Chromium, 1001 passed with it. `ruff check .` is clean.

**Live**, against mcrit 1.9.0. A proxy in front of the backend counted backend calls per page. Each page was loaded once to warm the local result cache, then measured on the second load, each column on a fresh server on the same port. I re-ran the branch column after the review changes and got the same numbers.

| page | master | this branch |
|---|---|---|
| `/` | 7 (5 `getSampleById`) | 2 (0) |
| `/explore/samples/7` | 8 (5) | 7 (4) |
| `/data/result/6ab3b4131eeeb027e04b57ae` (cross, 13 samples) | 15 (13) | 15 (13) |
| `/data/jobs/6ab3b4131eeeb027e04b57ae` | 28 (13) | 28 (13) |
| `/analyze/cross_compare?samples=7,...,12` | 8 (6) | 5 (3) |
| `/analyze/cross_compare?samples=0,...,12&query=coreutils` | 12 (10) | 9 (7) |
| `/analyze/unique_blocks?samples=7,8,9` | 5 (3) | 2 (0) |

- On the index, the five most recent 1vN jobs were for samples 8-12, which are also the five latest samples.
- The cross result and job pages already asked for each of their 13 distinct samples once. They cannot go lower without a batch lookup.
- All seven pages rendered HTML byte-identical to master, apart from the CSRF token.
- The flask log showed no 500s.

**Checked again on a second instance** (mcrit 1.9.0, 66 samples), master and this branch side by side, each behind its own counting proxy, measured on the second load:

| page | master | this branch |
|---|---|---|
| `/`, when the five latest 1vN jobs name none of the five latest samples | 7 (5 `getSampleById`) | 7 (5) |
| `/`, after a cross compare over every sample made four of them the same | 7 (5) | 3 (1) |
| `/explore/samples/0`, `/13`, `/23` | 5 (2) | 4 (1) |
| `/explore/samples/8` | 6 (3) | 5 (2) |
| `/data/result/<40-sample cross compare>` | 42 (40) | 42 (40) |
| `/data/jobs/<40-sample cross compare>` | 82 (40) | 82 (40) |
| `/analyze/cross_compare?samples=0,1,2` | 5 (3) | 2 (0) |
| `/analyze/cross_compare?samples=3,3` | 4 (2) | 2 (0) |
| `/analyze/cross_compare?samples=0,11,45` (11 and 45 are off the search page) | 5 (3) | 4 (2) |
| `/analyze/cross_compare?samples=0,1,2&query=family_id:2` | 5 (3) | 3 (1) |
| `/analyze/cross_compare?samples=40,...,51&ps=2` | 4 (2) | 4 (2) |
| `/analyze/cross_compare?samples=0,99999` (redirect) | 3 (2) | 3 (1, plus the search) |
| `/analyze/unique_blocks?samples=1,2,3,4&query=family_id:2` | 6 (4) | 2 (0) |
| `/analyze/unique_blocks?samples=16,17` | 4 (2) | 4 (2) |
| `/analyze/unique_blocks?samples=0,99999` | 4 (2) | 3 (1) |

- All 23 pages checked, including `/explore/samples/-1`, `/explore/samples/99999` and both selection pages without a selection, render byte-identical to master apart from the CSRF token. For the redirects, the page they lead to and its flashed messages are identical too.
- The index gains only when a recently matched sample is also among the five latest samples, so its count depends on the queue.

## Limitations
- **The pages that matter most are unchanged:**
  - The cross result and job pages still cost one call per distinct sample.
  - The job page also still makes one `getJobData` per dependency.
  - Both need the mcrit batch lookup described in Why.
- **Other places still fetch the same entry twice.** This PR does not touch them:
  - `data.jobs` still has both of its loops, and its family loop and `job_by_id`'s are left to #145, which adds the missing guard on exactly those lines.
  - `functiondiff._adhoc_picblock_pairs` fetches a sample twice when both functions belong to it.
- **The entries live on `g`**, like `get_client()`'s client. In production every request gets its own app context. A test that pushes an outer app context around several requests shares one `g`, and so would share the cached entries too.
- **`getFamily` keeps its default `with_samples=True`**, even though the index and job rows only read the family name. That is a separate change.

## Merge conflicts
- **#115** (`__init__.py`, `data.py`, `explore.py`): #115 passes the jobs through `describable_jobs()` before these lookups, so that one job whose payload cannot be read no longer takes the index or a job page down. Keep that filter and look up what it returns:
  - on the index, keep `described_jobs = describable_jobs(jobs)` and pass `described_jobs` instead of `jobs or []` to `get_sample_entries` and `get_family_entries`;
  - in `job_by_id`, keep `described_children` and call `samples_by_id.update(get_sample_entries(job.sample_ids or []))` inside its loop;
  - in `sample_by_id`, #115 filters when it builds the collection, so this PR's two lines stand as they are.

  Resolved that way, #115's tests and this PR's pass, and so does the full suite (1,087 passed).
- **#174** (`__init__.py`, `analyze.py`, `explore.py`): #174 moves these searches to `search_page(client, "samples", ...)`, and its `get_unique_samples_from_search_result` reads the typed result that returns. Keep this PR's order, with the search first, but make that search #174's `search_page(...)` in both `cross_compare` and `unique_blocks`. Taking this PR's lines as they are fails with `AttributeError: 'dict' object has no attribute 'entries'`. On the index, use #174's `latest_samples = sample_results.entries`, then this PR's three lookup lines. In `sample_by_id`, use #174's `functions = results.entries`, then this PR's two lines. Resolved that way, #174's tests and this PR's pass, and so does the full suite (1,019 passed).
- **#142** and **#160** (`__init__.py`) and **#159** (`data.py`): adjacent import lines. Keep both sides' names.
- The **#182** branch conflicts on the same `data.py` import lines. Keep both names.
- Every other open PR merges cleanly. The full suite passes on the merges with #130, #132, #133, #141, #145, #173, #208 and #210, and with the #183, #190, #192 and #207 branches.
