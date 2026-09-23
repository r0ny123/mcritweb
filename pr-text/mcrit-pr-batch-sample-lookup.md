Title: Add batch lookup endpoints for samples and families

## Summary
Fixes #BATCH.

MCRITweb resolves every sample and family a page names with its own `GET /samples/{id}` or `GET /families/{id}`. Against 1.9.0, a 13-sample cross compare view costs 13 serial round trips. The storage layer can already answer this in one query per collection (`getSampleEntriesByIds`, added for #111 and used by `MatcherInterface`), but the REST API and the client could not reach it.

This adds `POST /samples/ids` and `POST /families/ids`, and `McritClient.getSamplesByIds` and `getFamiliesByIds`.

## What changed
- **Routes**: `POST /samples/ids` and `POST /families/ids`, suffix `by_ids`, in the style of `by_sha256`. Responders are `SampleResource.on_post_by_ids` and `FamilyResource.on_post_by_ids`. They mirror `POST /functions` (`FunctionResource.on_post_collection`):
  - the body is a comma-separated id list;
  - the answer is `{"status": "successful", "data": {"<id>": entry.toDict(), ...}}`;
  - unknown ids are left out, and a duplicate is answered once;
  - an empty or malformed body answers 400.

  Sample ids may be negative, for query samples, resolved as `getSampleById` does. Family ids may not.
- **Storage**: `getFamilyEntriesByIds`, the family counterpart of `getSampleEntriesByIds`:
  - declared in `StorageInterface`;
  - one `$in` query in `MongoDbStorage`;
  - a loop over `getFamily` in `MemoryStorage`.

  Family entries carry no sample lists, as with `GET /families/{id}?with_samples=false`.
- **Index**: `MinHashIndex.getSamplesByIds` and `getFamiliesByIds` sit next to their singular counterparts. They read storage directly, as `getSampleById` does.
- **Client**: `getSamplesByIds` and `getFamiliesByIds` return `{id: SampleEntry}` and `{id: FamilyEntry}`. They honour `raw_responses` and both error modes, like `getFunctionsByIds`, except that an empty list answers `{}` without a request.
- **Tests**:
  - the storage batch reads, on both storages, covering negative ids, unknown ids, an empty list and duplicates;
  - `MinHashIndex`'s delegation;
  - both resources, with a mocked index;
  - the router: the new paths reach the new responders, and `/samples/{id}` and `/samples/sha256/{sha256}` resolve as before;
  - the client, with mocked `requests`: raw mode, both error modes, an empty list, int keys. The new file is `tests/testBatchLookup.py`.

## Why
- **The paths.** `POST /samples` is taken: it adds a sample. `/samples/ids` is a literal segment, which falcon matches before the `{sample_id:int}` field at the same depth; the router test confirms it.
- **The index methods.** Resources reach storage only through the index, so families need an index method like samples do.
- **Return types.** The client methods are typed `Any`, like `getFamily`: in raw mode they return the `requests.Response`, and `ty` rejects a `Dict` annotation for that.
- **Empty lists.** An empty list skips the request, because there is nothing to ask. `getFunctionsByIds` is left as it is.

## Validation
- Without the change, every new test fails except `testGetSampleEntriesByIds`, which covers the existing #111 storage read that the endpoint now exposes.
- Full suite against MongoDB 8.0: 345 passed, 53 subtests (main at 2ac8d7b: 319 passed, 49 subtests). `ruff format --check`, `ruff check` and `ty check` are clean.
- Live, with a server on this branch in front of a 1.9.0 corpus of 66 samples, 16 families and one query sample, read-only:
  - `POST /samples/ids` for ids 0-65, two unknown ids and -1 answered 67 entries, without the unknown ones. Each matched `GET /samples/{id}` field for field.
  - `POST /families/ids` for 0-15 and two unknown ids answered 16. Each matched `GET /families/{id}?with_samples=false`.
  - Median of 5: all 66 samples in one request took 5.2 ms, against 206.9 ms for 66 single requests. All 16 families took 2.6 ms, against 40.1 ms.
  - The batched answers were 3.6% (samples) and 16.7% (families) smaller than the single ones summed, since the envelope comes once.

## Limitations
- MCRITweb's side is a separate change: its per-request lookup helper would send its misses through these. It needs a release with this in it, since it raises MCRITweb's `mcrit` floor.
- The `mcrit client` CLI gets no subcommand; `getFunctionsByIds` has none either.
- The router test checks dispatch through the 400 and 405 paths only. `falcon.testing` validates the WSGI stream, and `req.stream.read()` without a size, as `FunctionResource` calls it, fails that check for any POST with a body. The full parse-and-answer path is covered at the resource level.

## Changelog
A proposed `[Unreleased]` entry. It isn't in the branch, so that this PR and the other open ones don't conflict in the same section:

> ### Added
> - `POST /samples/ids` and `POST /families/ids`, with `McritClient.getSamplesByIds` and `getFamiliesByIds`, answer several entries in one request. All 66 samples of a corpus took 5.2 ms in one request, against 206.9 ms in 66 ([#BATCH]).

## Merge conflicts
- 19 of the 22 open PRs merge cleanly.
- #178, #179 and #183 each touch `McritClient.py` right beside where this adds its two methods; the conflicts are only textual:
  - **#178, #179:** each adds a method after `getSampleById`, where `getSamplesByIds` goes. Keep both methods.
  - **#183:** it rewrites every method's signature and docstring. Keep the two new methods, and take #183's version of `getFamilies` and `getSamples` after them.
