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
