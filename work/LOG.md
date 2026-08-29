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
