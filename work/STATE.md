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
| 35 | 15 | "Analyze" on a function row starts a 1vsN for the parent *sample* | **yes** (code) | wrong behaviour | L | not started — needs a function-analysis flow that does not exist |
| 66 | 16 | Import page gives no progress indication | no | UX | M | **in progress** (worktree agent) |
| 99 | 17 | Result template rendering only covered for five report types | n/a (meta) | — | L | PR opened — [#26](https://github.com/r0ny123/mcritweb/pull/26) |
| 93 | 18 | Configurable Unique Blocks page under Analyze | n/a (feature) | — | L | not started |
| 80 | 19 | Block isolation table improvements | can't | — | M | not started |
| 75 | 20 | Export raw results as JSON | n/a (feature) | — | M | PR opened — [#24](https://github.com/r0ny123/mcritweb/pull/24) |
| 72 | 21 | Allow modifying functions (samples/families already possible) | n/a (feature) | — | L | not started |
| 69 | 22 | FunctionVs: loop visualization correctness | can't (needs click-through) | — | M | not started |
| 55 | 23 | "Rerun job" button | n/a (feature) | — | M | **in progress** (worktree agent) |
| 58 | 24 | Search should remember last sort order | n/a (feature) | — | M | **in progress** (worktree agent) |
| 56 | 25 | Mark id/SHA matches in search (blocked on #53) | n/a (feature) | — | M | not started |
| 53 | 26 | Special triggers for rows in table rendering | n/a (feature) | — | M | not started |
| 50 | 27 | Table widgets for result-page tables | n/a (refactor) | — | L | not started |
| 45 | 28 | Mark the search term in results | n/a (feature, labelled `wait`) | — | M | **in progress** (worktree agent — XSS-sensitive) |
| 48 | 29 | Minify/prettify HTML | n/a (feature) | — | M | not started |
| 63 | 30 | Optimize browser performance (render-blocking JS) | can't measure here | — | L | not started |
| 62 | 31 | Preload navbar icons | **yes** (measured with headless Chromium) | UX | S | PR opened — [#17](https://github.com/r0ny123/mcritweb/pull/17) |
| 60 | 32 | Consider htmx for table reload + pagination | n/a (refactor) | — | L | not started |
| 68 | 33 | Improve MatchingResults performance | can't measure here | — | L | not started |
| 67 | 34 | Investigate export→import bugs | can't (needs a real backend) | — | L | not started |
| 40 | 35 | Polish query matching results (filename missing, job name) | partially | — | M | **in progress** (worktree agent) |
| 39 | 36 | Inconsistent names between job and result - six headings render *empty* | **yes** (measured) | wrong behaviour | M | PR opened — [#19](https://github.com/r0ny123/mcritweb/pull/19) |
| 38 | 37 | Filter 'Matching Method Statistics' with the result | can't (needs backend) | — | M | not started |
| 36 | 38 | Job list tabs do not change the URL, so back/refresh lose the tab | partially | wrong behaviour | M | **in progress** (worktree agent) |
| 34 | 39 | Improve function pages (accordion, minhash flag, analyze button, shingles) | n/a (feature) | — | L | not started |
| 32 | 40 | Show the MinHash matching parameter in job results | n/a (feature) | — | M | PR opened — [#25](https://github.com/r0ny123/mcritweb/pull/25) |
| 9 | 41 | Promote a query to a full sample | n/a (feature) | — | L | not started |
| 42 | 42 | How to handle clustered sample sequences in cross compare (open question) | n/a (question) | — | — | not started |
| 44 | 43 | Treat "dedumped" filenames as unmapped? (open question) | n/a (question) | — | — | not started |
| 43 | 44 | Handle all kinds of errors from McritClient | n/a (design) | — | L | not started |
| 37 | 45 | Annotate jobs with user uuids (labelled `wait`) | n/a (feature) | — | L | not started |
| 46 | 46 | Cross job duration/progress is meaningless (labelled `wait`) | can't (backend) | — | M | not started |
| 47 | 47 | Queue result cache destroyed by force rematch | can't (backend) | — | M | not started — `mcrit` issue |
| 57 | 48 | META: Jobs (tracker) | n/a (meta) | — | — | not started |
| 59 | 49 | Compound index for search | can't (backend) | — | M | not started — `mcrit` issue |
| 64 | 50 | McritClient should return objects | can't (backend) | — | M | not started — `mcrit` issue |
| 70 | 51 | Dark mode (labelled `wait`) | n/a (feature) | — | L | not started |
| 74 | 52 | FunctionVs: graph sync, combined view | n/a (feature) | — | L | not started |
| 76 | 53 | Function search ~30s when nothing matches | can't (needs a large real DB) | — | ? | not started — `mcrit` issue |
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
