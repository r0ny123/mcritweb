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

---

## 2026-08-30, ~05:00Z — three PRs landed, and a Codex finding that hit 23 of them

### PRs opened

| PR | issue | what |
|---|---|---|
| [#24](https://github.com/r0ny123/mcritweb/pull/24) | 75 | export a job's raw result as a JSON download |
| [#25](https://github.com/r0ny123/mcritweb/pull/25) | 32 | show the MinHash matching setting a job was submitted with |
| [#26](https://github.com/r0ny123/mcritweb/pull/26) | 99 | measure which result templates the suite actually renders |

All three were implemented in isolated worktrees, then reviewed by me before landing.

#26 is worth noting for what it *found*: the coverage measurement itself is the
deliverable, but writing it surfaced two shipped bugs that no status-code assertion
could ever see, because both pages return 200 while saying nothing —
`result_corrupted.html` rendered an empty job id and a delete button pointing at
`/data/jobs//delete`, and `result_compare_function.html` printed
"Showing matches against family:" and then stopped. Both measured, both fixed.

### A correction I made before pushing #25

The implementation's docstring claimed "mcritweb never sends minhash_threshold".
That is false — `views/api.py:195` reads it off the query string and forwards it
through `McritClient`, which sends it as `minhash_score`. Rewrote the paragraph to say
what is actually true: mcritweb's own *submit forms* only ever set
`band_matches_required`, and the API proxy forwards whatever a caller supplies.

Same rule as before, applied to prose this time: a comment that is wrong is not a
smaller problem than code that is wrong. It is a *worse* one, because it is read as
established fact by the next person.

### Codex found a defect in 23 of my 24 open PRs at once

Codex, reviewing #26, flagged `Makefile`: the `init` target still ran
`pip install -r requirements.txt` alone, so a fresh checkout that follows the README
lands without pytest and `make test` fails with "No module named pytest" — the exact
failure the CI commit on that branch fixes *for the runner*, left unfixed for a human.

Verified the chain rather than taking it on faith:

```
$ grep -ci pytest requirements.txt
0
$ python -c "import importlib.metadata as md; print([r for r in md.requires('mcrit') if 'pytest' in r])"
['pytest; extra == "dev"', 'pytest-cov; extra == "dev"']
```

`requirements.txt` asks for plain `mcrit>=1.5.3`, so the `dev` extra is never
requested and nothing brings pytest in transitively. The finding is correct.

**The blast radius was the real story.** I had already fixed this once, on
`fix/ci-install-pytest` (PR #9) — and then cherry-picked the *older*, unfixed commit
`8268666` onto every other branch. So the defect was sitting in 23 open PRs, and
Codex happened to flag it on the one it was reviewing.

Fixing it only where it was flagged would have been the wrong call. Ported the
corrected `Makefile` and matching `AGENTS.md` onto all 23 branches — one plain commit
each, no force-push, no history rewritten — and verified before pushing that every
branch had exactly two files in its top commit and nothing else.

### That verification caught a second problem

The pre-push sweep found `work/harness/cookies.txt` present in the *local* copies of
four branches (52, 61, 78, 98) though absent from all the remotes. Those four local
refs were one commit behind: they had never picked up the remote's delete commit, so
my new Makefile commit had been built on a base that still carried the file. Pushing
them would have silently reintroduced it into four PRs.

Reset those four to their remotes and rebuilt the commit on the clean base.

**The standing rule earns its keep again:** verify the tree you are about to push,
not the tree you believe you are about to push. `git show --stat` before every push
caught the first version of this; a full `git ls-tree` sweep across all branches
caught this one. Neither would have been caught by looking at the diff I intended.

### Fleet dispatched

Six implementation agents running in isolated worktrees on issues **36, 40, 45, 55,
58, 66**. Each briefed with the full process — reproduce first, failing test first,
smallest viable change, hostile self-review to zero findings, full suite plus ruff —
and told explicitly *not* to commit or push. I review every diff before it lands.

Two got extra constraints worth recording:

- **#45 (mark the search term in results)** is an XSS trap. Highlighting user input
  inside output where the *haystack is also attacker-controlled* — sample filenames in
  a malware-analysis UI are named by the adversary — is the classic way to introduce
  it. Briefed to justify its escaping argument in full and to write tests that
  actually attempt the attack, both through the query and through a sample name, and
  to not ship if it cannot be made provably safe.
- **#55 (rerun job)** can reconstruct the *wrong* request. Briefed that offering the
  button for a job whose original request cannot be faithfully rebuilt is worse than
  not offering it at all: it would silently run a different analysis than the user
  believes they re-ran.

---

## 2026-08-30, ~06:00Z — seven more PRs, and what the fleet cost

### PRs opened

| PR | issue | what |
|---|---|---|
| [#27](https://github.com/r0ny123/mcritweb/pull/27) | 43 | answer a failed backend call with a page, not a stack trace |
| [#28](https://github.com/r0ny123/mcritweb/pull/28) | 58 | remember the sort order a listing was last viewed with |
| [#29](https://github.com/r0ny123/mcritweb/pull/29) | 36 | name the job list's tab in its own URL |
| [#30](https://github.com/r0ny123/mcritweb/pull/30) | 55 | rerun the jobs a request can be faithfully rebuilt from |
| [#31](https://github.com/r0ny123/mcritweb/pull/31) | 40 | name the queried file; stop giving it a family it has none of |
| [#32](https://github.com/r0ny123/mcritweb/pull/32) | 66 | say what the import is doing while it does it |
| [#33](https://github.com/r0ny123/mcritweb/pull/33) | 45 | mark the search term in the rows that matched it |

Six were implemented by worktree agents; #27 I did myself. **Every one was
re-verified here before landing** — I re-ran the reproduction against
`origin/master` and against the branch myself rather than quoting the agent's
transcript, and mutation-checked the load-bearing test in each (delete the guard,
confirm the test fails).

### The single most valuable finding: a live XSS on master

While checking what an attacker-controlled filename could reach, the #40 work found
that `clipboard_btn` built `onclick="copy_to_clipboard(this, '{{ value }}')"`. Jinja
escapes `'` to `&#39;`, which *looks* safe — but the HTML parser decodes the entity
**before** the attribute is compiled as script. Reproduced on pristine `master`:

```
  onclick as the JS engine sees it: "copy_to_clipboard(this, 'a');alert(1);//')"
  payload executes: True
```

Reachable today through a contributor-chosen sample filename, and in a
malware-analysis UI the filename is chosen by the adversary. Fixed in #31 (the value
moves to `data-clipboard-value`, read with `getAttribute`), because #31 would have
*widened* it to any visitor who can run a query — shipping the widening without the
mitigation was not an option. Offered to split it out if the maintainer wants it
merged ahead of the rest.

### Codex found three real defects I had shipped

Not one of them was cosmetic, and each exposed the same *kind* of blind spot:

1. **#26 / all 23 branches** — `make init` still didn't install pytest. I had fixed
   this once on `fix/ci-install-pytest` and then cherry-picked the *older* commit
   everywhere else, so it was live in 23 of 24 open PRs. Ported the fix to all 23.
2. **#27** — the 503 page linked an admin to `url_for('administration.server')`; the
   blueprint is registered as `admin`, so it raised `BuildError` and served an admin a
   500 *for the one condition the page exists to report*. **Every test in the file
   signed in as a visitor**, which is exactly why none of them saw it.
3. **#27** — `mcrit_server_required` runs before the view, so a probe failure never
   reached the API blueprint's handler and API callers still got a 302 to HTML. I had
   *flagged this in the PR body as a follow-up* — which made the PR's headline claim
   true only in the narrow case. Fixed rather than documented.
4. **#30** — the rerun route enforced the request shape but not the finished-or-failed
   gate. I had written the reason that gate exists and then put it only in the function
   that decides whether to draw the button. **Withholding a button hides the door; it
   doesn't lock it.**
5. **#31** — the query/stored gate was table-wide, so a *mixed* table (query filtered
   to one match) still gave the query column the fabricated family the change exists to
   remove.

### The lessons, stated plainly

- **A test suite that only exercises one role is not a test suite.** Findings 2 and 3
  both survived because every test in the file used the same fixture defaults —
  `as_role("visitor")` and a probe stubbed to succeed. Vary the axis the branch
  depends on.
- **"What I didn't do" is not a place to park a defect.** Finding 3 was in my own PR
  body as a known gap. Writing it down did not make the PR's claim true.
- **A gate in the template is not a gate.** Finding 4.
- **A test that asserts a row is *present* cannot see that its contents are wrong.**
  Finding 5 sailed past a test that checked exactly that.

Every fix above is mutation-checked: I put the bug back and confirmed the new test
fails. That is now the standing bar for a fix to a review finding.

### An environment hazard that cost real work

`git stash` shares `refs/stash` across **every worktree of a repository**. Three
agents used it concurrently to measure a clean baseline and their stashes crossed —
one agent's `stash pop` retrieved another's work into its tree, and the #66 agent's
worktree ended up holding the #45 agent's row-template edits while its own work sat
in the stack.

Nothing was lost: both agents detected it, recovered from the dangling stash commits,
and independently audited their final diffs. I verified all three trees from here
before landing anything, and confirmed each branch's committed diff contained only
its own files.

**Standing rule added to every agent brief from now on: never run `git stash` in this
repository.** For a clean baseline, `git worktree add --detach /tmp/baseline origin/master`.

I also corrected a figure I had been giving agents: the suite baseline on
`origin/master` is **239**, not 261. My number came from a feature branch. Three
separate agents measured 239 and flagged the discrepancy rather than quietly
adjusting their arithmetic, which is the right instinct.

### Next fleet

Four agents on **#35**, **#72**, **#34**, and a research pass over the nine issues
triaged as "can't reproduce / belongs in mcrit" (**#38, #68, #80, #69, #47, #64, #59,
#76, #77**) — that last one exists because those triage calls were made fast and some
of them are probably wrong. Several "backend" issues plausibly have a client-side half
(a filter over data already on the page, an N+1 fetch), and an N+1 is measurable
offline with `RecordingMcritClient` even without a large database.

---

## Session 6 — the last agent fleet lands, and nine "can't do this" triage calls fall over

### PRs #35 and #36 opened (issues #34 and #35)

Both agents finished. I reviewed each diff as a hostile reviewer before landing.

**Issue #34 → PR #35** (`fix/34-function-page-api-usage`). Accordion layout, an API
Usage section folded out of `xcfg["apirefs"]`, and a MinHash present/missing row.
The agent also found a real markup bug in `table/function_row.html:76`: the `>` closing
the `<i>` tag existed only on the *else* branch, so every function that **has** a
MinHash emitted an unterminated tag. Shingles were correctly declined — the raw
shingles are never persisted, `minhash_shingle_composition` is gated behind
`MINHASH_TRACK_SHINGLES` (default off), all 609 captured functions have it empty, and
its shape differs between strategies. Nothing real to render, so nothing rendered.

I verified two claims that mattered rather than taking them:
- `getFunctionById(function_id, with_xcfg=True)` — real signature, checked in
  `McritClient.py:338`.
- `apirefs` values are strings, not lists: 429 values across the fixtures, all `str`,
  e.g. `'ws2_32.dll!getpeername'`. So the `Counter(str(api) ...)` fold is right.
- The new fake's `getMatchesForPicHash` / `getMatchesForPicBlockHash` summary shapes
  match `QueryResource.on_get_query_pichash_summary` and
  `on_get_query_picblockhash_summary` exactly, including the `offsets` key the block
  variant adds. Fidelity is the thing Codex caught me on before (#34/`getStatus`), so
  I checked it against the installed mcrit rather than the report.

**Issue #35 → PR #36** (`fix/35-analyze-a-single-function`). The Analyze button on a
function row built its href from `function.sample_id`, so every function of a sample
got the same link — to the sample picker. There is no per-function 1-vs-N in the
backend, so the only meaning available is the parent sample's job read through the
`?funid=` filter `data.result` already implements.

The half worth recording: on master the job page's auto-forward **drops** `funid`
(`/data/jobs/<id>?forward=1&funid=2` → `/data/result/<id>`), so the route alone would
have degraded back into the reported bug one redirect later, for exactly the users
whose job was not already finished. I mutation-checked that: removing the forward
fails `test_analyzing_a_function_lands_on_the_function_filtered_result` and
`test_the_job_page_carries_the_function_filter_into_the_result`.

**A mistake of mine, recorded because it nearly cost the #34 work.** While
mutation-checking `explore.py` I reverted the mutation with `git checkout
mcritweb/views/explore.py` on a branch with no commit yet — which threw away the
agent's actual change, not just my mutation. I rebuilt it from the diff I had already
printed and confirmed byte-for-byte via `git diff --stat` (30 lines changed, 142
insertions — identical to before). Use `cp` backups for mutation checks, never `git
checkout`, on an uncommitted tree.

Also: the CI cherry-pick (`8268666`) carries `work/harness/cookies.txt` with it. On
the earlier branches I fixed that with a follow-up "drop the artefact" commit, so it
still sits in their history. On these two I cherry-picked with `-n`, removed the file
before committing, and squashed both CI commits into one — so `work/harness/` never
enters the history at all. Verified with `git ls-tree -r HEAD | grep -c cookies.txt`
→ 0 on both.

### Codex finding on PR #10: uppercase SHA-256 — real, fixed

`SHA256_PATTERN = re.compile(r"[a-fA-F0-9]{64}")` accepts uppercase and
`flash_sample_search_failed` forwarded the term unchanged. Samples store their hash as
a lowercase SMDA hexdigest and the backend's lookup is an exact match —
`MongoDbStorage.getSampleBySha256` is `find_one({"sha256": sha256})` — so a hash
pasted from a report came back 404 and was reported as *"No sample with SHA-256 … is
in the collection"* for a sample that is right there. A confident wrong answer, which
is precisely the failure mode issue #79 exists to remove.

Fixed by folding the value passed to `sha256_second_opinion` while keeping the typed
casing in the flashed message. Three tests, all mutation-checked:
- forwarding unchanged → 2 fail
- lowercasing `query` itself (the tempting wrong fix, which would also fold the
  display) → the third fails

`3f9b206` on `fix/79-say-what-a-failed-search-means`. Suite 256 pass, ruff clean.

The other half of that Codex review (failed lookup vs absent) was already fixed by the
raw-mode / 404-only change in `adc0e55`.

### Nine issues were triaged wrong, and an agent proved it

The research pass over the "can't reproduce / belongs in mcrit" set came back with
measurements, and **six of the nine calls were wrong**. Recording the corrections here
because they are now the work queue:

- **#38 (filtered matching statistics)** — triaged "needs backend". Four of the five
  statistics fields recompute *exactly* from `MatchingResult.function_matches`, which
  is already on the page. Verified against three real reports. Today the win.dridex
  page states 756 functions / 151 KB matched when the honest answer for that filter is
  4 / 249 bytes. Only `num_self_matches` is genuinely unavailable (the backend drops
  self-matches from the report).
- **#68 (result page performance)** — triaged "can't measure here". Measured end to
  end: `create_match_diagram` runs synchronously before `render_template` and is
  **275 ms of a 303 ms first view — 91%**. The `<img>` seam to move it behind already
  exists. Separately the report aggregation is computed twice per request and the
  first result thrown away (three one-line edits, 13–26% off every warm render).
- **#69 (FunctionVs loop visualisation)** — triaged "needs click-through". The
  click-through runs offline in headless Chromium. Four defects: "Show Cycles" throws
  (`g` is `null`; the duo loader uses `g_a`/`g_b`), "Show Loops" is never wired
  (`loopCollapser.init()` commented out), `loopsObj` is one global written by two
  racing XHRs, and `nodesAll` is one dict keyed by block offset so the two graphs
  collide. The *server* half is correct — 200/200 functions cross-checked against an
  independent networkx dominator computation.
- **#80 (block isolation table)** — triaged "can't". Mostly checkable. The reported
  "~120 character" clipboard truncation does **not** reproduce (a 5613-character rule
  copies intact), but two other real defects do: the copy reads `.html()` not `.val()`
  so user edits are silently discarded, and `&`/`<`/`>` copy as entities.
- **#77 (sample search slow)** — triaged "needs a large real DB". Found with a call
  counter on a 17-job corpus: `explore.py:168` calls `getQueueData()` with no
  arguments, and `limit=0` omits the limit entirely — so every sample-list and
  sample-search page view downloads the **whole job queue**. At 8500 jobs that is 8 MB
  transferred and parsed plus ~166 ms of pure mcritweb CPU, to annotate 25 rows.
  `getFamilies()` on the next line downloads every family for a datalist.
- **#76 (function search 30 s)** — core is genuinely mcrit's (unanchored
  case-insensitive regex over the largest collection, which must exhaust it when there
  are no hits). But `explore.search` runs all three searches sequentially by default,
  so the 30 s is charged to everyone who only wanted a family hit.

Correctly triaged: **#47** (`mongoqueue` picks the newest non-terminated job, so a
running force-rematch shadows a finished one — one query in mcrit), **#59** (no
compound indexes; worth noting mcritweb's sortable headers offer exactly the three
unindexed function fields), and the core of **#76**. **#64** is mcrit's for the client
change, but `explore.py:195` has the `FunctionEntry.fromDict` call commented out while
`explore.search` deserialises properly — latent inconsistency, one line.

### And twelve `wait`-labelled issues got proposals

Headlines, all measured:

- **#48 (minify HTML)** — close it. A minifier saves **1.1 KB gzipped on a 1.9 MB page
  load**. HTML is 1.9–10.6% of page weight; the other 1.14 MB is vendored JS (jquery-ui
  alone is 529 KB, used for one `sortable()` and an autocomplete). That is the real
  issue, and it is a different one.
- **#44 (`dedumped`)** — the code already does the **opposite** of what the issue
  proposes: `'dump' in filename` matches `dedumped`, so a de-dumped file is
  pre-filled as "Dumped" with an empty base address, and submitting that form **500s**
  (`ValueError: invalid literal for int() with base 16: ''`, in both submit paths).
  Highest value-per-line on the list.
- **#42** — sub-question (a), "do we need a reset-to-clustered button", is **already
  implemented** at `result_cross.html:191`.
- **#57 / #51** — the jobs search box is commented out in `jobs.html:139-148` while the
  POST handler survives and 400s without a `Search` field. And the obvious fix would
  ship a broken feature: `QueueRemoteCalls.getQueueData` applies its filter **after**
  paging, so wiring it gives "page 3 of 40, showing 2 results".
- **#46** — a cross-compare that took 8.06 s reports `0:00:00`, because `duration` is
  the parent's `finished_at - started_at` and the parent does not start until its
  children finish. `finished_at - created_at` is two lines and needs no extra calls.
- **#50** — 85 of 88 lines are byte-identical between two of the five hand-rolled
  result tables; 204 `column_type` branches across 935 lines. Extractable into a *new*
  `table/match_row.html`, which is what keeps it off the contended surface.
- **#7** — the arithmetic is the backend's, but mcritweb **truncates** the score for
  display (`"%3d"|format` on a float), so 1.04 and 0.86 render as `1` and `0`. That is
  a plausible cause of the reported "seemed too far from the expected value" and it is
  in scope.
- **#70 (dark mode)** — stays `wait`, but the issue understates it: Bootstrap 5.0.2 has
  zero `data-bs-theme` support (that is 5.3), 78 template lines carry literal colours,
  and `ScoreColorProvider` blends *toward 255* so the whole heat-map inverts in meaning
  on a dark ground. The cached match-diagram PNGs are baked on white and never
  invalidated.

---

## Session 7 — the "can't be done here" set becomes fifteen PRs

Every issue the research pass re-triaged now has a PR, plus the ones I did by hand.

### Landed this session

| issue | PR | one line |
|---|---|---|
| #34 | [#35](https://github.com/r0ny123/mcritweb/pull/35) | accordion, API usage, MinHash indicator — plus an unterminated `<i>` tag |
| #35 | [#36](https://github.com/r0ny123/mcritweb/pull/36) | analyze a function, not its parent sample |
| #9 | [#37](https://github.com/r0ny123/mcritweb/pull/37) | promote a query to a sample |
| #93 | [#38](https://github.com/r0ny123/mcritweb/pull/38) | unique blocks gets a page, a sample set and rule knobs |
| #44 | [#39](https://github.com/r0ny123/mcritweb/pull/39) | `dedumped` is not a dump; two 500s on the submit path |
| #38 | [#40](https://github.com/r0ny123/mcritweb/pull/40) | matching statistics follow the filter |
| #64 | [#41](https://github.com/r0ny123/mcritweb/pull/41) | deserialize the function listing |
| #69 | [#42](https://github.com/r0ny123/mcritweb/pull/42) | the FunctionVs loop and cycle highlights actually work |
| #68 | [#43](https://github.com/r0ny123/mcritweb/pull/43) | diagram off the page request; four costs |
| #77/#76 | [#44](https://github.com/r0ny123/mcritweb/pull/44) | stop downloading the whole queue and every family |
| #80 | [#45](https://github.com/r0ny123/mcritweb/pull/45) | clipboard copies `.value`; version column; sortable |
| #7 | [#46](https://github.com/r0ny123/mcritweb/pull/46) | round the score columns |
| #46 | [#47](https://github.com/r0ny123/mcritweb/pull/47) | a cross job that took 8s no longer reports 0:00:00 |
| #67 | [#48](https://github.com/r0ny123/mcritweb/pull/48) | the CFG view survives a function with no xcfg |
| #74 | [#49](https://github.com/r0ny123/mcritweb/pull/49) | the two CFG panes pan and zoom together |

### The worktree collision, and what fixed it

Four agents (#69, #68, #77, #38) were handed the **same** worktree by the harness and their
edits interleaved in `views/data.py`. Nobody lost work — each of them noticed
independently, isolated their own hunks, and rebuilt in a clean tree off `origin/master`
— but the numbers they first measured were contaminated, and two of them said so before
I asked.

**Standing fix, now in every brief:** the agent's first action is
`git worktree add --detach /tmp/work-<issue> origin/master`, plus a pristine
`/tmp/baseline-<issue>` it never edits, and it confirms `git status` there lists only its
own files before reporting. The four briefs I sent after that produced clean isolated
trees with no intervention.

One thing this cost me: an agent created a branch in the shared tree, which moved the
*other* agents' base from `227bc4a` to `df53db9` under them. Recoverable, but it is why
the rule is "your own tree first, before any other work" rather than "eventually".

### My own mistake, recorded

Mutation-checking `explore.py` on a branch with no commit yet, I reverted the mutation
with `git checkout mcritweb/views/explore.py` — which threw away the agent's actual
change along with my mutation. Rebuilt it from the diff I had already printed and
confirmed byte-for-byte via `git diff --stat`. **Use `cp` backups for mutation checks on
an uncommitted tree, never `git checkout`.**

### Codex findings this session — six, all real

- **#10 uppercase SHA-256** — real, fixed, and the mutation check needed three tests: two
  for the fold, one against the *tempting wrong fix* of lowercasing `query` itself, which
  would also have folded the display.
- **#19 `getMatchesForSampleVsGroup` unnamed** — real, and the fixture claim checked out
  exactly (5 such jobs in `queue.json`). The interesting half was **why my ratchet missed
  it**: it ratcheted against `Job.method_types["all"]`, which mcrit maintains by hand and
  which omits four methods. Now enumerates `@Remote`-decorated methods, which found
  `doDbCleanup` as well — plus a second ratchet reading the captured queue, which is the
  one the finding would have tripped.
- **#15 file-wide declaration search** — real. Scoping alone produced a *false positive*
  on a parameter reassignment, so the parameter half was not optional. Zero findings
  either way against the current tree, which is the right moment to tighten.
- **#16 dead CTA link for visitors** — real, and it was nine call sites, four of them
  older than my branch. Gate went in `_empty_state`, and the premise (`/data/submit` is
  403 for a visitor) is now pinned by its own test.
- **#44 partial queue read** — real, and worse than "undercounts": the flash *said* the
  annotations were not shown while some of them were.
- **#46 tooltip precision** — real and subtle. The test compared the cell against
  `round(tooltip)`, but the tooltip is already rounded to two decimals, so a score of
  2.501 (tooltip `2.50`, cell `3`) would have failed a correct page — a latent spurious
  failure waiting for the next fixture regeneration.
- **#47 fan-out parent queued last** — real; verified the parent is created 10ms after its
  last child. Did not take the remedy (per-child fetch is the cost the `wait` label is
  about) and relabelled instead, which is what was actually wrong.

Two threads left **open on purpose**, both maintainer calls rather than mine: whether
`main_duo.js` counts as vendored (it is already a project fork — 492-line diff from
`main.js`, our own CSRF patches on master), and whether an image cache counts as "writes"
in `routePolicy`'s table.

### Corrections agents made to my briefs, which is the point of asking them

- Jinja's `round` filter is round-half-to-**even**, not half-up — so the two rounding
  forms I offered are byte-identical for every input, and the choice had to be made on
  other grounds.
- The #46 progress rollup is **free** on `/data/jobs/<id>`, which already fetches every
  child; my cost objection only holds for the result pages.
- DataTables is **not** removed at `df53db9` — that lives on another branch. I had told
  an agent otherwise.
- The #80 version column costs **zero** extra calls for a family job, not one:
  `getFamily(with_samples=True)` already answers with them, checked against both mcrit
  1.5.3 and 1.8.1.

### #50 landed, and four more Codex findings

[PR #50](https://github.com/r0ny123/mcritweb/pull/50) — 244 `column_type` branches across four
result templates become 92, net −295 lines of template. Acceptance was a byte diff of 51
rendered pages: 37 byte-identical, and the 14 that differ are all `result_compare_all.html`,
all whitespace-only, all DOM-identical node by node. The macros went into a **new**
`table/match_row.html` precisely so they could not collide with the thirty-odd open PRs
touching `sample_row.html` / `function_row.html`.

Worth keeping: **Jinja renders a macro called with the wrong arity as nothing at all,
silently.** Marker-based assertions caught 6 of 18 arity mutations — a marker present in
one table hid breakage in another. A structural audit (every match table has header cells
and body cells) catches 18 of 18.

Findings closed:

- **#34** — the statistics test required every field of the captured status to appear,
  while `statistics.html` renders at most 12. Passes today at 8 fields; a fixture refresh
  from a richer backend would have broken CI with nothing about the page changing. Test
  now walks what the page renders, and a second test pins the cap against a synthetic
  15-field status so the limit is asserted somewhere other than a Jinja conditional.
- **#38 ×2** — `start_unique_blocks` forwarded ids the selection page never validated (it
  checks only the ten it renders), and the submit URL was a root-relative literal that
  leaves the app under a `SCRIPT_NAME` prefix. Both fixed; `cross_compare.html:90` has the
  same URL bug and was left alone as out of scope, with that said on the thread.

**A mistake worth recording.** I pushed the first #38 fix with a failing test, because
`pytest -q | tail -2 && git push` returns the exit status of `tail`, not pytest. The
failure was real — committing the fake to answering *every* `is*Id` let
`data.match_functions` past its guard and into `match_info["function_entry_a"]` on a
`None`. I narrowed the fake to `isSampleId`, wrote the exposed defect into its docstring,
and pushed the correction two minutes later. **Capture the exit code (`cmd > file; echo $?`)
rather than piping into `tail` inside a `&&` chain.**

---

## Round 4 — adversarial review of every open PR, and what it found

Five review agents were run over PRs #35–#50, each in its own worktree, each told to
mutate the code a test claims to guard and report what survived. Their findings are the
substance of this round; the corrections below are mine, verified independently before
acting on any of them.

**A security bug on `master`, found in passing.** `analyze.query` took the filename it
writes an upload under straight from the SMDA report's own `sha256` field — a string the
uploader wrote, which `SmdaReport.fromDict` assigns through with no validation — and
joined it into a path. A report declaring `"sha256": "../../../PLANTED"` put
attacker-chosen bytes at an attacker-chosen path, from `@visitor_required`, the lowest
role this application has. Reproduced against `df53db9`:

```
status: 202
PLANTED written outside instance/: True
  size: 303 path: /tmp/.../test_traversal0/PLANTED
uploads dir now: []
```

Fixed in its own branch (`fix/query-upload-path-traversal`, PR #58) with a hexdigest
shape check before the join, plus `.lower()` — an uppercase-hashed report used to land at
a name no reader would ever look up. Two nearby 500s (`sub/dir/NESTED`, a null `sha256`)
become the same honest 400. +16 tests, 239 → 255. `data.submit` reads the same field but
its SMDA branch returns before the `open()`, so it is unaffected.

**A live XSS sink held shut by two unrelated bugs.** `main.js:2733-2738` assigns a dot-graph
node label into `innerHTML`, and those labels carry `apirefs` — import names read out of the
analysed binary, interpolated by smda's `toDotGraph(with_api=True)` with no escaping. It does
not fire today: on the single-function page the handler throws two lines earlier on a missing
`#xcfg_right`, and on the comparison page `#tooltip`/`#value` do not exist. **Fixing either of
those "obvious" bugs arms it.** Recorded on PR #42's description; not touched, because touching
it means fixing the tooltip, which is a different change.

**Claims of mine that were wrong, corrected in place:**

- **#42** — "344 of the 609 fixture functions raise through loop detection". Measured
  myself: `total 609  with_xcfg 200  loops_ok 200  loops_raise 0  with_loops 65`. Zero
  raise; the other 409 cannot reach `findLoops` at all. The fix stands on the fault
  injection, not on the corpus. Also "6x loopsObj=5" was one sample of a coin flip (3/3 on
  a rerun), and "Panel state, not global state" overstated — the four globals still race,
  they are just no longer the storage.
- **#48** — "all 120 intact captured functions". It is 200.
- **#40** — the new `{% if %}` reindented *every* page, so "unchanged down to the rendered
  string" was false. 27 rendered pages against master: 27 differed, 10 after the whitespace
  fix, and those 10 are the pages the change is about. Also cited a `filterToFunctionScore`
  double-append hazard that does not exist (with both bounds set it takes the first branch).
- **#41** — "the rendered rows are byte-identical". Not for `offset`, which the wire dict
  carries two's-complement encoded: `0x-80000000` against `0xffffffff80000000`. Any
  kernel-mode driver sample. The corpus has none, which is why it looked identical.
- **#49** — `isUsableExtent` was justified by a case that cannot happen, and the mirror
  anchors the viewport's top-left corner rather than its centre.
- **#36** — the Conflicts section's advice ("prefer #34's side") breaks the PR: the hunk
  spans `requestMatchesForSample`, which only #36 adds. 5 failed.

**Tests that passed both ways** — each reproduced by reverting the code it guards:

| PR | test | result with the code removed |
|---|---|---|
| #35 | the whole of `testFunctionPage.py` vs `with_xcfg=True` | 11 passed |
| #43 | two tests named for atomic writes vs in-place writes | 326 passed |
| #44 | the newest-first order test vs a scrambled order | 21 passed |
| #45 | the sort test vs the entire sorting script deleted | 245 passed |
| #45 | nothing at all vs the clipboard fix reverted to the #80 bug | 245 passed |
| #38 | the cap's message assertion, satisfied by static page prose | 1 passed |
| #41 | `test_the_search_page_agrees` vs the loop it names | 3 passed |
| #50 | 4 of 36 arity mutations, two of them a real regression | 242 passed |
| #37 | the non-query-job guard | 25 passed |

One agent **disagreed with its brief and was right**: the review claimed `explore.sample_by_id`
still passed raw dicts, and it has called `fromDict` since 55aa4d6. Verified by blame on master
before accepting. Nothing was changed there.

**A pushback worth keeping:** a reviewer's harness ran as `python /scratch/dump.py`, so
`sys.path[0]` was the script's directory and `import mcritweb` resolved to the editable
install for every branch — every page came out "byte-identical" because nothing was
compared. They caught it themselves and redid the work with an
`assert mcritweb.__file__.startswith(os.getcwd())`. My own render harness for #40 carries
the same assertion for the same reason.

### What the review round landed

Eight fix agents, one PR each, each in its own worktree, each told to mutation-check
every test it touched. Six have landed; two are still out (#43, #44/#50).

| PR | what shipped | suite |
|---|---|---|
| #37 | the promote path now checks the stored file against `Job.sha256` - the hash the *backend* recorded for the payload the job ran on. Plus the kernel-mode `base_addr`, the `+` in family/version, and a guard test that passed with its guard deleted | 265 → 278 |
| #38 | no YARA rule at all when the bounds select no blocks; a stale selection settles in one request instead of 25 redirects; nothing is discarded on an unproven negative | 288 → 296 |
| #39 | `de-dumped` / `de_dumped` / `dedump` / `dedumping` recognised; the SMDA path stops demanding a base address it never reads; the parse behind that gets its own 400 | 276 → 315 |
| #35 | the fake honours `with_xcfg`, so the flag that makes the feature work is finally guarded; `get_api_usage` answers None for a broken shape | 250 → 255 |
| #41 | the offset above the sign bit is pinned; the search test searches by name so it reaches the loop it names | 242 → 243 |
| #46 | six more truncating score cells, one of them default-visible; the test now renders all four changed templates | 242 → 250 |

**Three agents disagreed with their brief, and each was right.**

- The #41 agent refused Finding 1: `explore.sample_by_id` has called `fromDict` since
  55aa4d6, on master and on the branch. Verified by blame before accepting; the reviewer
  had quoted a line that does not exist there.
- The #38 agent rejected "clamp `condition_required` at render" on better grounds than
  the brief gave: `min(len(yara_blocks), condition_required)` would write `1 of them`,
  but the *empty `strings:` section* is itself the syntax error, so clamping swaps one
  uncompilable rule for another. Confirmed against `UniqueBlocksResult.renderRule`.
- The #37 agent rejected both shapes the brief offered - store under `sha256(bytes)`
  everywhere (needs a mapping that does not exist, breaks every stored upload) and
  require filename == `sha256(bytes)` (would make `.smda` promotion permanently
  impossible, since the file is the report JSON while the name is the sample's hash) -
  and found a third: the descriptor hash the backend already computed. It also closes
  the TOCTOU between `os.path.isfile` and `open`, because what is hashed is what was read.

**One place I overrode an agent.** The #39 agent flagged that its own fix newly exposed a
500 - moving the base-address check off the SMDA path leaves an unreadable report body
reaching `json.loads` unguarded - and declined to fix it as a drive-by. That is the right
instinct in general and the wrong call here: this PR's headline is "an empty base address
was a 500, now a 400", and leaving a sibling 500 in the same route is inconsistent. Fixed,
with five unreadable bodies across both routes now answering 400 and reaching no backend
call; mutation-checked.

### The last three, and a brief of mine that was wrong

| PR | what shipped | suite |
|---|---|---|
| #43 | cache files keep the umask's permissions again; `write_atomically` finally has tests that can see it; temp files leave the served directory; a non-canonical filter id stops doing uncacheable work | 326 → 345 |
| #45 | both headline fixes get a lint that always runs plus a browser test that drives them; `families.json` recaptured so the family shortcut is not dead in the suite | 245 → 251 |
| #44 | the per-method queue reads are sorted back into newest-first; four fixture-coupled assertions derive what they mean; `SAMPLE_ROW_JOB_METHODS` tied to the installed mcrit | 262 → 264 |
| #50 | the column shape the refactor preserves is pinned two ways | 242 → 243 |

**My brief for #50 was wrong on a number and, more importantly, on the mutation that
matters.** I told the agent "9 call sites × 2 = 36"; it is **18** call sites × 2. And the
reviewer's one-at-a-time sweep cannot reach the edit a person would actually make -
dropping `unique_match_known=False` from *both* vs call sites at once. That keeps the
table rectangular, adds a whole real column, and was **fully green**. So a shape check
alone would not have been enough; the agent added a second guard reading the column list
`data.py` hands to both templates.

**Two more agents improved on the brief rather than following it.**

- For #43 I suggested `os.chmod(0o666 & ~umask)`. The agent found the better answer:
  never read the umask. `open(2)` masks its mode argument in the kernel, so opening with
  `opener=` and mode 0666 reproduces master's `open(path, "w")` exactly - no
  `os.umask(0)` window to race, no chmod. It also rejected a hardcoded 0644 because that
  would *widen* a hardened deployment, and closed an fd leak `mkstemp` had left.
- For #44 I offered "make the test bite, or make the docstring honest". The agent took
  the third option I had listed as preferable-if-cheap and made the concatenated list
  actually newest-first, then rejected two obvious sort keys with reasons: `job_id`
  descending is what `get_jobs` does, but `LocalQueue.put` sets `_id` to a uuid4 with no
  ordering; `created_at` is a `str` on the wire and a `datetime` locally, so a mixed list
  raises.

**One agent corrected my own PR's headline claim.** #43's "-77%" is page latency, and the
title says "stop doing the work twice". Counted end to end the work is *flat and slightly
higher*: master handed the diagram route the page's already-deserialised report, so a cold
view cost one `MatchingResult.fromDict`; now it costs two. Posted as a correction on the
PR.

**A cross-PR check the agents could not do.** #45 changes `tests/fixtures/families.json`,
which ten open PRs read. Dropping the new fixture into `fix/77-explore-page-backend-calls`
(262 passed) and `fix/68-result-page-performance` (345 passed) *without* #45's
`fixtureData.py` change leaves both green, so it is additive and there is no merge-order
hazard. Verified the shape against the installed backend rather than trusting the
reconstruction: `FamilyResource.on_get` does `family.samples[sample.sample_id] = sample`
and `FamilyEntry.toDict` writes `{id: sample.toDict()}`, which JSON renders with string
keys - which is what the fixture has.

**Where PR bodies were rewritten and where they were commented on.** #37, #38, #40, #41,
#42, #46, #48, #49 and #36 got their descriptions corrected in place. #39, #43 and #45 got
comments instead, because the API returned those bodies truncated or with a mangled regex
block, and overwriting text I could not read in full would have destroyed content.
