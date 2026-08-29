# Issue #79 — "Improve error message when a binary is not found in DB"

**Not fixed. The root cause looks like it is in `mcrit`, not in this repository.**

## What the issue reports

> The current error message displayed when a binary search fails reads:
> "Ups, search for `<hash>` in MCRIT's samples failed!"
>
> The issue proposes replacing this with more user-friendly alternatives, such as
> "No matches found" or "`<hash>` is not available in DB".

Filed 2022-10-25 by r0ny123, migrated as #79.

## Where that message comes from — measured

`mcritweb/views/explore.py`, in `samples()` and again in `search()`:

```python
results = client.search_samples(query, **pagination.getSearchParams(), limit=pagination.limit)
pagination.read_cursor_from_result(results)
if results is None:
    flash(f"Ups, search for {query} in MCRIT's samples failed!", category="error")
```

It fires on `results is None`, and `None` is what `McritClient` answers when the
**backend call failed** — not when the search succeeded and matched nothing. A search
that matches nothing returns a well-formed result with an empty `search_results`, and
MCRITweb's own bug there is that it then says nothing at all. That half is issue #54,
and it is fixed: https://github.com/r0ny123/mcritweb/pull/5

So the message is not simply mis-worded. On today's code it means what it says.

## Why a sha256 lookup would produce it — inferred, not executed

`mcrit` 1.8.1, `mcrit/index/MinHashIndex.py`, `getSampleSearchResults`:

```python
if re.match("^[a-fA-F0-9]{64}$", search_term) is not None:
    sample_entry = storage.getSampleBySha256(search_term)
    sha_match = sample_entry.toDict()
else:
    sha_match = None
```

There is no `None` check between the lookup and `.toDict()`. `getSampleBySha256`
returns `None` for a sha256 that is not in the collection — so searching for **any**
hash that is not already stored raises `AttributeError` inside the backend, the client
sees an error, `search_samples` answers `None`, and MCRITweb faithfully reports that
the search failed.

That is exactly the symptom #79 describes: you paste a hash to check whether it is
known, it is not, and you get an error rather than "no".

**Tagged inferred.** This is a source read of the installed `mcrit` 1.8.1 in
`.venv/lib/python3.11/site-packages/mcrit/`. There is no MongoDB and no docker daemon
in this environment (see `work/SETUP.md`), so no backend was available to run it
against. Confirm before quoting it upstream — one `curl` against a live mcrit with an
unknown sha256 settles it.

## Why nothing shipped here

Rewording MCRITweb's message would hide a genuine backend error behind "no matches
found", and the next person to hit a real backend failure would be told their search
matched nothing. That is a worse bug than the one being fixed.

The three things that could be done, in order of how defensible they are:

1. **Fix `mcrit`** — a `None` check, three lines, in the repository that owns the
   behaviour. Not reachable from here: the task's guardrails put PRs on
   `r0ny123/mcritweb` only.
2. **Distinguish the two cases in MCRITweb** without a backend change. Not possible
   today: `search_samples` collapses "backend errored" and every other failure into
   `None`. This is exactly what issue #43 ("Handle all kinds of errors coming from
   McritClient") is about, and doing it properly is that issue's job.
3. **Soften the wording anyway.** Cheap, and wrong for the reason above.

## Suggested comment for the issue, if someone wants to post one

> The message is not mis-worded — it fires on `results is None`, which is a failed
> backend call rather than an empty result. The empty-result case said nothing at all,
> which was #54.
>
> A sha256 lookup for a hash that is not in the collection looks like it hits an
> unchecked `None` in `mcrit`'s `MinHashIndex.getSampleSearchResults` (`sha_match =
> sample_entry.toDict()` with no guard), which would make an ordinary "not in the DB"
> query an error on the backend. Not verified against a live instance — worth
> confirming before moving this issue to `mcrit`.
