# STATE — triage of every open issue on fkie-cad/mcritweb

Live document. Updated after every issue, not at the end.

**Snapshot taken 2026-08-29.** 54 open issues; the set was reconstructed from the public
HTML issue list (see `work/LOG.md` for why the API was unavailable and how the list was
verified to be complete — the count matches GitHub's own "Issues 54" header exactly).

Codebase under triage: `r0ny123/mcritweb` @ `df53db9` (identical to `origin/master`),
which tracks upstream v1.4.8.

**Reproduction environment:** `work/SETUP.md`. Short version — the offline suite and
`ruff` run clean (239 passed), the app boots, and pages can be walked against the
project's own captured corpus through `work/harness/devserver.py`. There is **no real
MCRIT backend** (no MongoDB, no docker daemon), so anything whose symptom needs a
populated Mongo collection is marked `can't` with the reason.

## Severity ladder used

`data loss > security > crash > wrong behaviour > UX > cosmetic`

## Priority formula

`severity x users-hit / effort`, as instructed. Quick obviously-correct fixes that
unblock real users first; sweeping refactors last or not at all. Issues that cannot be
reproduced sink to the bottom regardless of their claimed severity.

---

## Ranked table

One row was added to this table after triage: the CI failure that turned out to block
every PR. It is not an upstream issue - see `work/LOG.md`, 22:05Z.

| # | prio | summary | reproduced | severity | effort | status |
|---|---|---|---|---|---|---|
| — | 0 | `/data/jobs/<id>` returns HTTP 500 when a sub-job has been deleted (`sorted` over `None`) | **yes** | crash | S | PR opened — [#18](https://github.com/r0ny123/mcritweb/pull/18) |
| — | 0 | Every CI unit job fails with `No module named pytest`; the suite has not run since `mcrit` moved it behind its `dev` extra | **yes** | blocks everything | S | PR opened — [#9](https://github.com/r0ny123/mcritweb/pull/9) |


| # | prio | summary | reproduced | severity | effort | status |
|---|---|---|---|---|---|---|
| — | 1 | `/data/linkhunt/<job_id>` returns HTTP 500 for every job type that is not one of the four matching methods | **yes** | crash | S | PR opened — [#2](https://github.com/r0ny123/mcritweb/pull/2) |
| 73 | 2 | Finished job with an empty result is reported as an unknown job id | **yes** | wrong behaviour | S | PR opened — [#3](https://github.com/r0ny123/mcritweb/pull/3) |
| 98 | 3 | `datetime.utcnow()` + implicit sqlite3 datetime adapter: 405 deprecation warnings on 3.13, plus a latent read crash | **yes** | wrong behaviour (latent crash) | S | PR opened — [#4](https://github.com/r0ny123/mcritweb/pull/4) |
| 54 | 4 | A search that matches nothing renders a heading and no message | **yes** | UX | S | PR opened — [#5](https://github.com/r0ny123/mcritweb/pull/5) |
| 101 | 5 | Login says "Incorrect username." vs "Incorrect password.", confirming which accounts exist | **yes** | security | S (enumeration half) / L (rate limiting) | PR opened (partial) — [#6](https://github.com/r0ny123/mcritweb/pull/6) |
| 100 | 6 | API tokens generated with MD5; no way to rotate one | **yes** (code) | security | M | PR opened — [#7](https://github.com/r0ny123/mcritweb/pull/7) |
| 78 | 7 | Search shows an entry twice when the term is also its id | **partially** | wrong behaviour | S | PR opened — [#8](https://github.com/r0ny123/mcritweb/pull/8) |
| 79 | 8 | "Ups, search for `<hash>` ... failed!" when a sha256 is simply not in the DB | **partially** | UX | S | PR opened — [#10](https://github.com/r0ny123/mcritweb/pull/10) |
| 89 | 9 | `mcrit_server_required` makes a blocking HTTP probe on every request to 36 routes | **yes** (code) | UX (latency) | M | PR opened — [#11](https://github.com/r0ny123/mcritweb/pull/11) |
| 51 | 10 | Job search is dead code (the form is inside a Jinja comment) | **yes** | UX | M | PR opened — [#12](https://github.com/r0ny123/mcritweb/pull/12) |
| 65 | 11 | 'No data in table' message is the same everywhere | no (cosmetic, no repro needed) | UX | M | PR opened — [#16](https://github.com/r0ny123/mcritweb/pull/16) |
| 52 | 12 | Line breaks in table headers and export/analyze buttons | can't (screenshot only) | cosmetic | S | PR opened — [#13](https://github.com/r0ny123/mcritweb/pull/13) |
| 41 | 13 | Long job names need line breaks | can't (screenshot only) | cosmetic | S | PR opened — [#14](https://github.com/r0ny123/mcritweb/pull/14) |
| 61 | 14 | Undeclared JS globals | partially | cosmetic | M | PR opened — [#15](https://github.com/r0ny123/mcritweb/pull/15) |
| 35 | 15 | "Analyze" on a function row starts a 1vsN for the parent *sample* | **yes** (code) | wrong behaviour | S–M (corrected) | **in progress** (worktree agent) |
| 66 | 16 | Import page gives no progress indication | **yes** (measured, headless Chromium) | UX | M | PR opened — [#32](https://github.com/r0ny123/mcritweb/pull/32) |
| 99 | 17 | Result template rendering only covered for five report types | n/a (meta) | — | L | PR opened — [#26](https://github.com/r0ny123/mcritweb/pull/26) |
| 93 | 18 | Configurable Unique Blocks page under Analyze | n/a (feature) | — | L | not started |
| 80 | 19 | Block isolation table improvements | can't | — | M | not started |
| 75 | 20 | Export raw results as JSON | n/a (feature) | — | M | PR opened — [#24](https://github.com/r0ny123/mcritweb/pull/24) |
| 72 | 21 | Allow modifying functions (samples/families already possible) | n/a (feature) | — | — | **blocked upstream** — mcrit has no way to modify a function; see below |
| 69 | 22 | FunctionVs: loop visualization correctness | can't (needs click-through) | — | M | not started |
| 55 | 23 | "Rerun job" button | n/a (feature) | — | M | PR opened — [#30](https://github.com/r0ny123/mcritweb/pull/30) |
| 58 | 24 | Search should remember last sort order | n/a (feature) | — | M | PR opened — [#28](https://github.com/r0ny123/mcritweb/pull/28) |
| 56 | 25 | Mark id/SHA matches in search (blocked on #53) | n/a (feature) | — | M | not started |
| 53 | 26 | Special triggers for rows in table rendering | n/a (feature) | — | M | not started |
| 50 | 27 | Table widgets for result-page tables | n/a (refactor) | — | L | not started |
| 45 | 28 | Mark the search term in results | n/a (feature, labelled `wait`) | — | M | PR opened — [#33](https://github.com/r0ny123/mcritweb/pull/33) |
| 48 | 29 | Minify/prettify HTML | n/a (feature) | — | M | not started |
| 63 | 30 | Optimize browser performance (render-blocking JS) | can't measure here | — | L | not started |
| 62 | 31 | Preload navbar icons | **yes** (measured with headless Chromium) | UX | S | PR opened — [#17](https://github.com/r0ny123/mcritweb/pull/17) |
| 60 | 32 | Consider htmx for table reload + pagination | n/a (refactor) | — | L | not started |
| 68 | 33 | Improve MatchingResults performance | can't measure here | — | L | not started |
| 67 | 34 | Investigate export→import bugs | can't (needs a real backend) | — | L | not started |
| 40 | 35 | Polish query matching results (filename missing, job name) | **yes** (3 of 5 complaints) | wrong behaviour | M | PR opened — [#31](https://github.com/r0ny123/mcritweb/pull/31) |
| 39 | 36 | Inconsistent names between job and result - six headings render *empty* | **yes** (measured) | wrong behaviour | M | PR opened — [#19](https://github.com/r0ny123/mcritweb/pull/19) |
| 38 | 37 | Filter 'Matching Method Statistics' with the result | can't (needs backend) | — | M | not started |
| 36 | 38 | Job list tabs do not change the URL, so back/refresh lose the tab | **yes** (plus a 500) | wrong behaviour | M | PR opened — [#29](https://github.com/r0ny123/mcritweb/pull/29) |
| 34 | 39 | Improve function pages (accordion, minhash flag, analyze button, shingles) | n/a (feature) | — | L | **in progress** (worktree agent) |
| 32 | 40 | Show the MinHash matching parameter in job results | n/a (feature) | — | M | PR opened — [#25](https://github.com/r0ny123/mcritweb/pull/25) |
| 9 | 41 | Promote a query to a full sample | n/a (feature) | — | L | not started |
| 42 | 42 | How to handle clustered sample sequences in cross compare (open question) | n/a (question) | — | — | not started |
| 44 | 43 | Treat "dedumped" filenames as unmapped? (open question) | n/a (question) | — | — | not started |
| 43 | 44 | Handle all kinds of errors from McritClient | **yes** (transport half: 4 of 5 failure modes were HTTP 500) | crash | M | PR opened (partial) — [#27](https://github.com/r0ny123/mcritweb/pull/27) |
| 37 | 45 | Annotate jobs with user uuids (labelled `wait`) | n/a (feature) | — | L | not started |
| 46 | 46 | Cross job duration/progress is meaningless (labelled `wait`) | can't (backend) | — | M | not started |
| 47 | 47 | Queue result cache destroyed by force rematch | can't (backend) | — | M | not started — `mcrit` issue |
| 57 | 48 | META: Jobs (tracker) | n/a (meta) | — | — | not started |
| 59 | 49 | Compound index for search | can't (backend) | — | M | not started — `mcrit` issue |
| 64 | 50 | McritClient should return objects | can't (backend) | — | M | not started — `mcrit` issue |
| 70 | 51 | Dark mode (labelled `wait`) | n/a (feature) | — | L | not started |
| 74 | 52 | FunctionVs: graph sync, combined view | n/a (feature) | — | L | not started |
| 76 | 53 | Function search ~30s when nothing matches | can't (needs a large real DB) | — | ? | **mcritweb half done in `fix/77-explore-page-backend-calls`** (`DEFAULT_SEARCH_TYPES`, explore.py:32) — the scan itself stays `mcrit`'s |
| 77 | 54 | Sample search is slow too | can't (needs a large real DB); no body | — | ? | not started — `mcrit` issue |
| 7 | 55 | Verify the nonlib frequency score calculation | can't (scoring lives in the backend) | — | ? | not started — out of scope per AGENTS.md |

`n/a (feature)` in the *reproduced* column means the issue describes something absent
rather than something broken, so "reproduce" reduces to confirming it is still absent —
which was done by code read in each case and is recorded per issue below.

---

## Per-issue detail

Everything below was either executed here or read out of the source at `df53db9`. Claims
are tagged **measured** (I ran it and the output is in `work/LOG.md`) or **inferred**
(read from source, not executed) as `AGENTS.md` asks for.

### (no issue number) — `/data/linkhunt/<job_id>` 500s for non-matching job types — prio 1

- **reproduced:** yes, **measured**.
- **repro:** start the harness, then
  `curl -s -o /dev/null -w "%{http_code}\n" --noproxy '*' -b work/harness/cookies.txt
  http://127.0.0.1:5001/data/linkhunt/6a7465f2f8b8d2c6f83664cd` (the corpus cross-compare
  job) → `500`. Same for the unique-blocks job `6a74660af8b8d2c6f83664f1`.
- **root cause:** `data.linkhunt` dispatches on `job_info.parameters` through an
  `if/elif` chain covering only `getMatchesForSample*`, `getMatchesForSmdaReport`,
  `getMatchesForMappedBinary` and `getMatchesForUnmappedBinary`. Any other finished job
  with a result falls off the end of the chain and the view returns `None`, which Flask
  turns into `TypeError: The view function for 'data.linkhunt' did not return a valid
  response.` The template written for exactly this case, `result_incompatible.html`, is
  wired to the *wrong* branch — the `else` that means "job id unknown".
- **severity:** crash. **effort:** S. **status:** PR opened.
- Not filed upstream as an issue; found during triage. Fixed as its own PR because it is
  a crash and is unrelated to the other work.

### #73 — empty result is indistinguishable from an unknown job — prio 2

- **reproduced:** yes, **measured** (regression test in the PR; the corpus has no
  empty-result job, so the test wires a backend that answers `{}` for a finished job).
- **root cause:** `data.result()` opens with `if result_json:`. An empty dict is falsy,
  so a *finished* job whose result is `{}` skips the whole dispatch, fails the
  `elif job_info and not (job_info.is_finished or ...)` guard because it *is* finished,
  and lands in the `else` that renders `result_invalid.html` — "Job ID ... or the result
  referenced by this job was not found in the system." The issue's own migration note
  says this; I confirmed it against `df53db9`.
- `result_empty.html` already exists and already says the right thing.
- **severity:** wrong behaviour. **effort:** S. **status:** PR opened.

### #98 — `datetime.utcnow()` and the implicit sqlite3 adapter — prio 3

- **reproduced:** yes, **measured**. On Python 3.13: `239 passed, 405 warnings`. Same
  suite on 3.11: `239 passed, 1 warning` (the deprecations only fire from 3.12).
- Four sites, not the two the issue lists — it misses `authentication.py:142`:
  - `mcritweb/db.py:63` — sqlite3 default datetime adapter
  - `mcritweb/db.py:65` — `datetime.datetime.utcnow()`
  - `mcritweb/views/authentication.py:142` — `datetime.utcnow()`
  - `mcritweb/views/data.py:54` — `datetime.utcnow()`
- **the trap the issue warns about, made concrete (measured):** `UserInfo.fromDb` parses
  both timestamps with `strptime(..., "%Y-%m-%d %H:%M:%S.%f")`. sqlite3's default adapter
  writes `val.isoformat(" ")`, which for an **aware** datetime appends `+00:00` — so a
  naive `utcnow()` → `now(timezone.utc)` swap alone makes every subsequent
  `UserInfo.fromDb` raise `ValueError`. Verified in a scratch interpreter.
- **bonus latent crash found while checking that (measured):** `isoformat(" ")` omits the
  fractional part when microseconds are exactly 0, and `strptime` with `%f` then raises
  `time data '2026-01-01 00:00:00' does not match format '%Y-%m-%d %H:%M:%S.%f'`. A user
  registered on that microsecond can never be read back — every page 500s for them. Rare
  (~1 in 10^6 registrations) but permanent once it happens.
- **severity:** wrong behaviour, with a latent crash. **effort:** S. **status:** PR opened.

### #54 — a search that matches nothing says nothing — prio 4

- **reproduced:** yes, **measured**.
- **repro:** `curl -s --noproxy '*' -b work/harness/cookies.txt
  "http://127.0.0.1:5001/explore/search?query=zzzznomatchzzzz"` → HTTP 200 whose body
  contains `<h1>Results for "zzzznomatchzzzz"</h1>`, the search form, and then nothing.
  No table, no message, no flash.
- **root cause:** `templates/search.html` renders each of the three result sections
  behind `{% if <group>|length > 0 or (<pagination> and <pagination>.hasCurrent) %}`.
  All three are false, and there is no `else`.
- **severity:** UX. **effort:** S. **status:** PR opened.

### #101 — no rate limiting / lockout on `/login` and `/register` — prio 5

- **reproduced:** the account-enumeration half, yes, **measured by code read** at
  `mcritweb/views/authentication.py` — `login()` flashes `'Incorrect username.'` when
  `UserInfo.fromDb` returns `None` and `'Incorrect password.'` when the hash check fails.
  An unauthenticated caller can therefore enumerate valid usernames one request at a time.
- The rate-limiting half is **not** attempted here. It is the larger part of the issue and
  it carries a design decision the issue itself leaves open ("Determine if lockout applies
  per-account (enabling deliberate user denial-of-service) or per-IP only"), plus a
  multi-host correctness question (per-worker SQLite counters). Picking one of those on a
  maintainer's behalf and shipping it is exactly the "if you're unsure, it doesn't ship"
  case. See `work/notes/issue-101.md` for what a fix would have to settle.
- The PR is scoped and titled to the enumeration half, which the issue explicitly calls a
  one-line fix on the same surface.
- **severity:** security. **effort:** S for the shipped half. **status:** PR opened, partial.

### #100 — API tokens: MD5 generation, no rotation — prio 6

- **reproduced:** yes, **by code read**. `hashlib.md5(uuid.uuid4().bytes).hexdigest()` at
  `mcritweb/views/authentication.py:104` and `mcritweb/db.py:575`. Grep for `md5` in
  `mcritweb/` returns exactly those two lines. There is no route that reissues a token —
  `templates/settings.html` shows it with a copy button only.
- The entropy is fine (UUID4); the finding is the algorithm choice and the missing
  rotation path. Both halves are small and fully specified in the issue.
- Hashed-at-rest storage is explicitly sequenced *after* these two by the issue, and is
  left alone.
- **severity:** security. **effort:** M. **status:** PR opened.

### #78 — duplicate entries in search results — prio 7

- **reproduced:** partially.
- The sample path the issue's title names is **already fixed**: `explore.search` collects
  samples into a dict keyed by `sample_id`, with the comment "deduplicate in case we have
  cases such as filename == sha256". So the exact symptom in the (2022) screenshot no
  longer occurs — searching for a sha256 returns one row.
- The **same bug is still present for families and functions**: both append `id_match`
  and then every entry of `search_results` to a plain list with no dedup, so an entry that
  is both the id match and a name match renders twice. **Inferred** from
  `mcritweb/views/explore.py`; the corpus cannot demonstrate it (its function names are
  all empty strings and no family name contains its own id), so the PR carries a unit test
  with a backend built for the overlap.
- **severity:** wrong behaviour. **effort:** S. **status:** PR opened.

### #79 — "Ups, search for `<hash>` ... failed!" — prio 8, not fixed here

- **reproduced:** partially. The message exists at `explore.samples` (and the sibling
  family/function views), and it fires when `client.search_samples(...)` returns `None`,
  i.e. when the **backend call failed** — not when there are simply no results.
- **root cause, inferred, and it is not in this repository:** `mcrit` 1.8.1,
  `MinHashIndex.getSampleSearchResults`, does
  ```python
  if re.match("^[a-fA-F0-9]{64}$", search_term) is not None:
      sample_entry = storage.getSampleBySha256(search_term)
      sha_match = sample_entry.toDict()
  ```
  with no `None` check. Searching for any sha256 that is *not* in the collection raises
  `AttributeError` inside the backend, the client gets an error, `search_samples` answers
  `None`, and MCRITweb faithfully reports "search failed". That is exactly the symptom
  #79 describes. **Not executed** — there is no backend here to run it against; it is a
  source read of the installed `mcrit` 1.8.1 and should be confirmed before being quoted
  as fact upstream.
- Rewording the message in MCRITweb would paper over a genuine backend error. The part
  that *is* MCRITweb's to fix — "nothing matched" being silent — is #54, which is fixed.
- **status:** not fixed. Written up in `work/notes/issue-79.md`.

### #89 — `mcrit_server_required` probes on every request — prio 9, not fixed here

- **reproduced:** by code read. 36 routes carry the decorator
  (`analyze.py` 10, `data.py` 12, `explore.py` 13, `api.py` 1), and each one makes a
  blocking `requests.get` to the backend root before its own work. The result is not
  cached.
- The issue lays out two options and says outright that "the decision belongs to whoever
  owns the error-handling story, not to a drive-by change", and pairs option 2 with #43.
  A TTL cache is a real behaviour change (a backend that just went down keeps looking up
  for the TTL; per-worker in a multi-process deployment) and I am not the owner of that
  call. Left alone deliberately; notes in `work/notes/issue-89.md`.

### #51 — proper sort/search for jobs — prio 10, blocked

- **reproduced:** yes, **measured**, and the issue's own migration note is now out of date.
  It says "templates/jobs.html:143-146 POSTs a `Search` field". At `df53db9` that whole
  block — the `Results for "..."` line and the form — sits inside a Jinja comment
  (`{# ... #}`, `templates/jobs.html:139-148`), so **there is no search box on the jobs
  page at all**. `data.jobs()` still accepts `POST` and still reads `request.form['Search']`
  into a `query` it never uses.
- A working job search needs a search/filter parameter on the backend's `getQueueData`,
  which `mcrit` does not expose. That makes it a backend change first.
- Small adjacent bug noticed: a `POST /data/jobs` without a `Search` field raises
  `BadRequestKeyError` → HTTP 400, because the read is `request.form['Search']` rather
  than `.get`. Unreachable from the UI while the form is commented out. Noted, not fixed.
- **status:** blocked. Notes in `work/notes/issue-51.md`.

### Everything else

The remaining issues are feature requests, refactors, open questions, tracker/meta
issues, or work that belongs to the `mcrit` backend. Each was read in full and its
current state checked against `df53db9`; the ranked table above carries the one-line
verdict. Two groups are worth calling out because "not reproduced" is a *result* there,
not a gap:

- **`mcrit`-owned (#47, #59, #64, #76, #77, #7, and the root cause of #79).** MCRITweb
  holds no analysis logic and `AGENTS.md` forbids changing matching or scoring semantics
  here. Nothing in this repository can fix them.
- **Needs a populated, real backend (#38, #67, #68, #76, #77, #80, #69).** No MongoDB and
  no docker daemon in this environment; the captured corpus is seven samples and five
  finished jobs, which is enough to render pages and nowhere near enough to measure a
  30-second search or to run an export→import cycle.

> **Both of those groupings were re-checked on 2026-08-30 and six of the nine calls
> were wrong.** See the revision below. The originals are left above unedited, because
> the point of this file is to be honest about what I concluded and when.

### Revision, 2026-08-30 — the "can't do this here" set, re-measured

A dedicated research pass measured every issue in the two groups above against the
offline corpus. Correcting the record:

| # | old call | corrected call | the measurement that settles it |
|---|---|---|---|
| #38 | needs backend | **tractable here, S–M** | 4 of 5 statistics fields recompute *exactly* from `MatchingResult.function_matches`, already on the page. The win.dridex view states 756 functions / 151 KB when the honest answer for that filter is 4 / 249 bytes. Only `num_self_matches` is unavailable (the backend drops self-matches). |
| #68 | can't measure here | **tractable here, M** | `create_match_diagram` is synchronous before `render_template`: **275 ms of a 303 ms first view (91%)**. The `<img>` seam to move it behind already exists. Separately the report aggregation runs twice per request, first result discarded — 3 one-line edits, 13–26% off every warm render. |
| #69 | needs click-through | **tractable here, M** | Click-through done in headless Chromium. Four client-side defects: `showCycles()` throws (`g` is `null`; the duo loader uses `g_a`/`g_b`), `Show Loops` never wired, `loopsObj` is one global written by two racing XHRs, `nodesAll` is one offset-keyed dict so the panels collide. The server half is correct — 200/200 functions cross-checked against networkx dominators. |
| #80 | can't | **partly tractable, S** | The reported ~120-char clipboard truncation does **not** reproduce (5613 chars copy intact). Two other real defects do: the copy reads `.html()` not `.val()` so user edits are discarded, and `&`/`<`/`>` copy as entities. Sample-version column costs one backend call. |
| #77 | needs a large real DB | **tractable here, S** | Found with a call counter on a 17-job corpus: `explore.py:168` calls `getQueueData()` with no args, and `limit=0` omits the limit — every sample-list/search view downloads the **whole queue**. At 8500 jobs: 8 MB transferred and parsed, ~166 ms of mcritweb CPU, to annotate 25 rows. |
| #76 | mcrit | **core is mcrit; a real half is here** | The scan is genuinely the backend's. But `explore.search` runs all three searches sequentially by default, so a 30 s function scan is charged to a user who only wanted a family hit. |
| #64 | mcrit | **mcrit, plus one line here** | `explore.py:195` has `FunctionEntry.fromDict` commented out while `explore.search` deserialises properly. Latent today (Jinja falls back to item lookup and the keys match), breaks on any future rename. |
| #47 | mcrit | **confirmed mcrit** | `mongoqueue.py:489` picks the newest *non-terminated* job with attempts left, so a still-running force-rematch shadows an older finished one. One query. |
| #59 | mcrit | **confirmed mcrit** | `_createIndices` creates only single-field indexes. Worth adding to the issue: mcritweb's sortable function headers offer exactly the three fields with no index at all (`offset`, `num_instructions`, `num_blocks`). |

Ranked work queue coming out of that pass: **#69**, **#68(a)**, **#77**, **#38**,
**#68(b)**, **#80**, **#76**, **#64**. #47 and #59 get a comment naming the exact
function and nothing else.

### Revision, 2026-08-30 — the twelve `wait`-labelled issues

- **#44** — the code already does the **opposite** of what the issue asks: `'dump' in
  filename` matches `dedumped`, so a de-dumped file pre-fills as "Dumped" with an empty
  base address, and submitting it **500s** in both submit paths (`ValueError: invalid
  literal for int() with base 16: ''`). ~4 lines. Highest value-per-line outstanding.
- **#48** — close. A minifier saves 1.1 KB gzipped against a 1.9 MB page load; HTML is
  1.9–10.6% of page weight. The payload problem is 1.14 MB of vendored JS per page.
- **#42** — sub-question (a) is **already implemented** (`result_cross.html:191`).
- **#46** — a cross-compare that took 8.06 s reports `0:00:00`; the parent job does not
  start until its children finish. `finished_at - created_at` is two lines.
- **#50** — 85 of 88 lines byte-identical between two of five hand-rolled result
  tables; 204 `column_type` branches over 935 lines. Extract into a **new**
  `table/match_row.html` — that choice is what keeps it off the contended surface.
- **#7** — arithmetic is the backend's, but mcritweb truncates for display
  (`"%3d"|format` on a float), so 1.04 and 0.86 render as `1` and `0`. In scope.
- **#57/#51** — the jobs search box is commented out while the POST handler survives
  and 400s. And wiring `filter=` would ship a broken feature: the backend filters
  *after* paging, so you get "page 3 of 40, showing 2 results".
- **#60 (htmx)**, **#70 (dark mode)**, **#37**, **#67**, **#74** — proposals recorded in
  `work/LOG.md`; #70 in particular is much larger than the issue implies (Bootstrap
  5.0.2 has no `data-bs-theme`; `ScoreColorProvider` blends toward 255 so the heat-map
  inverts in meaning on a dark ground; the cached diagram PNGs are baked on white).

---

## Cross-cutting defect, closed on every open PR (2026-08-30)

Not an upstream issue — a defect in my own branches, found by Codex reviewing PR #26.

`make init` installed only `requirements.txt`, which names no pytest; `mcrit` declares
`pytest` under a `dev` extra that `mcrit>=1.5.3` never requests. So `make test` on a
fresh checkout failed with `No module named pytest`. I had fixed this once on
`fix/ci-install-pytest` (PR #9) and then cherry-picked the *older* commit onto every
other branch, so it was live in 23 of my 24 open PRs.

Ported the corrected `Makefile` and `AGENTS.md` to all 23 — one plain commit each, no
force-push. Pre-push verification also caught four local branches (52, 61, 78, 98) that
were a commit behind their remotes and would have reintroduced `work/harness/cookies.txt`;
those were reset to their remotes and rebuilt.

Severity: blocks a contributor's first `make test`. Effort: S. Status: **closed on all
24 branches.**

---

## #72 — allow modifying functions: blocked upstream, with evidence

This one cannot be done in mcritweb, and the reason was checked at three layers of the
installed `mcrit` **1.8.1** — which is also the newest release on PyPI (1.6.1, 1.6.2,
1.7.0, 1.7.1, 1.8.0, 1.8.1), so this is not a "bump the dependency" problem.
`mcritweb` pins `mcrit>=1.5.3`.

1. **`McritClient` has no function-mutating call.** Its entire `### Functions ###`
   section is getters: `getFunctionsBySampleId`, `getFunctions`, `getFunctionsByIds`,
   `isFunctionId`, `getFunctionById`. The mutating HTTP calls in the whole client are
   `POST /respawn`, `POST /samples`, `POST /samples/binary`, `PUT /families/{id}`,
   `DELETE /families/{id}`, `PUT /samples/{id}`, `DELETE /samples/{id}`,
   `DELETE /jobs*`, `POST /import` — plus `POST /functions`, which is
   `getFunctionsByIds`, a **read** that uses POST only because the id list travels in
   the body.
2. **The server exposes no route.** `mcrit/server/FunctionResource.py` defines
   `on_get`, `on_post_collection`, `on_get_collection` — no `on_put`, `on_patch` or
   `on_delete` — so a `PUT /functions/{id}` would answer 405.
3. **The business layer has no such operation.** Every function method on
   `MinHashIndex` is a read, and its own docstring listing the operations that "need
   to be jobs to ensure database consistency" names exactly `deleteSample`,
   `deleteFamily`, `modifyFamily`, `modifySample`. Functions are deliberately absent.

The near-miss is `StorageInterface.updateFunctionLabels(smda_report, username)`, which
is called only from inside `MinHashIndex.addReport`. It fires when a *whole sample* is
submitted, takes a full `SmdaReport`, **appends** a `FunctionLabelEntry` rather than
changing `FunctionEntry.function_name`, and is unreachable from `McritClient` except by
re-uploading the entire sample — which mcritweb already offers as `data.submit`. It is
not a per-function modify.

**What upstream `fkie-cad/mcrit` would need**, mirroring the sample path:

1. `MinHashIndex.modifyFunction(function_id, update_information)` plus a storage method
   that writes `function_name` / `function_labels`, added to the job-redirected set
   alongside `modifySample`;
2. `FunctionResource.on_put` handling `PUT /functions/{function_id:int}` — the route
   already exists for GET, so only the handler is needed;
3. `McritClient.modifyFunction(...)` issuing that PUT, shaped like `modifySample`.

Until at least (3) exists, any mcritweb form would post to a route whose only possible
implementation calls a method that does not exist. **No PR is opened for #72 on
purpose**: a form that cannot work is worse than none, and tests for it would assert a
fiction — `RecordingMcritClient` will happily record a call the real client cannot make.

**Caveat, stated:** `fkie-cad/mcrit`'s unreleased branch could not be read from here
(the org is unreachable through this proxy). The evidence above is the newest published
release. The three-layer list is the checklist to re-verify against if that changes.


## A note for the next coverage audit

Matching triaged issues against `fix/<n>-*` branch names finds one apparent gap, **#76**,
and it is a naming artefact rather than a gap. Its mcritweb half - `/explore/search`
defaulting to all three types, so a navbar search charges every user a function scan they
did not ask for - ships on `fix/77-explore-page-backend-calls` as `DEFAULT_SEARCH_TYPES`,
with a comment at `explore.py:429-434` naming #76. The scan's own cost is `mcrit`'s.

So all 54 triaged issues are covered by a branch; several branches carry more than one
issue, and one issue's fix lives under another issue's branch name. Audit by reading the
branches, not by counting them.
