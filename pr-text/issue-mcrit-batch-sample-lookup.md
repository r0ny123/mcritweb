Title: Expose a batch sample lookup (POST /samples by ids / McritClient.getSamplesByIds)

MCRITweb renders pages that name many samples: cross-compare results, job overviews, the jobs table, and a sample's job list. It has to resolve each sample with its own `GET /samples/{id}`. Against mcrit 1.9.0, a 13-sample cross result costs 13 serial round trips per view. Families have the same problem via `GET /families/{id}`.

The storage layer already solves this. `StorageInterface.getSampleEntriesByIds` does one `$in` per collection in `MongoDbStorage` (added for #111), and `MatcherInterface` uses it. Only the REST API and the client are missing it.

Proposal, mirroring `getFunctionsByIds` / `POST /functions`:
- `POST /samples` (or `/samples/ids`) takes a comma-separated id body and returns `{sample_id: SampleEntry dict}`. Ids that aren't found are left out. Negative ids resolve from `query_samples`, as `getSampleById` already does.
- `McritClient.getSamplesByIds(sample_ids) -> Dict[int, SampleEntry]`.
- Optionally, the same for families: `getFamiliesByIds`, with `with_samples=False`.

MCRITweb routes these lookups through one per-request helper (familiary/mcritweb#191), so adopting it there is a one-function change.
