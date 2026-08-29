# SUMMARY — mcritweb triage session, 2026-08-29

One session. 54 open upstream issues triaged, 8 pull requests opened on the fork.
Everything here is cross-referenced from `work/STATE.md` (the triage table),
`work/LOG.md` (what was tried, what happened, what was decided) and `work/SETUP.md`
(how to reproduce any of it).

---

## PRs opened

All against `r0ny123/mcritweb`, base `master`. Never upstream.

| PR | issue | what it does |
|---|---|---|
| [#9](https://github.com/r0ny123/mcritweb/pull/9) | — | **Install pytest in CI.** Every unit job on every branch was failing with `No module named pytest`; the suite had not run in CI since `mcrit` moved pytest behind its `dev` extra. **Merge this first** — it blocks the other seven. |
| [#2](https://github.com/r0ny123/mcritweb/pull/2) | — | **`/data/linkhunt/<job_id>` 500s** for any job that is not one of the four matching methods. The dispatch chain has no `else`, so the view returns `None`. Also un-swaps `result_incompatible.html` and `result_invalid.html`, which were wired to each other's branch. |
| [#3](https://github.com/r0ny123/mcritweb/pull/3) | #73 | **A finished job with an empty result was reported as an unknown job id.** `if result_json:` cannot tell `{}` from absent. The tail now distinguishes unknown id / failed / finished-and-empty / still running. |
| [#4](https://github.com/r0ny123/mcritweb/pull/4) | #98 | **`datetime.utcnow()` and the implicit sqlite3 adapter.** 405 → 1 deprecation warning on 3.13. Also fixes a latent crash older than either deprecation: a user registered on an exact-zero microsecond could never be read back. |
| [#5](https://github.com/r0ny123/mcritweb/pull/5) | #54 | **A search that matched nothing said nothing.** Adds the message, and keeps it out of the way when the search actually *failed* — which the naive version would have mislabelled. |
| [#6](https://github.com/r0ny123/mcritweb/pull/6) | #101 (part) | **`/login` no longer confirms which accounts exist** — one message for both failures, and an absent username now costs the same password check. Measured before: 101 ms vs 1.8 ms. **Rate limiting is not in it**; see below. |
| [#7](https://github.com/r0ny123/mcritweb/pull/7) | #100 | **API tokens: `secrets.token_hex(32)` instead of MD5, and a POST-only rotation route.** Also stops the v0.12.0 migration printing each generated token to the log. |
| [#8](https://github.com/r0ny123/mcritweb/pull/8) | #78 | **An entry that is both the id match and a name match is listed once.** The sample path was already fixed; families and functions were not. |

Every PR: a zero-finding self-review round (rounds logged in `work/LOG.md`), the full
suite green locally on Python 3.11 **and** 3.13, and `ruff check .` clean. Each carries
its own regression tests, and where the tests can run against `master` at all, the
failing-first run is quoted in the PR body.

Seven of the eight also carry a cherry-pick of #9's one-line CI fix, so their own CI
could run before it merges. Those commits no-op once master has it and can be dropped
on merge; a comment on each PR says so.

## Issues triaged and ranked

All 54 open issues on `fkie-cad/mcritweb` have a row in `work/STATE.md` with a
reproduction attempt recorded. Ranked by `severity x users-hit / effort`:

1. CI not running the suite at all (no issue number — found here)
2. the linkhunt 500 (no issue number — found here)
3. **#73** empty result vs unknown job
4. **#98** timestamp deprecations + latent read crash
5. **#54** silent empty search
6. **#101** account enumeration on `/login`
7. **#100** MD5 API tokens, no rotation
8. **#78** duplicate search rows

— all shipped. Then, not shipped:

9. **#79** better message for a hash that is not in the DB
10. **#89** the per-request backend probe
11. **#51** job search
12–54. the long tail: feature requests, refactors, open questions, tracker issues, and
work that belongs to the `mcrit` backend.

## Issues left untouched, with reasons

**Written up rather than fixed** — each has a note with the analysis, so the next
person starts from evidence instead of the issue body:

- **#79** — `work/notes/issue-79.md`. The message is not mis-worded: it fires when the
  backend call *failed*, not when nothing matched. The reason a sha256 lookup produces
  it looks like an unchecked `None` in `mcrit`'s `MinHashIndex.getSampleSearchResults`
  — **inferred from source, not executed**, because there is no backend here. Softening
  MCRITweb's wording would hide a real error, so nothing shipped. The half that *was*
  MCRITweb's is #54, and it is fixed.
- **#89** — `work/notes/issue-89.md`. The issue says outright that the decision belongs
  to whoever owns the error-handling story. Both options are behaviour changes with
  real costs (a TTL is a licence to be wrong for that long; removing the probe is
  paired with #43, itself unresolved). The note carries a caching probe an operator can
  drop into `instance/config.py` today, since `MCRIT_SERVER_PROBE` is already a
  config key.
- **#101, rate limiting half** — `work/notes/issue-101.md`. The issue leaves the
  deciding question open in its own words (per-account lockout hands out a
  denial-of-service; per-IP is evaded and punishes a shared NAT), and two more it does
  not raise: where the counter lives, and that `request.remote_addr` behind NGINX is
  the proxy.
- **#51** — `work/notes/issue-51.md`. Blocked: `getQueueData` has no filter parameter,
  so a working job search is a `mcrit` change first. The issue's own migration note has
  drifted — the search form is inside a `{# ... #}` comment, so there is no search box
  at all today.

**Cannot be reproduced here, and the reason is the same for all of them:** no MongoDB
and no docker daemon, so no real MCRIT backend (`work/SETUP.md`). That rules out
measuring #76 and #77 (search timings on a large collection), #68 and #63
(performance), #67 (export→import round trip), #38 (whether the aggregation follows the
filter), #80 and #69 (click-through UI checks). It also rules out #52 and #41, whose
only content is a screenshot on a 2022 GitHub CDN.

**Backend-owned, so nothing in this repository can fix them:** #7, #47, #59, #64, #76,
#77, and the root cause of #79. `AGENTS.md` is explicit that MCRITweb holds no analysis
logic.

**Feature requests and refactors, deliberately last or not at all** per the brief:
#9, #32, #34, #35, #37, #39, #40, #42, #43, #44, #45, #46, #48, #50, #53, #55, #56,
#58, #60, #61, #62, #65, #66, #70, #72, #74, #75, #93, #99, and the two tracker issues
#57 and #100's sequel. Each has a one-line verdict in `work/STATE.md`.

**Not built on:** the pre-existing PR on the fork,
[#1 "Scan for typos and logic errors"](https://github.com/r0ny123/mcritweb/pull/1). It
is stale — based on `5dbf5ae`, `mergeable_state: dirty`, and most of its content has
since landed independently (the `params.py` split, the `setup.py` missing comma in
v1.4.2, the `testPagination` import path, the combined `UPDATE server` statement).
Rebasing three commits onto a year of movement is a bigger job than the two lines still
relevant, and none of it overlaps this work.

## The three things I would do next

1. **Merge #9, then re-run CI on everything.** Until it lands, the repository has no
   working test signal — a PR can be merged on a green Ruff job while the suite has not
   executed a line. That is worse than a red pipeline, because it looks fine. Everything
   else on this list assumes it is done.

2. **Settle #43 (`McritClient` error handling), because three other issues are waiting
   behind it.** #89 cannot be decided without it — the issue says so. #79 cannot be
   fixed here without it, because `search_samples` collapses "backend errored" into the
   same `None` as everything else. And the `search_failed` flag added in #5 is a
   one-view version of the same idea, which will want folding in. Pick one of the two
   forks the issue names (meaningful exceptions vs. a checked `None` everywhere), write
   it into an ADR beside `0001` and `0002`, and the three unblock together.

3. **Get a real backend in front of the result templates, then act on #99.** Eight of
   the issues that could not be reproduced here are one `docker-mcrit` away from being
   answerable in an afternoon, and #99 (five report types covered out of 48 templates)
   is the reason a rendering regression can sit unnoticed — `instance/cache/` is never
   invalidated, so a stale result page looks like a working one. The corpus fixtures
   already exist and `tests/fixtures/regenerate.py` rebuilds them from any instance with
   one finished job of each type; the gap is coverage, not tooling.

---

## Handover

- `work/LOG.md` — timestamped, append-only, written for a reader picking this up cold.
  Includes the mistakes: a `str.replace` that patched two views it should not have (and
  the rule adopted afterwards — assert the occurrence count on every textual patch), and
  a test asserting `elapsed > 0` that a review round removed.
- `work/STATE.md` — the triage table, one row per open issue, plus per-issue detail for
  everything worked on. Claims are tagged **measured** or **inferred**, as `AGENTS.md`
  asks.
- `work/SETUP.md` — the environment, what is unavailable and why, and
  `work/harness/devserver.py`, which serves the app against the captured corpus so
  pages can be walked without a backend.
- `work/notes/` — the four write-ups above.
- Branches: `fix/<issue>-<slug>` per PR, all pushed. Documentation lives on
  `claude/mcritweb-triage-fixes-a5adho` and is not part of any PR.
