Title: Fetch submit form family names as they are typed

## Summary

Part of #192: bounds the submit form's family lookup. The job-queue half needs a backend change in mcrit (below), so #192 stays open.

`/data/submit` no longer downloads the whole family table on every load. Its family field now uses the same fetch-as-you-type type-ahead as the listing pages. The sample-row queue reads on `/explore/samples` and `/explore/families/<id>` are left as they are.

## What changed

- `templates/table/submit_or_query_dropzone.html`: the inline `new Autocomplete(... families|autocomplete_items ...)` block is replaced by `{% include 'js/ac_family_names.html' %}`, and the macro's `families` parameter is gone.
- `templates/js/ac_family_names.html`: also attaches to `#family`, and marks each field it has attached to (`data-family-autocomplete`). A listing page now runs the partial twice (once for its edit modals, once for the drop overlay), and without the mark the modal fields would get a second widget.
- `views/data.py` (`submit` GET): no more `getFamilies()`.
- `views/analyze.py`, `submit.html`, `query.html`, `base.html`: the `families=` arguments are dropped, along with the overlay's `TODO: get families... dynamically?`.
- `mcritweb/__init__.py`: the `|autocomplete_items` Jinja filter is removed. No template uses it any more, and keeping it around would invite embedding names again.
  - `mcritweb.autocomplete.autocomplete_items` stays; `explore.family_names` is its one caller and the only way names reach the widget.
  - AGENTS.md, `autocomplete.py` and the `family_names` docstring now say so.
- `views/explore.py`: two sentences on `sample_row_job_collection` saying why its queue reads have no `limit`. No code change there.
- Tests:
  - `testExplorePageCalls.py`:
    - `/data/submit` and `/analyze/query` make no `getFamilies` call and wire `#family` to `explore.family_names`;
    - `/explore/samples` includes the partial twice (listing and overlay), with the attach-once guard present.
  - `testAutocompleteEscaping.py`:
    - no type-ahead page embeds family names;
    - the ratchet accepts an empty `data: []`/`setData([])` anywhere. The only other expression it accepts is `data.suggestions || []`, and only in the fetching partial.
      - The exemption is per expression, not per file: every production call site now goes through that partial, and a whole-file exemption would leave the offline ratchet checking none of them.
      - The allowed expression also counts only while `data.suggestions` is named nowhere else in the file, so an in-place rewrite before `setData` fails too.
      - New bypass cases: re-embedded names; "the partial post-processes the endpoint's items"; the partial rewriting them in place.
    - `testJavascriptScoping.py` and `routePolicy.py`: comments updated for the removed `families_ac` and the endpoint's new users.
    - a new browser case types into the overlay's `#family` on `/explore/samples`, gets suggestions, and finds exactly one widget per family field.
  - `testScriptEscaping.py`: the `family_names` endpoint test now also runs a `'`/`"` attribute-breaking name, and asserts no quote or angle bracket survives in label or value.

## Why

**Submit form.** mcrit answers `getFamilies()` with one storage lookup per family, so the form cost more the bigger the corpus got. #77 moved the listing pages to `explore.family_names`. Moving the submit form to the same partial keeps its behaviour:
- picking an existing family still works;
- a name that doesn't exist yet is still accepted as free text;
- the pre-fill from the dropped file's header still works, because `fill_form` sets `#family` with `.val()`, which is independent of the widget.

**Queue reads: why they stay unbounded.**
- The badge counts *all* of a sample's matching jobs, and "Last 1:N Job" is the newest finished `getMatchesForSample` job.
- mcrit 1.9.0's `GET /jobs` (client `getQueueData` → `JobResource.on_get_collection` → `QueueRemoteCalls.getQueueData` → `MongoQueue.get_jobs`) supports these selectors, none of which can pick out a page's 25 sample ids:
  - `method`: a mongo query on the indexed `payload.method`;
  - `state`: filtered in python over the whole method;
  - `start`/`limit`/`ascending`;
  - `filter`: one substring, tested in python against `Job.parameters` after `get_jobs` has already paged.

Options considered and turned down:
- **A plain `limit` (newest N per method):** it undercounts the badge and blanks the link for every sample whose jobs are older than the window, and nothing on the page says so. `test_a_sample_search_makes_these_backend_calls_and_no_others` already pins the absence of a limit.
- **A newest-N window with a "k+" badge when the window is full:** it would be honest about the truncation, but it is a visible loss of information. An older sample would show "3+" where it shows "7" today, and could still lose its "Last 1:N Job" link, for the sake of a transfer the backend could avoid outright.
- **One `filter` request per sample:** up to 50 requests per page, each scanning the whole method on the server, instead of 2.
- **A per-request cache:** it saves nothing, because each view reads the queue once.
- **A short-TTL cache:** it shows stale badges and links right after a job is queued or finishes, which is exactly when people look.

**The backend change.** Add a `sample_ids` selector to `/jobs`, e.g. `GET /jobs?method=getMatchesForSample&sample_ids=7,8,9`. `MongoQueue.get_jobs` would apply it as an anchored regex on the already-indexed `payload.descriptor`: `^\["getMatchesForSample", \{"0": (7|8|9)[,}]`. The descriptor is `[method, params, file_params]` with the first argument at a fixed position. With that, `sample_row_job_collection` passes the page's ids and keeps `filterToSampleIds` as the exact check.

The full proposal is written up as a ready-to-file mcrit issue. **It still needs filing** against danielplohmann/mcrit; this PR does not file it.

## Validation

- Full suite: 980 passed, 18 skipped. `ruff check .` is clean. The playwright browser tests ran against the installed chromium, including the new overlay case.
- I broke the partial on purpose in two ways, both HTML-decoding the labels through a `<textarea>` before `setData`: once into a new array, once in place. Each makes `test_every_type_ahead_gets_its_names_from_the_escaping_endpoint` fail offline, without playwright.
- With master's `mcritweb/` and this branch's tests, six tests fail. With this branch's code, they pass:
  - `test_the_submit_form_asks_for_family_names_as_they_are_typed[/data/submit]` and `[/analyze/query]`;
  - `test_the_drop_overlay_brings_its_own_family_type_ahead`;
  - `test_no_type_ahead_page_embeds_the_family_names[/data/submit]`;
  - `test_every_type_ahead_gets_its_names_from_the_escaping_endpoint`, because master's dropzone still embeds names;
  - `test_the_drop_overlay_suggests_without_doubling_the_modal_widgets`.

  The new attribute-payload endpoint case passes on both, since the endpoint is unchanged. It is added coverage.
- Live, against the mcrit 1.9.0 backend (13 samples, 3 families), with every backend request logged from inside the flask process. Numbers are warm page loads, master → this branch:

| page | backend calls | backend bytes | page bytes |
|---|---|---|---|
| `/explore/samples` | 4 → 4 | 19,286 → 19,286 | 64,858 → 67,407 |
| `/explore/families/1` | 5 → 5 | 13,441 → 13,441 | |
| `/data/submit` | 2 → 1 (`GET /families` gone) | 548 → 65 | 15,488 → 17,630 |
| `/` | | | 24,875 → 27,100 |

  - The `GET /families` call removed from `/data/submit` was 483 bytes here, and it grows with the corpus. Typing now costs one `search/families?query=cor&...&limit=10`, 237 bytes.
  - Job badges and "Last 1:N Job" links for every row of `/explore/samples` (samples 0–12) and `/explore/families/1` (7–10) are identical to master.
- In Chromium, on `/data/submit`:
  - typing `cor` sends one `familyNames?q=cor` request and suggests `coreutils`, and selecting it fills the field;
  - `brandnewfamily` stays as typed;
  - dropping a `.smda` file pre-fills family `coreutils`, version `9.1` and ticks SMDA.

  In the drop overlay on `/explore/samples`, "Add to database" → `cor` suggests and selects `coreutils`, and the edit-sample field still carries one widget. Writing routes were blocked in the browser, and only GETs reached the backend. No page errors, no 500s.

## Limitations

- The queue reads on the samples and family pages are unchanged until mcrit gets the `sample_ids` selector, and that issue still has to be filed.
- Suggestions now come from mcrit's search parser rather than from a client-side substring match over every name. The listing pages have behaved this way since #77. Concretely:
  - there is no diacritic folding when choosing the candidates;
  - a leading `-x` negates;
  - `OR` and `field:` syntax apply.

  The widget still shows at most 5 items.
- Pages are about 2.2 kB larger (index), or 2.5 kB on listing pages that also carry an edit modal (+2,142 B on `/data/submit` with this 3-family corpus). The shared partial's script now rides along with the drop overlay on every page. On `/data/submit` it replaces the embedded list, which grew with the corpus.

## Merge conflicts
- **#126** (`base.html`, `js/ac_family_names.html`, `table/submit_or_query_dropzone.html`): #126 defers Bootstrap and so builds the family type-ahead on `DOMContentLoaded`; it also adds a `lazy` flag to the dropzone macro. This PR drops the macro's `families` argument and attaches the shared type-ahead to the dropzone's family field. On merge:
  - keep #126's `DOMContentLoaded` wrapper and call this PR's `attachFamilyAutocomplete(document.getElementById('family'))` inside it;
  - keep #126's `lazy` and drop `families` from the macro and from the call in `base.html`.
- **#130** (`data.submit`): #130 wraps the `getFamilies()` call this PR removes. Take this PR's side.
- Every other open PR merges cleanly.
