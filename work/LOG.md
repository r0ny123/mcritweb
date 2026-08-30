# Work log — mcritweb issue triage & fixes

Append-only. Newest entries at the bottom. Timestamps are UTC.

## Conventions for whoever picks this up

- Repo under work: `/home/user/mcritweb`, remote `origin` = `https://github.com/r0ny123/mcritweb` (the fork).
  Upstream `fkie-cad/mcritweb` is **read-only** here: the session's GitHub API scope is the fork
  only, and `add_repo --access push` for upstream was refused. Upstream issues are therefore read
  through `WebFetch` against the public HTML pages, not through the API.
- All PRs go to `r0ny123/mcritweb`, base `master`. Never upstream.
- Branch naming: `fix/<issue-number>-<short-slug>`.
- `work/STATE.md` is the live triage table. `work/SETUP.md` is the reproduction environment.

---

## 2026-08-29T19:43Z — session start

Cloned working tree already present at `/home/user/mcritweb` on branch
`claude/mcritweb-triage-fixes-a5adho` (clean, at df53db9 "adjusted README").

Read `README.md`, `AGENTS.md`, `CONTEXT.md`, `Makefile`, `ruff.toml`, `pytest.ini`,
`.github/workflows/test.yml`, `docs/agents/*`. Key constraints taken from AGENTS.md:

- `ruff check .` and `python -m pytest` are exactly what CI runs. No formatter; do not reformat.
- `@bp.route` must be the outermost decorator; every route needs a row in `tests/routePolicy.py`.
- Writing routes must be POST-only (the five `analyze` job submitters are the documented exception).
- Every non-safe method needs a CSRF token; `|safe` inside a `<script>` block is a test failure.
- Do not bump the version, do not touch vendored `static/` assets (except the deliberately
  patched `static/dropzone.js`), do not change matching/scoring semantics.
- Migrated issues carry a `<sub>Migrated from ...</sub>` footer: the GitHub creation date is the
  migration date (2026-08-04 for most), not the filing date.

### Decision: where the issues live

`r0ny123/mcritweb` has **0 open issues** and 1 open PR (#1 "Scan for typos and logic errors",
head `cursor/scan-for-typos-and-logic-errors-befc`). The backlog the task refers to is upstream
on `fkie-cad/mcritweb` (54 open issues). Attempts, in order:

1. `mcp__github__list_issues` on `fkie-cad/mcritweb` → "Access denied: repository not configured
   for this session. Allowed repositories: r0ny123/mcritweb".
2. `add_repo(fkie-cad/mcritweb, access=read)` → repo is public, git reads already work, but the
   answer states GitHub API tools do not cover unattached repositories.
3. `add_repo(fkie-cad/mcritweb, access=push)` → denied by the permission classifier.
4. `curl https://api.github.com/...` → denied by the permission classifier.
5. `WebFetch https://api.github.com/repos/fkie-cad/mcritweb/issues?...` → HTTP 403.
6. `WebFetch https://github.com/fkie-cad/mcritweb/issues` → **works**.

So: issue bodies come from the public HTML via WebFetch. Noted limitation — WebFetch's page
conversion truncates a 25-row issue list to ~12 rows, so the full open-issue set had to be
reconstructed by fetching the list under both `sort:created-desc` and `sort:created-asc`
across pages and taking the union, then probing the remaining number gaps individually.

---

## 2026-08-29T19:48Z — environment

Full details in `work/SETUP.md`. Summary of what was established:

- `pip install -r requirements.txt` under the **system** pip fails building `picblocks`
  (a transitive dep of `mcrit`): Debian's patched setuptools raises
  `AttributeError: install_layout` during the wheel build. A venv with current
  setuptools builds it. Decision: work in `.venv` (gitignored), and a second `.venv313`
  on Python 3.13 because two of the issues are about deprecations that only fire there.
- Baseline: `239 passed` / `All checks passed!` on 3.11. Same suite on 3.13:
  `239 passed, 405 warnings`.
- `flask run` boots and serves `/register`. No MongoDB and **no docker daemon**
  (`docker info` → `failed to connect to the docker API at unix:///var/run/docker.sock`),
  so a real mcrit backend cannot be brought up here.
- Decision: rather than call the whole backlog unreproducible, use the project's own
  offline backend. `tests/fixtureData.CorpusMcritClient` serves real captured reports
  and `create_app` exposes the seam (`MCRIT_CLIENT_FACTORY`, `MCRIT_SERVER_PROBE`).
  `work/harness/devserver.py` wires those behind a normal HTTP server, so pages can be
  walked with curl. This is what nearly every reproduction below ran against.
  Its limits are written down in `work/SETUP.md` — mcrit's `field:value` parser, its
  cursor encoding and anything timing-related still need a real backend.

## 2026-08-29T19:50Z — triage complete

All 54 open issues read and recorded in `work/STATE.md`. Notes on the process:

- WebFetch truncates a 25-row GitHub issue list to ~12 rows, so the open set was
  rebuilt from six list fetches (`sort:created-desc` and `sort:created-asc`, pages 1-3,
  plus `sort:updated-asc`) unioned, then the remaining number gaps probed individually.
  #49 and #71 turned out to be **closed** (they appeared in no listing); #45, #46, #47
  and #74 are open and were only found by probing. Final count 54, which matches
  GitHub's own header exactly — that equality is the check that nothing was missed.
- The open PR on the fork, r0ny123/mcritweb#1 "Scan for typos and logic errors", is
  **stale**: its base is `5dbf5ae`, `mergeable_state` is `dirty`, and most of what it
  contains has since landed independently (`params.py` split out of `utility.py`, the
  `setup.py` missing comma fixed in v1.4.2, the `testPagination` import path). Nothing
  I am working on overlaps it. Not built on: rebasing someone else's three commits onto
  a year of movement is a bigger job than the two lines still relevant.

## 2026-08-29T20:05Z — PR 1 of N: the linkhunt 500 (no issue number)

Found while reading `data.py` for #73. `/data/linkhunt/<job_id>` dispatches on
`job_info.parameters` through an `if/elif` with no `else`, so any job type that is not
one of the four matching methods returns `None` from the view → Flask 500.

Measured, against the harness:

```
$ curl -s -o /dev/null -w "%{http_code}\n" --noproxy '*' -b cookies.txt \
    http://127.0.0.1:5001/data/linkhunt/6a7465f2f8b8d2c6f83664cd   # cross compare
500
$ ... /data/linkhunt/6a74660af8b8d2c6f83664f1                      # unique blocks
500
```

```
TypeError: The view function for 'data.linkhunt' did not return a valid response.
The function either returned None or ended without a return statement.
```

`result_incompatible.html` exists for exactly this case and was wired to the wrong
branch — the `else` that means "job id unknown". Fixed both; three regression tests,
all three fail on master. Full suite 242 passed on 3.11 and 3.13, ruff clean.

**Decision:** shipped as its own PR rather than folded into #73, because it is a crash,
it is unrelated to what #73 describes, and one PR per concern keeps the diffs
reviewable. Not filed as an upstream issue — the task's guardrails put PRs on the fork
only, and filing upstream was not asked for.

→ https://github.com/r0ny123/mcritweb/pull/2

## 2026-08-29T20:20Z — PR 2: issue #73

Reproduced exactly as the issue's migration note describes. `data.result` opens with
`if result_json:` and `{}` is falsy, so a finished job with an empty report skips the
dispatch, fails the "not finished" guard, and renders `result_invalid.html`.

Measured, before and after, same script:

```
BEFORE  finished job, empty report      -> HTTP 200: Job ID: ... or the result referenced by this job was not found in the system.
AFTER   finished job, empty report      -> HTTP 200: Job ID: ... does not contain any data.
```

The same script's second case killed the *before* run outright:

```
TypeError: The view function for 'data.result' did not return a valid response.
```

— `data.result`'s dispatch chain has no `else` either. Nothing reaches it today (the
chain covers every method in `Job.method_types`), so it is forward protection. Added
in the same PR because the restructured tail sits directly under it.

**Decision (self-review round 1):** the original condition was
`not (is_finished or is_failed or is_terminated)`, which short-circuits. My first draft
reordered the checks; caught on review that a job which is *both* finished and failed
would change answer. Reordered so failed/terminated is checked first, preserving it.
Round 2 produced no findings.

→ https://github.com/r0ny123/mcritweb/pull/3

## 2026-08-29T20:40Z — PR 3: issue #98

Measured: `239 passed, 405 warnings` on Python 3.13 → `248 passed, 1 warning` after
(the remaining one is pytest's own, about a `parametrize` generator in `testCsrf.py`).
Four sites, not the two the issue lists — it misses `authentication.py:142`.

The trap the issue warns about, made concrete: sqlite3's implicit adapter writes
`isoformat(" ")`, which for an **aware** datetime appends `+00:00`, and `fromDb`
parses with `"%Y-%m-%d %H:%M:%S.%f"`. A mechanical `utcnow()` → `now(timezone.utc)`
swap alone would have made every row this version writes unreadable.

**Bug found while checking that**, older than either deprecation: `isoformat(" ")`
drops the fractional part when the microsecond is exactly 0, so a user registered on
that microsecond can never be read back — every page 500s for that account. Measured:

```
stored value: '2026-01-01 00:00:00'
reading that user back: ValueError: time data '2026-01-01 00:00:00' does not match format '%Y-%m-%d %H:%M:%S.%f'
```

Fixed by formatting the INSERT explicitly (same format the UPDATE path already used,
so the stored text is byte-identical and no migration is needed) and accepting both
shapes on read, so already-written rows heal.

**Decision:** `ruff` rejected `datetime.timezone.utc` under `UP017` and demands
`datetime.UTC`, which needs Python 3.11. Took the linter's answer — 3.11 is the bottom
of the CI matrix and AGENTS.md says to target 3.11/3.12 — and flagged in the PR that
this makes the README's "Python 3.8+" formally untrue, with the one-line alternative
spelled out for the maintainer.

→ https://github.com/r0ny123/mcritweb/pull/4

## 2026-08-29T21:00Z — PR 4: issue #54

Measured: `/explore/search?query=zzzznomatchzzzz` returns 200 with the heading, the
form, and nothing else.

**Decision (self-review round 1):** the first draft showed "Nothing matched ..." purely
on "no rows rendered". But `search()` treats a backend that answered `None` as a
*failed* search and flashes an error — and that page has no rows either, so the message
would have fired on top of the error and made a wrong claim. Added a `search_failed`
flag threaded from the view. That is why the PR touches `explore.py`, not only the
template.

**Mistake worth recording:** the first attempt at that edit used
`str.replace` on a pattern (`if results is None:` + the flash line) that also occurs in
`family_by_id` and `sample_by_id`, and inserted `search_failed = True` into two views
that have no such variable — a guaranteed `NameError`. Caught by reading the diff
before running anything. Redone by partitioning the file at `def search():` and
asserting `count(...) == 1` for every replacement. Lesson for the next session: assert
the occurrence count on every textual patch.

Five tests, one of which fails on master; the other four are the guards a
one-flag-over-three-sections change needs, including one asserting the echoed search
term is escaped.

→ https://github.com/r0ny123/mcritweb/pull/5

## 2026-08-29T21:20Z — PR 5: issue #101 (enumeration half)

`/login` said `'Incorrect username.'` or `'Incorrect password.'`. Measured, before:

```
existing account   median  101.4 ms   message: ...Incorrect password.
no such account    median    1.8 ms   message: ...Incorrect username.
```

**Decision:** shipped the timing fix alongside the message. A message-only fix would
have *looked* closed while leaving a 56x timing oracle on the same endpoint — the two
numbers above are from this codebase, not from a textbook. An absent username now
costs a `check_password_hash` against a hash of a random secret. After: ~101 ms both
ways, one message both ways.

**Decision:** the rate limiting the issue is titled for is **not** shipped. The issue
itself leaves the deciding question open ("per-account, enabling deliberate user
denial-of-service, or per-IP only"), and two more it does not raise — where the counter
lives, and that `request.remote_addr` behind NGINX is the proxy — are deployment
decisions. Written up in `work/notes/issue-101.md`. PR title and body scope it to the
half that shipped.

**Self-review round 1** removed a test that asserted `elapsed > 0`, i.e. one that could
never fail. The timing claim is asserted by counting `check_password_hash` calls
instead — same claim, no wall-clock flake on a shared runner.

→ https://github.com/r0ny123/mcritweb/pull/6

## 2026-08-29T21:40Z — PR 6: issue #100

Both halves the issue asks for. `hashlib.md5(uuid.uuid4().bytes).hexdigest()` at two
call sites → one `db.generate_apitoken()` = `secrets.token_hex(32)`. New POST-only
`admin.regenerate_apitoken`, reached from a `data-post` button, with a `routePolicy`
row. Verified live:

```
POST /admin/regenerate_apitoken -> 302 ; token becomes a303356d...6342 (64 hex)
GET  /admin/regenerate_apitoken -> 405
POST without a CSRF token       -> 400
```

**Decision:** installed a test asserting a legacy 32-char md5 token still
authenticates, because the risk of this change is somebody later adding a length check
and locking out every pre-existing token.

**Also fixed in the same commit:** the v0.12.0 backfill migration printed each token it
generated to stdout — a live credential in the container log of every instance that
upgraded through that version. Same call site, same issue.

**Not done:** hashed-at-rest storage, which the issue explicitly sequences after these.

→ https://github.com/r0ny123/mcritweb/pull/7

## 2026-08-29T21:55Z — PR 7: issue #78

The sample path the issue's title names is **already fixed** (deduplicated by
`sample_id`). Families and functions still appended `id_match` and then every
`search_results` entry to a plain list.

**Decision:** rather than close #78 as fixed, apply the same fix to the two branches
that were left behind, and say plainly in the PR that the reported symptom is the one
that no longer occurs. The corpus cannot render the duplicate (its function names are
empty strings, no family name contains its own id), so the tests build a backend that
returns the same entry in both fields — which is exactly what mcrit does.

**Self-review:** a dedup that also dropped distinct rows would pass every "appears
once" test, so there is a fifth test asserting a multi-hit query still lists every row.

→ https://github.com/r0ny123/mcritweb/pull/8

## 2026-08-29T22:05Z — CI was red on every PR, and it was not the PRs

All seven PRs came back with every `Unit tests (Python 3.x)` job failing:

```
/opt/hostedtoolcache/Python/3.11.16/x64/bin/python: No module named pytest
##[error]Process completed with exit code 1
```

Ruff green throughout, which is what makes this look like a working pipeline.

Root cause, measured:

```
$ python -c "import importlib.metadata as m; print([r for r in m.requires('mcrit') if 'pytest' in r])"
['pytest; extra == "dev"', 'pytest-cov; extra == "dev"']
```

The Makefile said "pytest and pytest-cov arrive with mcrit, so requirements.txt covers
both". They no longer do. The suite has not run in CI since mcrit moved them behind the
`dev` extra. (The same thing bit me locally at 19:50 — I installed pytest by hand and
did not stop to ask why, which I should have.)

**Decision:** this is a base-branch failure, not any PR's, and no fix for it existed —
so I wrote one (PR #9: install pytest pinned in the workflow, like ruff already is,
rather than adding a test dependency to the runtime `requirements.txt`), and
cherry-picked that same commit onto all seven branches so their CI can run before it
merges. It no-ops once master carries it. One comment on each PR saying so. PR #9 is
green on all four interpreters.

## 2026-08-29T22:15Z — not fixed, written up instead

- `work/notes/issue-79.md` — the "Ups, search failed!" message is not mis-worded; it
  fires on a failed backend call. The reason a sha256 lookup produces it looks like an
  unchecked `None` in `mcrit`'s `MinHashIndex.getSampleSearchResults`. **Inferred from
  source, not executed** — there is no backend here. Softening the wording in MCRITweb
  would hide a real error, so nothing shipped.
- `work/notes/issue-89.md` — the probe. The issue says the decision belongs to the
  error-handling owner and it is right; `MCRIT_SERVER_PROBE` already lets an operator
  install a caching probe from `instance/config.py` without touching the decorator,
  and the note carries that recipe.
- `work/notes/issue-51.md` — job search. The issue's migration note has drifted: the
  search form is inside a `{# ... #}` comment, so there is no search box at all. A
  working one needs a filter parameter on `getQueueData`, which is a `mcrit` change.

## 2026-08-29T20:51Z — CI green on all eight PRs

The queued webhook backlog (79 events) was entirely CI failures on **pre-fix heads** —
`f2ab1aa`, `f1c247f`, `6e94552`, `2be4587`, `d013a09`, `c829473`, `3a3b2b9` — i.e. the
commits before the CI fix was cherry-picked onto each branch, plus CodeRabbit's
"Review skipped, auto reviews are disabled on this repository" notices, which need no
action. Nothing in the backlog was a finding.

On the current heads, every completed check is `success`:

| PR | head | Ruff | 3.11 | 3.12 | 3.13 | 3.14 |
|---|---|---|---|---|---|---|
| #9 | 8268666 | ok | ok | ok | ok | ok |
| #2 | 6b35e1e | ok | ok | ok | ok | ok |
| #3 | 5439350 | ok | ok | ok | ok | ok |
| #4 | 2120c23 | ok | ok | ok | ok | ok |
| #5 | 812ff8a | ok | ok | ok | ok | ok |
| #6 | 0bd417d | ok | ok | ok | ok | ok |
| #7 | 65168d0 | ok | ok | ok | ok | ok |
| #8 | 8b240b9 | ok | ok | ok | ok | ok |

(A handful of duplicate jobs from the paired push/pull_request runs were still queued at
the time of writing; no job on any post-fix head has failed.)

A self check-in is scheduled hourly (`trig_01TBQpE69HGB2HUCmwkEkttN`) to re-check the
eight PRs until they are merged or closed: any new failure is a real one, since the
base-branch failure is now accounted for. It re-arms silently when nothing has changed.

**Note for the next session:** the CI failure is the single most consequential thing
found today, and it was invisible from the inside — Ruff stayed green throughout, so the
pipeline read as healthy while the suite had not executed a line since `mcrit` moved
pytest behind its `dev` extra. Worth checking, on any repo, that a green pipeline is
actually running the tests it claims to.

---

## 2026-08-30T02:20Z — user redirected: work every issue until each has a PR

`/goal`: "work on all the issues ... until every issue has a PR", and separately:
"address all the codex review findings in each PR as those lands".

Consequences for the plan in `work/SUMMARY.md`:

- The original brief said feature requests come "last or not at all". That is
  superseded: work down the ranked table and open a PR per issue.
- The PR check-in routine now also reads reviews and review comments on every PR each
  hour and treats a Codex finding as a bug report - verify, fix, push, reply, resolve.
  As of 02:20Z no review has landed on any PR; the only comments are CodeRabbit's
  "Review skipped - auto reviews are disabled on this repository", which needs none.

## 2026-08-30T02:00-02:20Z — PRs 8-14

Same method throughout: reproduce, failing-first test where the setup allows it,
minimal fix, self-review to zero findings, `pytest` + `ruff` green, PR with
before/after.

- **#79** → PR #10. Reworded the failure, and gave a SHA-256 a real answer:
  `getSampleBySha256` is a different endpoint from the search, so it still answers
  when the search cannot. Measured before/after in the PR. Also **corrected my own
  earlier triage**: I had marked this "not fixable here" because the root cause is in
  mcrit. The message *was* still MCRITweb's to fix, and the direct lookup delivers
  exactly what the issue asked for.
- **#89** → PR #11. TTL cache on the reachability probe, default 5s, `0` restores the
  old behaviour exactly. Measured: 8 page loads, 8 round-trips before, 1 after.
  **The suite caught a real bug in my first draft**: a module-global cache leaked
  between tests and broke `testFixtures.py::test_backend_check_still_applies_to_authorized_users`,
  which passed alone and failed in the suite. `create_app` now clears it, and a test
  pins that.
- **#51** → PR #12. **My triage was wrong**: I recorded it as blocked on a backend
  change, but `McritClient.getQueueData` already takes a `filter` string. The search
  box is back (as a GET) and the term reaches the backend. The genuinely-blocked part
  is narrower than I said: mcrit filters *after* slicing, so the counts stay
  unfiltered. Written at the call site and in the PR.
- **#52** → PR #13, **#41** → PR #14. Both screenshot-only issues, and I say so in the
  PRs: no browser here, so I reproduced the *mechanism* in the markup and the tests
  pin the plumbing rather than the pixels. The two want opposite behaviour (headings
  and buttons must not wrap; job descriptions must) and their CSS is deliberately
  placed in different parts of `style.css` so the branches do not conflict.
- **#61** → PR #15. 20 undeclared assignments across 8 templates, now a ratchet test.
  **The one that needed reading rather than a sed**: `families_ac` is top-level in two
  script blocks that land on the same page, so `const` there would have been a
  SyntaxError on four pages - a "tidy-up" that breaks them. It stays `var`.
- **#65** → PR #16. The empty-state message becomes the caller's to choose, defaulting
  to today's text; 11 of 13 tests fail on master.

---

## 2026-08-30 02:30-02:45Z — #62, and a stray file found in every open PR

### #62 (preload navbar icons) → PR [#17](https://github.com/r0ny123/mcritweb/pull/17)

The issue has a title and no body ("Preload icons in navbar -> explore", migrated from
the old private repo). So the first job was to establish there is a real symptom rather
than guess at one.

**Measured, not inferred.** Chromium is preinstalled in this environment
(`/opt/pw-browsers/chromium-1194/chrome-linux/chrome`); `pip install playwright` with
`PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1` gets the driver without a download. Driving the
corpus harness with it and recording the request waterfall of `/`:

```
 1. +   19ms  stylesheet  bootstrap.css      <- 7 stylesheets, 8 scripts, 2 logos
...                                              all go out in one burst
18. +   25ms  script      dropzone.js
19. +  159ms  font        fa-solid-900.woff2  <<< 145ms after the last of them
```

Same shape at 1280x800 (last script +203 ms, font +355 ms). The cause is that a font is
invisible to the preload scanner - it is named inside `all.css`, not in the HTML, so it
is only fetched once that sheet is parsed *and* layout finds an element drawing with it.
`all.css` sets `font-display: block`, so every `fa-` icon is a blank box until then.

Fix is one `<link rel="preload" as="font" type="font/woff2" crossorigin>` in `base.html`.
After: the font is request #1 at +13 ms, still fetched exactly once.

**The trap, and why there is a test for it.** `crossorigin` is not decoration. Fonts are
fetched in CORS mode even same-origin, so without it the preload does not match the
CSS-driven fetch. I removed the attribute and re-measured to check rather than assert it:
two requests for the same 150 KB, +221 ms and +400 ms. `tests/testIconPreload.py` pins it.

Only the solid face is preloaded. `base.html`'s help icon sits outside the
`{% if g.user %}` block, so the solid face is drawn on every page including `/login`
(checked); the regular face is three copy buttons, brands and v4compat are unused.
Preloading those would waste the transfer and log a console warning. There is a test
asserting the premise ("base.html still draws a solid icon on every page") so that if the
help icon ever goes, the unconditional preload gets reconsidered rather than silently
becoming dead weight. 4 of 5 tests fail on master; the 5th is that premise guard and
passes there by design. `244 passed` on 3.11 and 3.13, ruff clean.

### The stray file — a real finding, and mine

Cherry-picking the CI fix onto the #62 branch aborted:

```
error: The following untracked working tree files would be overwritten by merge:
	work/harness/cookies.txt
```

`git show --stat 8268666` showed why: **the CI-fix commit committed
`work/harness/cookies.txt`**, a cookie jar my own harness writes. And because that commit
was cherry-picked onto every fix branch, `git ls-tree` confirmed the file was sitting in
**all 15 pushed branches**, i.e. in every open PR.

What it actually contains: a Flask session cookie for `user_id 1`, signed with
`harness-secret` — a string hardcoded in `work/harness/devserver.py` — against a
throwaway SQLite database in `/tmp`. So it is not a credential for anything real. But the
guardrail says *never commit secrets, tokens, or anything from a local `.env`*, and this
is exactly that shape: a session token, in a diff that has no business containing one, in
15 PRs a reviewer is being asked to read. It stays out on both counts.

**How it was removed.** Not by rewriting the branches — the guardrail forbids force-push
and history rewriting, and these branches have open PRs pointing at them. One ordinary
commit per branch deleting the file, 16 branches including the CI source branch so future
cherry-picks stay clean. Verified afterwards with `git ls-tree -r --name-only` across
every `origin/fix/*`: 0 hits everywhere.

**How it got in and what stops a recurrence.** The `git add` for the CI commit was made
from a working tree that had the harness cookie sitting in an untracked `work/` on a
branch where `work/.gitignore` (which does cover it) is not present — that file only
exists on `claude/mcritweb-triage-fixes-a5adho`. The harness now writes its cookie jar to
the scratchpad via `--cookie-file` rather than into the repo, so there is nothing to pick
up. Rule for the rest of this run: **read `git show --stat` of every commit before
pushing it**, not just the diff of the files I meant to touch.

This is the second time a mistake of mine was caught by reading rather than by a test
(the first was the #54 `str.replace` that patched the wrong views). Both were textual
operations whose *scope* was wrong while each individual edit looked fine.

---

## 2026-08-30 02:45-03:55Z — parallel review, and seven of my nine PRs had real defects

The user authorised subagents ("you can spawn your own subagents to review the PRs ...
up to 30 ... to work parallely"). I ran eight at once, all read-only on this checkout:
four hostile reviews over PRs 2-18, four reconnaissance passes over upcoming issues.

**This was the single most valuable hour of the run.** The reviews found defects in
seven of the nine substantive PRs, and two of them were things I had seen and shipped
anyway. Both of those are the same failure mode: I noticed a problem, wrote a comment
acknowledging it, and let the comment stand in for a fix.

### Findings, and what I did about each

| PR | finding | fixed |
|---|---|---|
| #12 (#51) | mcrit filters *after* slicing the page, so job search only ever searched page 1. Its own inline comment said so. | rewritten: unpaged fetch + local filter |
| #11 (#89) | the cache write was unconditional, so an in-flight probe overwrote `forget_server_probe()`; and an older answer could overwrite a newer one, which my docstring said was impossible | generation counter + start-time comparison; TTL now measured from completion |
| #10 (#79) | claimed "no sample with this SHA-256" when the *call failed* - `handle_response` maps 404 and 500 and 502 alike to None | raw mode, only 404 is absence |
| #6 (#101) | `/register` still leaked account existence; the timing dummy used today's hash method against databases written with an older one, leaving a ~30% gap | both closed; rehash-on-login so the table converges |
| #17 (#62) | the preload fetched 150KB on /login at phone widths and the font was never drawn - and my premise-guard test was a markup match that could not see it | gated on `g.user`; guard replaced with something markup can honestly check |
| #16 (#65) | three tables sitting under a search box still said "upload your first sample" | plus three more sites found while checking |
| #14 (#41) | the wrapping stopped at the jobs list; the same string on the overview and every result page was unwrapped | one class in `column_table.html` |
| #2 | the new `else` was unreachable for the job types its comment named (they store no result), so those still rendered "Job in Progress" forever | full state chain + `job_failed.html` |
| #3 (#73) | a failed job reported as "not found"; a report that *cannot be fetched* reported as *empty*, though `job_info.result` distinguishes them | three-way split |
| #5 (#54) | one failure flag over three independent searches; `hasCurrent` (a cursor param) mistaken for "has rows"; an escaping test that passed on master | all three |
| #7 (#100) | a visitor's token works against the API but settings showed neither the token nor the rotate button | `API_ROLES`, one constant |
| #9 | `make init` still did not install pytest, one target above the comment saying it must | fixed |
| #4 (#98) | **clean** - the reviewer round-tripped a real legacy database through master and the branch and confirmed the migration and downgrade safety | - |
| #18 | **clean** | - |
| #15 (#61) | **clean** - the reviewer executed all 45 pages' inline scripts in one shared V8 global and found zero redeclaration errors | - |

### The lesson, stated plainly

Two of these (#12, #2) were defects I had *documented in a code comment* and shipped.
A comment explaining why something is wrong is not a mitigation. If the honest comment
would read "note this is incorrect", the change is not ready.

A third (#17) is worse in kind: I wrote a test whose docstring claimed to guard an
invariant, implemented it as a substring match on markup, and never asked whether the
assertion could distinguish the failing case. It could not. A guard that cannot fail is
worse than no guard, because it is read as evidence.

### Reconnaissance, and two corrected triage calls

- **#35 is not effort L.** My table said "needs a function-analysis flow that does not
  exist". The `?funid=` filter and `result_compare_function.html` already exist and
  render (verified live); what is missing is a route that starts the parent-sample job
  and lands on `?funid=<id>`. S-M, with one design question for the maintainer.
- **#56 has a half nobody filed.** `/explore/functions?query=5` renders "No functions
  available" while `/explore/search?query=5&type=function` finds it - the listing pages
  read `search_results` only and drop `id_match`/`sha_match` on the floor. Same for
  families. That is a search hiding an existing record: wrong behaviour, effort S, and
  it is nowhere in the issue text. Reproduced live, both directions.

### New defects found while reproducing other things

- `/data/jobs/<cross compare>` was HTTP 500 (`sorted` over a `None` child job) → PR #18.
- `/data/jobs?active=notARealCategory` is an uncaught `KeyError` → 500, any visitor.
- `data.py:559` passes `job_info=result_json` to `result_corrupted.html`, so that page
  renders an empty job id and a delete button pointing at nothing.
- `result_compare_function.html` renders `matching_result.getFamilyNameByFamilyId(famid)`
  with `famid` never passed to that template.

None of these have issue numbers. Each gets its own PR.
