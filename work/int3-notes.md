# int3 — integration rebuild across 68 branches

Worktree: `scratchpad/fx/int3`, detached at `origin/master` (df53db9).
Order: `scratchpad/merge_order_v3.txt` (68 branches).
Baseline on master: `ruff check .` clean; suite `4 failed, 235 passed`
(the 4 known Windows failures: testSecretKey key-permissions + 3 in testUserFilters).

## Conflict log

### #5 fix/101-do-not-confirm-which-accounts-exist — 1 hunk
`mcritweb/views/authentication.py` login success path. Ours (#3 timezone-aware)
had `user_info.last_login = utc_now()`; theirs added password rehash +
`db.clear_login_failures(...)` but still wrote `datetime.utcnow()`.
Resolved: keep `utc_now()` (the tz-aware helper #3 introduced; `datetime` is no
longer imported in this module) and take all three of theirs' new statements.
Taking either side alone would have dropped a fix.

### #6 fix/100-apitoken-generation-and-rotation — 4 hunks
- `mcritweb/db.py` imports: ours (#101) added `import time` (the login throttle
  uses `time.time()`); theirs *removed* `import uuid` because `generate_apitoken`
  no longer needs it. Kept `import time`, dropped `import uuid` — taking "ours"
  wholesale would have left an unused import ruff flags.
- `mcritweb/db.py` module constants: disjoint additions (#98's `utc_now`/
  timestamp helpers vs #100's `APITOKEN_BYTES`/`generate_apitoken`) — union.
- `authentication.py` import line: same-module import, unioned the names.
- `authentication.py` module constants: disjoint (#101 messages vs #100
  `API_ROLES`) — union.

### INTEGRATION DEFECT 1 — duplicate test name, no conflict (class 2)
`tests/testResultPages.py:138` and `:248`. #1 (`fix/linkhunt-500-on-incompatible-job`)
and #2 (`fix/73-empty-result-vs-unknown-job`) each added a
`test_a_terminated_job_says_it_was_terminated`, in different regions of the file,
so the merge was clean. The second definition shadows the first, so #1's
assertion (`b"terminated before it could finish"` reached via the `one_job`
fixture) silently stopped running. Caught by `ruff` F811 only because I ran it
after merge #2 — the suite stayed green.
Resolved: renamed #73's copy to
`test_a_terminated_job_is_not_reported_as_an_unknown_one`, matching its
neighbour `test_a_failed_job_is_not_reported_as_an_unknown_one` and its actual
assertion (`b"was not found in the system" not in ...`). Both tests now run.

### #7 fix/78-deduplicate-search-results — 1 hunk
`tests/testSearchPages.py`: #4's "nothing matched" tests and #7's dedup tests
were appended at the same point. Disjoint names (`safe_union` confirmed no
shared `def`/`class`), so union.

### #9 fix/79-say-what-a-failed-search-means — 4 hunks
`mcritweb/views/explore.py`, the three per-category search failure branches in
`search()`.
- hunk 0: disjoint module-level additions (#54's `SEARCHABLE_TYPES` vs #79's
  `SHA256_PATTERN` + `flash_search_failed`/`flash_sample_search_failed`) — union.
- hunks 1-3: both sides edit the *same* two statements. Ours (#54) added
  `search_failed.add("<cat>")` — which is what stops a failed category being
  reported as "Nothing matched" — next to the old flash string; theirs (#79)
  replaced the flash string with the new helper. Taking either side alone loses
  a fix: "ours" keeps the bad wording, "theirs" drops the `search_failed`
  bookkeeping and the page would then claim nothing matched after a backend
  error. Hand-resolved to `search_failed.add(cat)` followed by the #79 helper
  call, in each of the three branches (now explore.py:467, :489, :515).

### #10 fix/89-cache-the-backend-probe — 1 hunk
`mcritweb/__init__.py` `app.config.from_mapping(...)`: two unrelated new config
keys (`TRUSTED_PROXY_COUNT` from #101's throttle, `MCRIT_SERVER_PROBE_TTL` from
#89) landing on the same line. Union.

### INTEGRATION DEFECT 2 — #54's tests pinned wording #79 replaced (no conflict)
`tests/testSearchPages.py:215` and `:249` asserted `"failed!"`, the old flash
string. #9 (`fix/79-say-what-a-failed-search-means`) deliberately rewrote that
message to "Could not search MCRIT's <collection>... - the backend did not
answer.", and its own tests (`tests/testSearchFailures.py`) assert
`"the backend did not answer"`. The two test files never conflicted, so this only
showed up when the suite ran.
Resolved by retargeting #54's two assertions (and the stale docstring quote) at
`"the backend did not answer"` — the same phrase #79's own tests use. The intent
of #54's tests is untouched: a failure is still reported, and "Nothing matched"
still must/must not appear. Not a weakening: the assertion is on the message
that actually exists now.

### #11 fix/51-job-search — 1 hunk
`mcritweb/__init__.py`: same-module `from .views.utility import ...`, ours the
one-line form with #89's `forget_server_probe`, theirs the parenthesised form
with #51's `describable_jobs`/`job_is_describable`. Unioned the names into
theirs' parenthesised form (all three call sites verified present).

### #13 fix/41-wrap-long-job-names — 1 hunk
`mcritweb/templates/table/job_row.html`: adjacent `<td>`s. Ours (#52) added
`class="buttons"` to the actions cell; theirs (#41) added `job-description` to
the job cell. Both classes are real rules in `static/style.css` (`td.job-description`
at :192, `td.buttons` at :266), so either side alone silently drops a stylesheet
rule with no test to notice. Kept both.

### #15 fix/65-empty-table-messages — 2 hunks (both structural)
- `mcritweb/views/data.py` `jobs()`: #11 restructured the paging into
  `if query: ... else: ...` with a `limit_param` variable; #65 changed only the
  `else`-branch `max_count` to `sum(statistics.get(active_category, {}).values())`
  so an unknown `?active=` sizes the page at zero instead of raising KeyError.
  Ours' structure kept, #65's guarded expression and its comment grafted into
  the inner `else` (data.py:872-879). Taking "theirs" would have reverted #11's
  job search entirely; taking "ours" would have kept the KeyError.
- `mcritweb/templates/jobs.html`: #11 wrapped the table in
  `{% if query and not jobs %}`; #65 replaced the `job_table(...)` call with a
  per-category empty-state map and `empty_message`/`empty_link` kwargs. Both
  ended at the same `{% endif %}`, which is why they collided. Nested #65's
  `{% set %}` block and kwargs inside #11's `{% else %}` branch, and kept #11's
  `order_toggle=`/`order_ascending=` kwargs on the call — #65 was written against
  master and its `job_table(...)` line does not carry them, so a naive "take
  theirs" would silently drop the sort-order feature with no failing test.

### #17 fix/job-overview-500-on-deleted-dependency — 2 hunks
- `mcritweb/views/data.py` `job_overview()`: ours (#51) had replaced the raw
  `for job in child_jobs` loops with `describable_jobs(child_jobs)`; theirs added
  `missing_children` and passed it to the template. Kept ours' loops and appended
  `missing_children=missing_children` to the `render_template` call (data.py:964);
  `job_overview.html:25-28` reads it, so dropping it would have rendered nothing
  where the "N sub-jobs are no longer in the system" notice belongs.
  Theirs' `if child_jobs:` guard is subsumed — iterating an empty list is a no-op.
- `tests/testResultPages.py`: ours inserted #73/#1's block of tests immediately
  above `test_job_page_renders_for_a_finished_job`, whose signature theirs
  rewrote into a `@pytest.mark.parametrize` over five reports. Kept ours' new
  tests and theirs' parametrised signature (the shared body already reads
  `report`).

### #19 fix/jobs-500-on-unknown-category — 2 hunks
- hunk 0: ours had #51's `UNREADABLE_PAYLOAD_REASON` + `@bp.route('/jobs')`;
  theirs added `JOB_CATEGORIES`/`known_job_category` + `@bp.route('/jobs',
  methods=('GET','POST'))`. Kept both bodies and **ours' route line**: #51
  (commit 8cd24d9) deliberately made `/jobs` GET-only, because the search box is
  now a GET and the old POST branch raised `BadRequestKeyError` for any POST
  without the field. Taking theirs' route line would have re-added a POST method
  with no handler behind it and re-opened that 400.
- hunk 1: **duplicate fix (class 2)** — #65 and #19 independently rewrote the
  same `max_count` line with the same `statistics.get(active_category, {})`
  guard. Took ours (#65's, already in tree), which also carries #51's
  `limit_param=`. No behavioural difference; theirs' `if active_category else 0`
  is dead in that branch.

### INTEGRATION DEFECT 3 — #19's category allowlist does not know #51's/#65's categories
`mcritweb/views/data.py:770` (`JOB_CATEGORIES`). #19 builds the fallback
allowlist from `Job(None, None).method_types["all"]` plus two hand-added
maintenance methods. But #51 appends a `getMatchesForSampleVsGroup` tab to the
menu, and #65 gives both `getMatchesForSampleVsGroup` and `doDbCleanup` an
empty-state sentence in `jobs.html` — neither is in `method_types["all"]`.
Merged, `/data/jobs?active=getMatchesForSampleVsGroup` on a backend that is not
currently reporting those jobs (an old bookmark, or after the page's own
per-category delete — precisely the case #19 exists for) flashes
`"getMatchesForSampleVsGroup" is not a job type.` and falls back to another tab.
No conflict, no failing test: #19's own tests use a fake that reports every
method, so `category in statistics` short-circuits the allowlist.
Resolved: added both names to `JOB_CATEGORIES` with a comment, and added
`tests/testJobCategories.py::test_every_category_with_an_empty_state_is_also_a_known_category`,
which asserts every key of jobs.html's empty-state map (itself enumerated from
`mcrit.Worker.Worker` by #65's test) is a known category. Verified the new test
fails when the two names are removed again.

### #20 fix/56-listing-pages-drop-id-matches — 8 hunks across 5 files
- `templates/families.html`, `functions.html`, `samples.html`: same macro call,
  ours (#65) added `empty_message=`, theirs added `exact_matches=`. Merged the
  kwargs.
- `templates/search.html` x3: same, with #54's "No more X match ... on this page."
  wording preserved and `exact_matches=<kind>_exact_matches` spliced in.
- `mcritweb/views/explore.py` x4 (the `family` and `function` branches of
  `search()`): ours was #78's dedup-by-id; theirs is #56's `by_id` +
  `exact_matches_to_prepend` + `exact_match_marks`. Took **theirs**, because it
  subsumes #78 rather than reverting it: `by_id[...] = ` for the exact hit then
  `by_id.setdefault(...)` for the text hits is the same deduplication with the
  same "id match keeps its place at the top" ordering, plus the first-page-only
  rule #78 did not have. Verified `tests/testSearchPages.py`'s #78 tests still
  pass after this.

### #21 fix/53-table-row-kwargs — 21 hunks across 7 files
### INTEGRATION DEFECT 4 — #53 and #56 both mark the exact hit (class 2)
#53 adds a generic `row_decorations` channel (`templates/table/row_decoration.html`:
tints + a badge column) and uses it to badge the search page's exact hit
(`ID_MATCH_DECORATION` / `SHA_MATCH_DECORATION`, `<span class="badge bg-success">ID
match</span>`). #56 (merged at #20) adds an `exact_matches` channel
(`links.html:65-75`, a "Match" column, `<span class="badge bg-primary" title="Exact
match on this record's ID">ID</span>`). Both render on the same rows of the same
tables. Merged naively the search page grows **two adjacent badge columns saying the
same thing**.
Resolved: one mechanism per job.
- The row macros (`family_row.html`, `function_row.html`, `sample_row.html`) now take
  **both** kwargs and render both, because they are not the same job: `row_tint` is
  what `cross_compare.html:176` needs (#53's other, unduplicated use) and
  `badge_column_*` renders nothing unless a caller passes badges.
- `explore.search` keeps #56's `exact_matches` and drops #53's decoration badges.
  #56 is strictly broader: three listing pages as well as search, ID vs SHA-256
  distinguished, and first-page-only via `exact_matches_to_prepend`.
- `analyze.cross_compare` keeps `row_decorations` (tints only), so #53's mechanism
  is still live and still tested.

### INTEGRATION DEFECT 5 — stray tail line dragged in by the merge (class 3)
`mcritweb/views/explore.py` (samples branch of `search()`): git matched theirs'
trailing `sample_decorations[sample_entry.sample_id] = ID_MATCH_DECORATION` onto
ours' `exact_matches_to_prepend` loop *outside* the conflict region, so it survived
silently. With #53's constants gone it is a `NameError` on any sample search with an
exact hit, and semantically wrong even with them: it labels a SHA-256 hit "ID match".
Removed, along with the three now-unused `*_decorations = {}` initialisers.
No test covered it — `ruff` does not see a module-global NameError.

Other hunks in #21: `cross_compare.html` import (union, unrelated imports);
`search.html` x3 (took ours — #56's `exact_matches=` plus #54's `empty_message=`);
`job_row.html` `job_header` (kept ours' `order_toggle`/`order_ascending` signature
from #52/#58 plus theirs' kwargs-swallow lines).
Test fallout: #53's `test_the_search_page_badges_an_id_match` /
`..._a_sha256_match` asserted its own markup on the search page. Replaced by
`test_the_search_page_marks_an_exact_hit_exactly_once`, which asserts #56's mark is
present *and* that #53's `bg-success` badge is not also rendered — i.e. it now pins
the anti-duplication invariant rather than one branch's markup.

### #22 fix/63-page-specific-libraries — 1 hunk
`mcritweb/templates/jobs.html`: #51 and #63 each replaced the removed DataTables
initialiser with their own explanatory comment. Unioning would have left two
comments about one absence (class 5). Merged into one, keeping #63's account of
why the selector never matched and what was removed, plus #51's point about why
reviving it would be wrong.

### #23 fix/75-download-raw-result — 2 hunks
`tests/testResultPages.py` imports only: `import copy` (ours) vs `import json`
(theirs), and `from fixtureData import job_id_of` vs `... job_id_of, load`.
Both kept / names unioned.

### #24 fix/32-show-band-setting — 2 hunks
`mcritweb/__init__.py`: theirs added a `from .views.params import
get_minhash_matching_label` line next to the `.views.utility` import (which ours
had already grown), and a `@app.template_global()` next to ours'
`app.add_template_global(job_is_describable)`. Both disjoint — kept both.

### FIX (not an integration defect, but in scope) — cached result written in text mode
`mcritweb/views/data.py` `cache_result` (line ~78). #23 (`fix/75-download-raw-result`)
serves a cached report by streaming the file and a cache miss by `json.dumps` in
memory, and asserts the two answer identical bytes. `cache_result` opens the file
with `"w"`, so on Windows the on-disk copy has CRLF and the in-memory one LF, and
`test_raw_result_download_prefers_the_cache_over_a_second_fetch` fails. Added
`newline="\n"`. (Pre-existing on that branch on Windows rather than caused by the
merge; the task's success criterion is the 4 known failures, so it is fixed here.)
Watch: #42 `fix/68-result-page-performance` rewrites this call into
`write_atomically(..., "w")` — the same fix has to survive that merge.

### #25 fix/99-result-template-coverage — 1 hunk
`mcritweb/templates/result_compare_function.html`: ours (#39) rewrote the h1 to
`{{ job_info.method|job_name }}`; theirs (#99) deleted the following
`<p>Showing matches against family: {{ ...getFamilyNameByFamilyId(famid) }}</p>`
because `famid` is never passed to this template and the line is wrong for a
per-function view anyway. Kept ours' h1 and theirs' deletion.

### INTEGRATION DEFECT 6 — #99's template-coverage ratchet caught three cross-branch drifts
`tests/testResultTemplateCoverage.py` (from #25) is a ratchet written against master;
three other branches had already changed what it measures. All three failures were the
ratchet doing its job, so the tree/table was corrected rather than the test weakened.
1. `/data/linkhunt/ffffffffffffffffffffffff` used to fall through to
   `result_incompatible.html`; #1 (`fix/linkhunt-500-on-incompatible-job`) and #2
   (`fix/73-...`) made an unknown job id answer `result_invalid.html` ("was not found
   in the system"), which is right. Retargeted that row and added
   `/data/linkhunt/{cross_compare}` so `result_incompatible.html` keeps a URL — a job
   that exists but carries no MatchingResult is what "incompatible" now means.
2. `job_failed.html` is new (added by the linkhunt job-state work) and had neither a
   URL nor a stated reason, so the ratchet failed. The corpus holds only finished
   jobs, so it got an `UNCOVERED` entry naming the reason, in the style of
   `job_in_progress.html`'s.
3. `test_a_cross_compare_with_a_bad_custom_order_names_the_job` asserted the "Delete
   job data" link as a **visitor**; #11 (`fix/51-job-search`, commit ccd2ce7) gated
   that button on contributor/admin, because `delete_job_by_id` is
   `contributor_required` and an ungated button just buys a visitor a 403. Changed the
   test's role to contributor — the assertion (the link names the right job id) is
   unchanged and is what the test is actually about.

### #26 fix/43-backend-transport-errors — 4 hunks
- `views/administration.py`, `views/data.py`: theirs adds
  `from mcritweb.backend_errors import require_result` above a `mcritweb.db` import
  whose name list ours had already grown (#100's `generate_apitoken`, #98's
  `utc_now`). Kept both lines with ours' name list.
- `views/explore.py`: theirs adds `import requests`; ours' flask import line carries
  `current_app` (from #89). Kept both.
- `views/utility.py` `mcrit_server_required`: ours (#89) calls the caching
  `probe_server(probe, ttl, server_url)`; theirs (#43) inserts an
  `if backend_errors.wants_a_status_code(): return Response(status=502)` before the
  flash+redirect. Combined. Checked that the combination is sound:
  `probe_server` re-raises `requests.RequestException` rather than swallowing it
  (utility.py:236-238), so #43's `except Exception` still sees a transport failure
  through #89's cache, and a *cached* failure is replayed by re-raising too.

### INTEGRATION DEFECT 7 — #43's "still broken" marker was half-closed by #51
`tests/testBackendNoResult.py::test_the_listing_pages_are_left_to_the_branch_that_rewrites_them`
asserts that `/explore/samples` *raises* when `getFamilies` or `getQueueData` answers
None, deferring the fix to #77. #11 (`fix/51-job-search`) closed the `getQueueData`
half without touching this file: `explore.samples` now calls
`JobCollection(describable_jobs(jobs))`, and `describable_jobs` iterates `jobs or []`
(`views/utility.py:117`). So the marker asserted the opposite of the merged
behaviour. No conflict; only the suite saw it.
Resolved by splitting: the marker keeps the `getFamilies` case (genuinely still open
until #77 lands, later in this order), and the `getQueueData` case became
`test_the_sample_listing_already_survives_a_queue_it_cannot_read`, a positive
assertion naming why. Not a weakening — the old assertion was factually wrong.

### #27 fix/58-remember-sort-order — 4 hunks
- `mcritweb/views/explore.py` x3: ours had `exact_matches = {}` (#56) immediately
  above the `CursorPagination(...)` line theirs extended with `sort_memory=`.
  Kept both.
- `docs/manual/README.md`: #56's paragraph about the `Match` column and #58's about
  remembered sort order landed at the same spot. Union — but with a blank line
  between them, which the raw union did not leave: Markdown would otherwise have
  run the two paragraphs together in the rendered `/help` page.

### #28 fix/36-job-tab-in-the-url — 4 hunks
- hunk 0: ours had dropped `from datetime import datetime` (#98 replaced it with
  `utc_now`); theirs added `from urllib.parse import urlencode`. Resolved to the
  urlencode import alone.
- hunk 1: **third independent fix of the same thing (class 2)**. #36 adds
  `MENU_ONLY_CATEGORIES` + a `known_categories` set; #19 already added
  `JOB_CATEGORIES` + `known_job_category`, and #65 the `.get()` guard. Kept #19's,
  which is strictly broader (defers to the backend's statistics, flashes rather than
  silently resetting) and dropped #36's duplicate. Kept ours' `@bp.route('/jobs')`
  again, for the same reason as at #19.
- hunk 2 / 3: kept ours (#19's guard-with-flash; #65's `.get()` plus #51's
  `limit_param`).
- #36's real contribution — the canonicalising redirect to `?active=<derived>` — sits
  in a region that merged cleanly and is kept intact.

### INTEGRATION DEFECT 8 — a second stray tail line (class 3)
`mcritweb/views/data.py` `jobs()`: the line
`known_categories = set(job_template.method_types["all"]) | MENU_ONLY_CATEGORIES | set(statistics)`
and its four-line comment merged *outside* the conflict region, so they survived
after I dropped `MENU_ONLY_CATEGORIES` — an immediate `NameError` on every request to
`/data/jobs`, and the variable is unused anyway now that #19's guard is the one in
force. Removed.

### INTEGRATION DEFECT 9 — #36's redirect breaks 26 tests written against the old URL
Once `/data/jobs` answers 302 to the URL that names its tab, every other branch's
tests that fetch `/data/jobs` (or `/data/jobs?Search=...`, `?state=...`) without
`follow_redirects` see the redirect body instead of the page. 26 failures across
testJobSearch, testJobSort, testJobCategories, testEmptyTableMessages,
testJobDescriptionWrapping, testJobNames, testPageAssets, testJobList.
The redirect is #36's whole point and its own tests use `follow_redirects=True`, so
the tests were brought to it: `follow_redirects=True` added to the jobs-**list** GETs
(never `/data/jobs/<id>`). Two needed more than that:
- `testJobSearch.py::test_no_search_term_means_no_filter` counts `getQueueData`
  calls; the redirect returns before that call, so following it restores the single
  call the test expects rather than doubling it. Checked the ordering in `jobs()`.
- `testJobList.py::test_an_invented_category_falls_back_instead_of_failing` asserted
  the invented value appears nowhere. #19 now flashes `"no-such-category" is not a
  job type.` deliberately. Retargeted: the page still must not render it as a tab or
  in a link (`active=no-such-category` absent), and the flash must carry it escaped
  (`&#34;no-such-category&#34;`) — which also pins that the echo is autoescaped.

### #29 fix/55-rerun-job — 5 hunks
### INTEGRATION DEFECT 10 — one table, renamed by one branch and extended by another
`mcritweb/views/params.py`. #24 (`fix/32-show-band-setting`) added
`BAND_RANGE_LABELS` and `BAND_VALUE_TO_LABEL` derived from master's
`BAND_RANGE_ARG_TO_VALUE`; #29 (`fix/55-rerun-job`) *renamed* that dict to
`BAND_RANGE_BY_SLIDER_POSITION` and added `slider_position_for_band_range` reading it
the other way. Two names for one table, or a `NameError`, depending on which side is
taken.
Resolved to one table under #55's name (it says what the key is), with a merged
comment naming all three readers, `BAND_VALUE_TO_LABEL` rebased onto it,
`parse_band_range` using #55's local alias, and `tests/testMinhashParameter.py`'s
two references renamed. `slider_position_for_band_range` and `BAND_VALUE_TO_LABEL`
now both derive from the same literal, which is what stops the two directions
drifting.
Also `views/data.py`: a comment reworded by both (took #55's, which reads correctly
in its new position) and `job_overview`'s `render_template`, where ours had #51's
`describable_jobs` loops and #17's `missing_children` and theirs adds `can_rerun=`
and `configuration_url=`. All four kept.

### #30 fix/40-query-result-identity — 7 hunks
Two branches each add a new SQLite table (#101 `login_attempt`, #40 `query_upload`),
so every place the schema is listed collided:
- `README.md`: two `* unreleased:` entries — union, both kept as separate bullets.
- `mcritweb/db.py` `init_db()`: the conflict covered only the `with open_resource(...)`
  header line; the shared `db.executescript(...)` body sits *below* it, so a plain
  union would have produced two `with` headers over one body — a silent loss of one
  table on a fresh install, and valid Python. Written out as two full blocks instead.
- `mcritweb/db.py` `migrate()`: two independent guarded CREATEs — union.
- `views/analyze.py`, `views/data.py` imports — union; data.py needed a follow-up
  because both sides imported different names from `mcritweb.db` on separate lines,
  which ruff's I001 caught (`utc_now` + `get_query_filename` folded into one line).
- `tests/testMigrations.py`: the "all tables exist" set — merged both names into one
  set literal; the two new test functions — `safe_union` (disjoint names).
Checked for the `SCHEMA_V1_4_8`-defined-twice hazard: only one definition
(`tests/testMigrations.py:115`).

### #32 fix/45-mark-the-search-term — 16 hunks across 11 files
Mechanically the same shape throughout: #45 threads a `highlight_terms` kwarg from
each listing template through `_table_base` into the row macros, and every one of
those call sites and signatures had already grown `exact_matches` (#56),
`row_decorations` (#53) and `empty_message` (#65).
- 8 template call sites (`families/functions/samples/single_family/single_sample/
  search.html`): spliced `highlight_terms=query|search_terms` in after
  `column_setup=`, keeping ours' kwargs and line layout.
- `table/{family,function,sample}_row.html`: `mark` added to the existing
  `links.html` import (ours already carried #56's `exact_match_*`), and
  `highlight_terms=None` appended to each row macro signature after
  `exact_matches=None, row_decorations=None`.
- `table/table.html`: ours had #65's `empty_state` block ending at the
  `_table_base` signature theirs rewrote. Kept the block and theirs' signature.
- `mcritweb/__init__.py`: two disjoint import lines and two disjoint template-global
  registrations — union.

### #35 fix/35-analyze-a-single-function — 3 hunks
### INTEGRATION DEFECT 11 — two fakes for one backend method, and a lost sibling
`tests/fixtureData.py`: #34 (`fix/34-function-page-api-usage`) and #35 each added a
`CorpusMcritClient.getMatchesForPicHash`. #34's answers a **list** of triples when
`summary=False`; #35's answers a **set**. The real `McritClient` returns JSON, i.e. a
list, and `fix/fake-status-fidelity` (#33) is in this same set of branches precisely
because fake fidelity matters, so #34's is the faithful one and was kept — it also
brings `getMatchesForPicBlockHash`, which #35 has no equivalent of.
Taking "ours" wholesale then dropped `requestMatchesForSample` and its
`# --- job submission ---` header, which sat inside the *same* conflict hunk on
theirs' side purely because it was adjacent. That is not a duplicate of anything and
`analyze.compare_function` calls it, so all five `testFunctionAnalysis` tests raised
`NotImplementedError`. Re-added verbatim below `getMatchesForPicBlockHash`.
Also: `MATCHED_SAMPLE_ID` (theirs) kept next to `altered_job`/`inject_job` (ours);
`table/function_row.html` — #35 replaces the row's 1-vs-N button with a per-function
one guarded on `function_id >= 0`, #52 had added `class="buttons"` to the enclosing
`<td>`. Took #35's block with #52's class on the `<td>`.

### #36 fix/9-promote-a-query-to-a-sample — 4 hunks
- `AGENTS.md`: ours held two bullets (the `TRUSTED_PROXY_COUNT` one from #101 and the
  old "Uploads land in instance/temp/uploads/ named by SHA-256" one); theirs is a
  rewrite of the uploads bullet that restates both ceilings verbatim and adds the
  job-id naming rule. Kept the proxy bullet + theirs' uploads bullet. Unioning would
  have documented the upload naming twice with the first copy stating the very rule
  #9 replaces (class 5).
- `README.md`: union, a third `* unreleased:` bullet.
- `mcritweb/views/analyze.py` `query()`: #40 records the uploaded filename in SQLite,
  #9 persists the bytes under the job id. Different things, both best-effort, both
  after the job is queued — kept both.
- `mcritweb/views/data.py`: `views.utility` import — `query_upload_path` added to
  ours' parenthesised name list.

### #38 fix/44-dedumped-is-not-a-dump — 5 hunks
### INTEGRATION DEFECT 12 — a conflict tail would have re-opened #9's security fix
`mcritweb/views/analyze.py` `query()`. #44's side of the hunk adds a `try/except`
around `SmdaReport.fromDict(json.loads(...))` (its real contribution here: the base
address check moved to the dump branch, so a malformed .smda no longer 400s by
accident) — but the hunk *continues* into master's
`upload_sha256 = smda_report.sha256` / `hashlib.sha256(...)` /
`with open(.../uploads/upload_sha256, "wb")`, which is exactly the code #36
(`fix/9-promote-a-query-to-a-sample`) removed because an `.smda` upload named by the
`sha256` its own report declares lets any visitor overwrite another user's stored
query. Taking "theirs" would have restored the vulnerability *and* left the file
written twice under two names, with no conflict and no failing test.
Resolved: kept #44's guarded parse, cut the hunk at `upload_sha256 = ...`, so the
only write is #9's job-id-named one.
Other hunks: `analyze.py` imports (both lines edited, names merged);
`views/data.py` `views.params` import list (union + `ruff --fix` for I001);
`tests/conftest.py` (theirs adds `addReport` next to
`requestMatchesForSmdaReport` — union); `tests/testUpload.py` (`safe_union`,
disjoint test names).

### #39 fix/38-filter-the-matching-statistics — 2 hunks
`mcritweb/__init__.py`: one more import line and one more `add_template_global`,
both disjoint from what #51/#32/#45 had already added there. Union.

### #40 fix/64-deserialize-the-function-listing — 2 hunks
### INTEGRATION DEFECT 13 — #56 kept raw wire dicts where #64 deserialises
`mcritweb/views/explore.py` `functions()`. #56 rewrote the listing into a `by_id`
dict and deliberately kept **raw dicts** (`by_id[exact['function_id']] = exact`),
saying so in a comment: "Kept as raw dicts, which is this page's existing
convention". #64's whole point is that the raw dicts are a latent bug (Jinja falls
back from attribute to item lookup, so a derived property such as
`getShortSha256` would raise). Only the second loop conflicted; **#56's
exact-match loop and its comment are outside the conflict region**, so a
take-theirs would have deserialised one loop and left the other handing raw dicts
to the same macro, with the comment still asserting the old convention.
Resolved: both loops now build `FunctionEntry.fromDict(...)` and key `by_id` on
`entry.function_id`, and the stale comment above them (which git had merged
cleanly) was rewritten to state both #56's dedup rule and #64's deserialisation.
`tests/testSearchPages.py`: disjoint additions — `safe_union`.

### #41 fix/69-functionvs-loop-visualisation — 2 hunks
### INTEGRATION DEFECT 14 — three branches, three fakes for one backend method
`tests/fixtureData.py::CorpusMcritClient.getMatchesForPicHash` was written
independently by #34 (list of tuples), #35 (a `set`) and #41 (a sorted list of
lists). Only one can survive, and the choice is not cosmetic: the fake is the
contract the views are tested against. Kept **#41's**, the only one whose non-summary
return is what `McritClient` actually parses off the wire — JSON arrays — and the
only one with a deterministic order. (#35's `set` was already dropped at #35.)
The conflict again dragged neighbours along: ours' side of the hunk also held
`getMatchesForPicBlockHash` (#34, no counterpart in #41) and
`requestMatchesForSample` (#35), and theirs' held `getMatchFunctionVs` (#41).
Spliced so all four methods survive with one `getMatchesForPicHash`.
`tests/testResultPages.py`: `import pathlib` vs `import re` — kept both.

### #42 fix/68-result-page-performance — 9 hunks
- `static/style.css`: #52's `white-space: nowrap` rules and #68's `.mcrit-diagram`
  placeholder, both appended at the end. Union; brace balance checked (the file has
  no dark-theme block yet — that arrives with #58).
- `views/data.py` imports: `import uuid` (theirs, used by `write_atomically`) kept,
  `from datetime import datetime` dropped (#98 replaced it with `db.utc_now`),
  ours' `from urllib.parse import urlencode` kept.
- `cache_result`: **#68's `write_atomically` supersedes the `newline="\n"` fix I made
  at #23** — its docstring documents exactly the same Windows CRLF hazard and passes
  `newline=""` for text modes. Took theirs, with `utc_now()` for the timestamp.
- `result_matches_for_sample_or_query`: #40's `name_query_sample` helper and its call
  kept, on #68's widened `(..., diagram_size=None)` signature.
- the `result_compare_all` branch: #68's `count_aggregated_function_matches(...)` and
  `diagram_size=`, #9's `is_query_result`/`can_promote_query`, and #68's `order_samples`
  helper that followed it on theirs' side — all four kept.
- **the cross-compare custom-order branch: #68 reverts #99's fix.** Theirs' rewrite
  ends `render_template("result_corrupted.html", reason=reason, job_info=result_json)`
  — the result *dict*, not the Job, which is exactly the bug #99 found (empty heading
  id, a "Delete job data" link resolving to `/data/jobs//delete`). Took #68's O(n)
  `order_samples` call with #99's `job_info=job_info` and its comment.
  `testResultTemplateCoverage.py::test_a_cross_compare_with_a_bad_custom_order_names_the_job`
  would have caught this one; the rest of this hunk it would not have.
- `jobs()` and `job_overview()`: ours' `describable_jobs` loops (#51) and render
  kwargs (#51/#17/#55) kept, with #68's `and job.family_id not in families_by_id`
  guard — the actual performance fix in those two hunks — grafted in.
- `tests/testResultPages.py`: the import block. The conflict covered only
  `import pathlib` vs `import re`/`types`, but #68's two *new* import lines
  (`MatchingResult`, and `count_aggregated_function_matches, order_samples` from
  `views.data`) sat just below the hunk on theirs' side and were lost with it —
  seven F821s. Restored.
- `tests/testJobsPages.py` (new in #68): two more `/data/jobs` GETs needing
  `follow_redirects=True` after #36. The redirect returns before any
  `getQueueData`/`getFamily` call, so the call counts those tests assert are
  unaffected.

### #43 fix/77-explore-page-backend-calls — 11 hunks, and the largest cross-branch fallout so far
Conflicts, first:
- `docs/manual/README.md`: #56/#58's paragraphs and #77's new "Plain terms and
  prefixed terms" section — union, with a blank line between them.
- `templates/js/ac_family_names.html`: took theirs wholesale. #77 replaces the
  shipped name list with a fetch-as-you-type against a new `/explore/family_names`,
  so ours (master's `|tojson` from #85, plus #14's `var` declaration) has nothing
  left to apply to; theirs is an IIFE using `const`/`let` throughout, so #14's
  JS-scoping ratchet stays satisfied.
- `views/explore.py` x7: module additions unioned; `families()` keeps #56/#64's
  `by_id`/`exact_matches` and loses the `getFamilies()` preload; `samples()` and
  `single_family()` take #77's `sample_row_job_collection`; `sample_by_id` keeps
  #58's `sort_memory="function"` on #77's up-front `job_collection` binding, and
  #51's `describable_jobs` on #77's narrowed queue read.
- `tests/fixtureData.py`, `tests/testScriptEscaping.py`: `safe_union`.
Then, the things nothing conflicted over:

**a. `sample_row_job_collection` lost #51's readability guard.** #77's new helper does
`JobCollection(jobs)`; every other place a job reaches a row macro goes through
`describable_jobs` (#51), because `filterToSampleIds` and the macro both read
`job.sample_id`, which raises for an unreadable payload. Added it inside the helper.
(That made the helper request-scoped — the memo lives on `g` — so #77's direct-call
ordering test needed an `app.test_request_context()`.)

**b. `render_template("samples.html", ...)` lost `exact_matches=`.** #77's side of that
hunk was written against master and does not carry #56's kwarg; taking it dropped the
Match column from the sample listing. Caught by ruff (F841 on the now-unused local),
not by a test — five `testExactMatchMarking`/`testListingIdMatches` tests failed only
after I looked. Restored.

**c. `sample_by_id`'s new `filter=` re-opens what #51 fixed.** #77 sends
`getQueueData(filter=str(sample_id))`; the backend evaluates that as
`filter in job.parameters` (`QueueRemoteCalls.getQueueData:41`), which raises server
side for a job whose payload cannot be read — so **one** unlistable job anywhere in
the queue fails the whole request and the sample page loses every job annotation,
which is precisely the failure #51 removed. Resolved by falling back to the
unfiltered queue when the filtered request fails, before giving up and flashing: the
filter is only a pre-narrowing, `filterToSampleIds` is what makes the set exact.
Also made the corpus fake answer `None` there rather than propagating the exception —
`McritClient` maps a backend failure to None, so a view was being tested against a
failure mode it can never actually see.

**d. #77's newly faithful fake exposed three stale test premises.**
- `tests/testMalformedJobPayload.py`'s synthetic `job_document` lacks `locked_by`,
  `locked_at` and four other fields every real queue document has; #77's `_job_state`
  (a transcription of `mongoqueue._identifyJobState`) reads them, so `state=finished`
  on the home page became a KeyError. Added the fields.
- `testJobNames::test_the_job_list_calls_it_the_same_thing` read `/data/jobs` for both
  job names; the fake now honours `method=`, so each name is only on its own tab.
  Parametrised by category instead.
- `testBackendTransportErrors.INDEX_CALLS` listed `getFamily`. `index()` asks the
  queue for `method="getMatchesForSample"` only, and `Job.family_id` is None for that
  method, so the `getFamily` loop is unreachable — it looked reachable only while the
  fake ignored `method=`. Dropped from the list, with the reasoning recorded there.
- `testExplorePageCalls::..._survives_a_failed_function_search` asserted the old
  `"failed"` wording #79 replaced (same class as defect 2). Retargeted.
- `testSearchPages::test_one_category_failing_...` asserted the message names
  "sample, function"; #77 sets `DEFAULT_SEARCH_TYPES = ["family", "sample"]` (a plain
  function term costs a full scan — its manual section says so), so functions are not
  searched without `?type=`. Retargeted to "sample", plus an assertion that the failed
  category is not counted among the ones that answered.
- `tests/testBackendNoResult.py`'s remaining marker — "`/explore/samples` still breaks
  on getFamilies, #77 will say whether it closed it" — is now answered: #77 removed
  the `getFamilies()` call. Turned into the positive assertion it asked to become.

### #44 fix/80-block-isolation-table — 5 hunks
### INTEGRATION DEFECT 15 — two rewrites of the same YARA rule builder
`views/data.py`. #37 (`fix/93-configurable-unique-blocks`) made the rule's parameters
a form (`build_yara_rule(blocks_result, yara_params)` returning `(rule, cover)`, plus
`YARA_RULE_DEFAULTS` / `YARA_CONDITION_MINIMUM` / `YARA_REQUIRED_PER_SAMPLE_MAXIMUM`);
#44 annotates each selected block with its `function_id`
(`build_yara_rule(job_info, blocks_result, blocks_statistics)` returning the rule,
plus `YARA_CONDITION_REQUIRED = 7` and `name_functions_in_rule`). Same function name,
different signature and return arity — either side alone silently drops the other
feature, and taking theirs would additionally have broken the caller.
Resolved into one builder: #93's parameterised cover and early "no blocks, no rule"
return, with #80's `name_functions_in_rule` applied to the rendered rule before it is
returned. Dropped `YARA_CONDITION_REQUIRED`, which is
`YARA_RULE_DEFAULTS["condition_required"]` under a second name (the
`SCHEMA_V1_4_8`-style hazard). `get_sample_versions` and the `sample_versions=`
template variable kept; #93's `yara_params`/`yara_query` kept.
`templates/result_unique_blocks.html`: #93's parameter form and empty-rule warning
kept, with **#80's copy line** — #80 replaced `copyElementToClipboard` with
`copyTextAreaToClipboard` in the script block above (which merged cleanly), so ours'
`onclick` would have called a function that no longer exists.
`tests/testResultPages.py`: two disjoint import sets, merged.

### #45 fix/7-round-the-score-columns — 13 hunks
### INTEGRATION DEFECT 16 — two branches created the same new test module
`tests/testBrowser.py` is a **new file on both** #44 (`fix/80-...`, the unique-blocks
clipboard) and #45 (`fix/7-...`, the score tooltips), with different module
docstrings, different `playwright` imports, and colliding `live_server` / `browser_page`
fixtures that mean different things (#80 signs a session cookie and watches `alert()`;
#7 logs in through the form and collects console errors). Unioning them would have
left one definition shadowing the other and half the browser coverage silently dead —
and pytest would still have been green.
Resolved by giving #7's module its own name, `tests/testBrowserScores.py`, with a
docstring paragraph saying why. Both modules now run: 3 + 2 tests, both under a real
Chromium.
Other hunks: `views/data.py` — #7's `recover_score_divisors` next to #40's
`name_query_sample` on #68's widened signature (one merge produced a stray duplicate
`def result_matches_for_sample_or_query(...)` line, removed), and `divisors=` added to
the four `render_template` calls that already carried #68's `diagram_size=` and #9's
promote flags. `tests/testResultPages.py` import block: two disjoint sets, merged.
Test fallout: `testResultPages::test_the_function_comparison_page_shows_the_overall_
match_score` (from #41/#69) asserted `int(7.8125) == 7`; #7 changed that template's
`"%d"|format` to `"%.0f"|format` deliberately, so the page now reads 8. Assertion
changed to `round(float(expected))`, with the reason recorded in the docstring — the
test still pins that the page shows the backend's number.

### #46 fix/46-cross-job-duration — 4 hunks
### INTEGRATION DEFECT 17 — a second `utc_now`, shadowing the imported one
`views/data.py` already does `from mcritweb.db import ... utc_now` (#98's
**timezone-aware** clock, used for the cache filename). #46 adds a module-level
`def utc_now()` returning a **naive** whole-second UTC datetime — same name, different
type, in the same module. The definition wins over the import, so `cache_result` would
silently switch clocks; and had I taken the import's version instead,
`total_duration`'s own `(created_at.tzinfo is None) != (finished_at.tzinfo is None)`
guard would have returned None for every running job and the feature would have
vanished with no test failing (the tests freeze the clock).
Resolved by renaming #46's to `job_clock_now()`, keeping it naive, saying in its
docstring why the two exist, and retargeting `tests/testJobDuration.py`'s
`monkeypatch.setattr`. Also rewrote its body from the deprecated `datetime.utcnow()`
(#98's whole point) to `datetime.now(UTC).replace(tzinfo=None, microsecond=0)`, which
is the same value.

### INTEGRATION DEFECT 18 — a stray `@bp.route` on the wrong function (class 3)
Splicing #46's block in left master's `@bp.route('/jobs',methods=('GET', 'POST'))`
sitting above ours' `@bp.route('/jobs')`, i.e. two rules for one endpoint, with POST
back on the one #51 deliberately made GET-only. Caught by #51's own
`testJobSearch::test_the_jobs_page_no_longer_accepts_a_post` (405 became 200).
Removed.
Other hunks: `job_overview`'s render gained `child_progress=dependency_progress(...)`
alongside ours' kwargs; `tests/fixtureData.py` — #46 introduces `_queue_by_id` for the
same dict ours already calls `_queued_by_id`, so ours kept and the duplicate dropped.

Note: `tests/testFunctionVsBrowser.py::test_each_boundary_encloses_the_blocks_of_one_loop[a-84]`
failed once in a full-suite run and passes three times out of three in isolation —
watched for the rest of the merge.

### #48 fix/74-synchronise-the-cfg-panes — 5 hunks
- `AGENTS.md`: both branches rewrote the same `main_duo.js` bullet — #69 describing
  its per-panel state and four fixed sinks, #74 the two-pane synchronisation. Kept
  #69's (the longer, and the one carrying the escaping rules `testScriptEscaping.py`
  enforces) and grafted #74's sentence and its ADR link into it. **Re-measured the
  numbers it quotes**: with both patches merged the file is 4,012 lines and the diff
  against stock `main.js` is 1,264 — neither branch's figures (3,902/1,137 and
  3,647/620) is true of the merged file, and AGENTS.md asks for `file:line`-grade
  claims to be checked against the revision they describe.
- `tests/fixtureData.py` x4: a **fourth** `getMatchesForPicHash` and a second
  `getMatchFunctionVs`. Kept ours (the #41 versions already settled at #41), but took
  two things from #74's: the module-level `MINHASH_CONFIG` singleton it also adds
  (which had merged cleanly and would otherwise have been dead) and its `float(...)`
  cast on the score, with the reason — the real client's value has been through JSON,
  and a numpy scalar here lets a view look right against a shape the wire never
  produces.

### INTEGRATION DEFECT 19 — three ADRs, all cited as "ADR-0003" (class 6)
`AGENTS.md:76`, `:129` and #74's bullet each linked `[ADR-0003](docs/adr/00NN-...)`
at a *different* file — 0012 (backend probe), 0010 (search results are dicts), 0013
(no combined CFG view). Each branch wrote its ADR as 0003 locally; the files were
renumbered into 0009-0016 on the way in, and the link **text** was not. Corrected each
label to the file it points at, and checked mechanically that no
`[ADR-NNNN](docs/adr/MMMM-...)` pair disagrees anywhere in the tree.
(ADR numbers 0003-0008 and 0014 are unused so far — re-checked at the end.)

### #49 fix/50-deduplicate-result-tables — 17 hunks
### INTEGRATION DEFECT 20 — #50's shared macros are a copy of master, i.e. a silent revert of #7
This is the failure the brief names, and it is real. #50 moves the five result
templates' inline match tables into `templates/table/match_row.html`, and that file was
written against **master**: its cells carry `{{ "%3d"|format(...) }}` (truncation) and
`data-hint="... / {{ matching_result.reference_sample_entry.binweight }}"` — the two
things #45 (`fix/7-round-the-score-columns`, ADR-0009) had just replaced with
`"%3.0f"` and the recovered `divisors.matchable` / `divisors.nonlibrary`. git resolves
this as "ours deleted the block, theirs replaced it with a macro call", so **taking
theirs is a clean, conflict-free revert of #7 on all five pages** — and #7's tests move
with the markup: they read the rendered page, so they would have gone on passing
against the macro's numbers.
Resolved by porting #7 into the macro rather than into the pages:
`famlib_row` gained a `divisors` argument (a Jinja macro does not close over the
caller's scope, which is the whole reason #50's own docstring gives for its parameter
list), its four tooltips now divide by `divisors.matchable`/`.nonlibrary`, its four
score cells and `aggregated_function_row`'s `best_score` and `matched_function_row`'s
`matched_score` all round; and the six call sites pass `divisors` through.
Verified two ways, in `scratchpad/int3_cellcheck.py`:
 - all 7 distinct score `<td>`s that #7 wrote into the templates are present in the
   merged tree verbatim (whitespace-normalised), 0 missing;
 - #7's own rendered-page tests (`test_score_columns_round_rather_than_truncate`,
   `test_score_tooltips_divide_by_the_total_their_percentage_uses`,
   `test_function_score_column_rounds_rather_than_truncates`) pass and are
   non-vacuous — each asserts it found score cells and that the expected template was
   the one rendered.
Also in these hunks: #50's side re-introduces the synchronous
`create_match_diagram(current_app, ...)` calls that #42 (`fix/68-result-page-performance`)
removed in favour of the lazy diagram route + `diagram_size` — dropped, so #68 is not
reverted either. Kept #68's single `getAggregatedFunctionMatches()` per branch feeding
both `len()` and `sorted_page` (`count_aggregated_function_matches` still has its own
call site and its own test), #9's promote flags, #7's `divisors=`, and #50's
`family_rows`/`library_rows`/`sample_rows`/`function_rows`.
`result_compare_function.html`: import line — #68's `match_diagram` plus #50's
`sortable_header_col`. `tests/testResultPages.py`: import block and two disjoint test
blocks (`safe_union`), with the import list re-sorted for ruff.

### #56 fix/42-cross-compare-ordering — 2 hunks
`views/data.py` `result_matches_for_cross`: theirs is master's O(n^2) inner loop with
#99's `job_info=job_info` fix already folded in; ours is #68's `order_samples` helper
with the same fix. Took ours — the rest of #42 (the `order=` query parameter,
`CROSS_ORDERINGS`, `order_sample_ids`, `active_order`) merged cleanly around it, and
`order_samples(samples, order)` answers None for exactly the case theirs' `for/else`
catches. `tests/testResultPages.py` import block: kept both sides' names.

### #57 fix/query-upload-path-traversal — 1 hunk
### INTEGRATION DEFECT 21 — a security fix superseded by a stricter one, and its tests still assert the vulnerable scheme
#57 hardens the sha256-named upload path in `analyze.query`: it validates that the
`sha256` an SMDA report *declares* is a hexdigest before joining it into a path, so a
report saying `"sha256": "../../../PLANTED"` cannot choose where the upload lands.
#36 (`fix/9-promote-a-query-to-a-sample`) had already removed that write entirely — the
file is named by the backend-issued job id, and `views/utility.query_upload_path`
refuses anything that is not one. #57's fix therefore has nothing left to guard.
Taking theirs would have re-added the sha-named write **beside** #36's job-id one:
two copies of every upload, one of them under a name the uploader controls.
Resolved: took ours (no sha-named write), removed the now-dead `UPLOAD_SHA256`
constant and its comment, and **deleted `tests/testQueryUpload.py`** — every one of
its five tests asserts the file is stored under a hash, which is now false, and all
five are superseded test-for-test by `tests/testQueryUploads.py` (from #36), which
covers the same disclosure end to end plus the traversal, the Windows device names,
the `"None"` job id and the promote path. Confirmed the survivors pass (80 tests).

### #58 fix/70-tokenise-the-palette — 26 hunks across 19 files, and five cross-branch defects
Straightforward halves first: README (union, a fourth `unreleased` bullet); `db.py`
(the theme constants beside #98's timestamp helpers; the `user` INSERT gained #70's
`theme` column while keeping #98's `format_timestamp(utc_now())` rather than the
deprecated `datetime.utcnow()` theirs still wrote); `authentication.py` /
`administration.py` imports; `MatchReportRenderer.py`, `testMigrations.py`,
`testResultPages.py` (unions); the four result pages' diagrams became
`{{ match_diagram(diagram_filename(...), diagram_size) }}` — #68's lazy `<img>` macro
named by #70's helper; `result_compare_*.html` row hunks took #50's macros.

### INTEGRATION DEFECT 22 — the theme in the filename vs #68's filename grammar (class 4)
`views/data.py`. #70 appends `-dark` to a cached diagram's name; #68 renders a missing
diagram from the name the browser asked for, parsed by `DIAGRAM_FILENAME_RE` whose job
id charset includes `-`. So `<job>-dark.png` parses as **one long job id nobody has**:
`load_cached_result`/`getResultForJob` miss, nothing is rendered, and every dark-theme
diagram is a broken image until some other request happens to write it. Merged
cleanly, and #70's own `test_the_match_diagram_is_cached_per_theme` was written
against the pre-#68 inline rendering.
Resolved: `DIAGRAM_FILENAME_RE` grew `(?:-(?P<theme>dark))?`, and `diagram_filename` /
`create_match_diagram` take the theme as an argument so `render_missing_match_diagram`
draws **the theme named in the file it was asked for** rather than the requester's —
otherwise following a link to somebody's dark diagram writes a light one under the
dark name. Added `tests/testMatchDiagrams.py::
test_a_dark_diagram_is_recognised_rather_than_read_as_a_job_id` (x3) and
`test_the_dark_diagram_is_rendered_on_demand_and_is_not_the_light_one`, which compares
the two images' corner pixel; verified all four fail without the regex alternative.

### INTEGRATION DEFECT 23 — a `NameError` in `create_match_diagram` from the same hunk
Taking #70's one-line `output_path = ... diagram_filename(...)` dropped the
`output_filename` variable #68's `write_atomically(app, cache_path, output_filename,
...)` call needs. Every diagram rendered and then failed to be written, and
`diagram_file`'s broad `except Exception` turned that into a 404 — 12 failures in
`testMatchDiagrams.py`. Now computed once and used for the check, the write and the log.

### INTEGRATION DEFECT 24 — #70's base.html re-adds the libraries #63 removed
`templates/base.html`. #70's side of the `<head>` hunk still lists
`jquery-ui.css` and `dataTables.bootstrap5.min.css`, because #70 branched before #63
took DataTables out of the application and moved jQuery UI's stylesheet into
`result_cross.html`. Taking theirs put 41 KB of CSS back on every page and broke
`testPageAssets`'s two ratchets. Kept only #70's `theme-dark.css` link.
Its own `test_the_dark_stylesheet_is_linked_after_every_vendored_one` then asserted
the presence of `dataTables.bootstrap5.min.css`, which no longer exists anywhere;
rewritten to derive the list from base.html and to require `theme-dark.css` last
there, plus a new
`test_a_page_specific_stylesheet_is_outranked_by_scope_rather_than_order` recording
why #63 and #70 are compatible at all: `result_cross.html` loads jquery-ui.css from
`{% block style %}`, i.e. *after* theme-dark.css, and every rule in theme-dark.css is
scoped to `:root[data-theme="dark"]`, so it wins on specificity instead of order.
That scoping is now asserted (76 rules, none unscoped).

### INTEGRATION DEFECT 25 — #53's row tints could not follow the theme, and #70's script reads a class
`templates/table/row_decoration.html`. #53's `ROW_TINTS` are literal colours written
into a `style` attribute; #70 turned the same two states into `tr.row-selected` /
`tr.row-pending` classes, tokenised per theme, **and rewrote cross_compare's click
handler to read the state back with `classList.contains("row-selected")`**. Keeping
#53's inline style would have failed #70's colour ratchet *and* left that handler
unable to see a selected row (it would try to toggle a row that is not togglable).
Resolved by making a tint a class name rather than a colour: `row_tint` now emits a
class fragment written inside the row's existing `class="..."` (never a second
attribute), the three row macros and `cross_compare.html` were adjusted, and #53's six
tint tests retargeted from the colour to the class.

### INTEGRATION DEFECT 26 — colour literals in markup #70 never saw
`test_no_template_spells_out_a_colour` is #70's ratchet over template `style=`
attributes. It passed on #70's branch and failed after the merge, on markup that
arrived from other branches: `table/match_row.html` (12 literals — #50 copied those
cells off master *after* #70 tokenised the originals), `table/table.html` (#65's
`empty_state` link), `table/column_table.html`, `unique_blocks.html` (#93's new page,
which #70 could not have tokenised: a `color: black` link and a `yellowgreen` row
tint). All moved onto the palette. `unique_blocks.html`'s picker script also still
wrote `style.backgroundColor = "rgb(240, 240, 240)"` / `"white"` — the ratchet does
not lint `<script>`, but #70 converted the three sibling pickers to `row-pending` for
exactly this reason, and "white" is not what an unselected row is on a dark page.
Converted. `static/style.css`'s `.mcrit-diagram` placeholder (#68) was likewise a
literal grey and slategray; moved onto `--surface-muted` / `--muted-text`.
Also retargeted `testExplorePageCalls`'s `badges()` helper, which recognised the job
badge by `color:green`.

### style.css structure
Checked with `scratchpad/int3_cssbalance.py`: `style.css`, `theme-dark.css`,
`navbar.css` and `signin.css` all brace-balanced, no `:root`/`@media` block nested
inside another, and the dark palette block is last with 22 declarations and no rules
reparented into it. (The dedicated brace test the brief mentions is not in the tree
yet at this point in the order; re-checked at the end.)

### #60 fix/jobs-500-when-the-queue-cannot-be-read — 1 hunk
`views/data.py`: the same `max_count` line #65, #19 and #36 had each already fixed —
a **fourth** copy of the `.get()` guard. Took ours; #60's real contribution (the
`statistics is None` guard right after `getQueueStatistics()`) merged cleanly.
Test fallout in its new `tests/testJobsQueueUnavailable.py`: two `/data/jobs` GETs
needed `follow_redirects=True` after #36, and
`test_a_category_the_queue_does_hold_still_paginates` read `start` out of the recorded
call's **kwargs** — #77 rewrote `CorpusMcritClient.getQueueData` to record it
positionally, so the assertion was reading `None` and would have passed for a broken
pagination as easily as a working one. Now reads whichever slot it is in.

### #61 fix/pagination-reserved-query-args — 1 hunk
`views/explore.py` import line: `describable_jobs` (#51) and
`request_args_for_link_building` (#61) — both kept.
Then two things that merged cleanly and were wrong:
- `views/cursor_pagination.py` ended up with `from mcritweb.views.pagination import
  request_args_for_link_building` in the *middle* of the file, after #58's sort-memory
  block — ruff E402. Moved to the import block. (Both branches appended to the top of
  the file; the merge put one after the other's new code.)
- five `testPagination.py` cases and one `testPageLoadingSpinner.py` case fetch
  `/data/jobs`, which answers 302 since #36. `follow_redirects=True`, as elsewhere.

### #62 fix/submit-metadata-into-the-query-string — 4 hunks
`views/data.py`: import line (both sides' names), module-level helper (disjoint), and
the `addBinarySample` call — #62 wraps its three text fields in
`quote_backend_query_value`, #43 wraps the whole call in `require_result`. Kept both;
either alone drops a fix (the escaping, or the "backend answered nothing" handling).
`tests/testUpload.py` import line: both names.

### #64 fix/sample-filtered-result-pagination-count — 6 hunks
`views/data.py`, three `render_template` calls. #64 fixes the `?samid=` page's
function pagination (it lists individual matches, so it must count
`num_function_matches`, not the aggregate — ours still had #68's
`count_aggregated_function_matches` there, which leaves the tail of the table on no
page at all) and adds `num_original_aggregated_functions` for the "filtered: N"
figure on the family and unfiltered pages. Kept #64's count and its new kwarg on
top of ours' `divisors=`/`diagram_size=`/`sorted_page` rows and #9's promote flags.
`tests/testResultPages.py`: two import hunks merged by hand (six modules between the
two sides) and one `safe_union` of disjoint test blocks.

### #65 fix/stop-printing-match-reports — 4 hunks
- `MatchReportRenderer.py`: #68's geometry constants/helpers and #65's `LOG` (union),
  and the `print(f"stack size: ...")` line, which #65 turns into `LOG.debug` and #68
  had replaced the two size expressions beside it with the shared
  `stacked_diagram_size(num_blocks)` — the same arithmetic, and the one
  `match_diagram_size` reserves the `<img>` box from, so it has to stay the shared
  call. Took both.
- `views/data.py`: the diagram write — #68's `write_atomically` with #65's
  `app.logger.debug` (and its comment on why `app`, not `current_app`); and
  `getMatchFunctionVs` — #43's `require_result` wrapper, #65's removal of the
  `print(match_info)` that dumped the whole 1-vs-1 report per request.
#65's AST ratchet `testNoStrayPrints.py` passes: the prints left in
`MatchReportRenderer.py` are all inside its allowlisted CLI-only functions.

### #67 fix/import-rejected-is-not-malformed — 1 hunk
`tests/testUpload.py` import line: `import random` (theirs) beside `re` / `quote`
(ours). Both kept.

### #68 fix/autocomplete-escapes-suggestions — 3 hunks
### INTEGRATION DEFECT 27 — #77 moved the type-ahead's data out of reach of #68's escaping
`static/autocomplete.js` is vendored and may not be patched; it renders each suggestion
through `innerHTML` and into a `data-label` attribute, so a family name reaching it is
markup. #68 escapes at the two call sites with an `autocomplete_items` Jinja filter.
But #43 (`fix/77-explore-page-backend-calls`) had already replaced one of those call
sites: the family type-ahead on the four explore pages now **fetches** its suggestions
from `/explore/familyNames` as the user types and builds `{label, value}` in the
browser. That data reaches the same `innerHTML`, unescaped. Taking ours dropped the
escaping for four of the five pages; taking theirs reverted #77's whole point. The
conflict is only in one template, and #68's own ratchet is source-level, so the hole
would have been invisible on the merged tree until somebody named a family
`zz<img src=q onerror=...>`.
Resolved by giving the escaping one implementation and two producers:
- new `mcritweb/autocomplete.py` holds `autocomplete_items(names)` and `RESPONSE_KEY`;
- `__init__.py`'s `autocomplete_items` filter delegates to it (for the
  `submit_or_query_dropzone` macro, which still ships its list with the page);
- `explore.family_names` answers `{"autocomplete_items": [...]}` built by the same
  function, and `js/ac_family_names.html` hands that array straight to `setData`
  rather than mapping raw names.
The ratchet was **extended, not weakened**: it now also accepts a data expression that
is the `autocomplete_items` field of a response, or a literal empty array (the initial
`data:` of a widget filled in later). Three new bypass cases were added to its own
regression set and all are still rejected - a response read under another key, names
mapped into items in the browser, and a non-empty array literal - and two new tests
carry the weight the field name now rests on:
`test_the_endpoint_escapes_what_it_hands_the_type_ahead` (poisoned backend, asserts no
markup character survives and that the payloads really got there) and
`test_both_producers_build_the_same_items`. Plus
`test_a_fetching_page_ships_no_names_of_its_own`, so a page cannot end up with two
producers again.
Test fallout: #68's `test_the_type_ahead_data_is_html_escaped` was parametrised over
five pages and can only inspect the one that still ships its names — narrowed to it,
with the other four covered by the endpoint test. Three of #77's tests
(`testExplorePageCalls` x2, `testScriptEscaping` x1) asserted the endpoint's old
`{"family_names": [...]}` shape; updated. #77's `testScriptEscaping` docstring said
outright that the widget's `innerHTML` sink "is not made safe by anything here" —
rewritten, because it now is, and by whom.
Other hunks: `AGENTS.md` (theirs' headline bullet naming `autocomplete.js` plus ours'
`main_duo.js` and dropzone sub-bullets); `submit_or_query_dropzone.html` (theirs'
filtered one-liner).


## After the last merge: the deliberate sweep

### INTEGRATION DEFECT 28 — `SCHEMA_V1_4_8` defined twice (class 6)
`tests/testMigrations.py:115` and `:194`. #30 (`fix/40-query-result-identity`) and #58
(`fix/70-tokenise-the-palette`) each added the same 74-line schema constant, with its
own comment, and I unioned them at #30 — `resolve.safe_union` only guards against a
shared `def`/`class`, not against a shared assignment, so it reported the union as
safe. The two bodies are byte-identical, so the second silently shadowed the first and
every test using it still passed. Found with an AST scan for module-level names bound
twice (`SCHEMA_V1_4_8` was the only hit in the whole tree). Removed the second copy;
the surviving comment now names both migrations that start from that schema.

### The stylesheet brace test
The brief says there is a test for the dropped-`}` failure. There is not — I searched
every one of the 68 branches for a test that reads a stylesheet and counts braces, and
only `testJavascriptScoping.py` (braces in JS) and `testCfgGraphs.py` (braces in one
dot graph) exist. Since the invariant is real and this merge is exactly the situation
that breaks it (`style.css` took additions from #52, #68 and #70, three of them at the
end of the file), I wrote it: `tests/testStylesheetStructure.py` — brace balance and
"no `:root`/`@media` has become nested" for the four project stylesheets, plus
"the dark palette block contains only custom properties", plus its own regression
cases so it cannot pass vacuously. Verified it fails when a real `}` is removed from
`static/style.css`, and that a brace inside a comment or a string does not fool it.

### README: a claim that was false on its own branch
#70's changelog entry ends "Not themed: ... the match diagram PNGs, which are baked on
white and cached without invalidation." Its own branch themes them
(`MatchReportRenderer(g.theme)`, `THEME_GROUNDS`, the `-dark` suffix), so the sentence
was wrong before the merge and after it is the sentence a reader would use to decide
whether the `-dark` cache names matter. Corrected.

### `[ADR-0003]` a third time
`AGENTS.md:94` still labelled `docs/adr/0014-no-htmx-for-table-reloads.md` as ADR-0003
— a third branch that numbered its ADR 0003 locally. Fixed, and re-checked
mechanically: no `[ADR-NNNN](.../MMMM-...)` pair disagrees anywhere, the 16 ADR files
are numbered 0001-0016 with no gaps and no duplicates, and their cross-references
(0001->0002, 0002->0001, 0008->0005, 0015->0004) all resolve.

### Sweeps that came back clean
- **Silently reverted markup (class 1), all 68 branches.** `int3_survivors.py` diffs
  each branch against master, takes every distinctive added line in `mcritweb/`, and
  checks it is still in the merged tree. 175 lines are not — every one of them is a
  line a later branch rewrote in place (a `render_template` call that grew kwargs, a
  helper superseded by a shared one, the code I deliberately dropped), and each
  matches a resolution recorded above. No unexplained loss.
- **The result tables specifically.** `int3_cellcheck.py`: all 7 distinct score `<td>`s
  #7 wrote are present verbatim; #7's rendered-page tests pass and are non-vacuous.
- **Duplicated visible things (classes 2 and 5).** Rendered 30 pages (every listing,
  every result type, every filter, both job pages, the analyze pages, settings) through
  the corpus fixtures and looked for a repeated sentence, a repeated badge label, or a
  table whose rows disagree with its header. The one repeated badge is `ID` appearing
  once each in the family table and the sample table of a combined search - two
  different records - and the "ragged" tables are `colspan="2"` headers and my parser
  mishandling nested tables. Nothing left over.
- **Stray decorators (class 3).** `@bp.route` is the outermost decorator on every view,
  no route is registered on a private-looking function, `testRoutePolicy.py` passes and
  both of its ratchets (`IN_VIEW_GUARD`, `KNOWN_INERT_DECORATORS`) are still empty sets.
- **Filename/regex couplings (class 4).** The diagram grammar is fixed and tested
  (defect 22). The other filename-derived name, the result cache's
  `%Y%m%d-%H%M%S-<job_id>.json`, is parsed by `find_cached_result_filename` on a
  fixed-width timestamp prefix and guarded by `is_cacheable_job_id`; no branch added a
  suffix to it.
- **Definitions twice (class 6).** One AST scan over `mcritweb/` and `tests/`: after the
  `SCHEMA_V1_4_8` fix, no module-level name is bound twice. No Jinja macro is defined
  twice in one file except the two nested helpers in `pagination_widget.html`, which
  are inside two different outer macros and are that way on master. No config key is
  set twice; no template filter or global is registered twice.
