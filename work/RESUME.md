# Resuming after a dropped connection

Written 2026-08-31, while the integration rebuild was in flight. Read `STATE.md` for what
the campaign is; this file is only about picking the work back up.

## What is already safe, and needs nothing

All of it is on `origin` (the fork `r0ny123/mcritweb`) and on GitHub. A lost connection,
a lost machine or a wiped temp directory does not touch any of it.

- **16 fix branches**, all pushed, each reviewed and mutation-checked before push.
- **8 new upstream PRs**: `fkie-cad/mcritweb` **#163-#170**.
- **8 fixes folded into PRs that already existed**: #110, #115, #119, #124, #128, #140,
  #144, #160 - by fast-forwarding the PR branch, head SHA verified in each case.
- **4 mcrit bugs filed**: `danielplohmann/mcrit` **#155-#158**.
- **11 PR bodies corrected** where their "What I didn't do" notes had gone false.
- `work/LOG.md` and `work/STATE.md`, committed on `claude/mcritweb-triage-fixes-a5adho`.

**The audit the campaign was for is finished.** Nothing below is needed to call it done.

## The one thing that was in flight, and how it ended

A rebuild of the integration branch across **68 branches** - the 60 originals (which now
carry their fixes) plus the 8 new master-based ones. It is a *verification artifact*: it
proves the set still integrates. No landed branch or PR depends on it.

**Finished.** `origin/integration/all-68` @ `d830417`.

- All 68 merged: 23 cleanly, 45 with conflicts. Recomputed with
  `git merge-base --is-ancestor` rather than by counting merge commits (a fast-forward
  leaves none, and that undercount already happened once here), against a control branch -
  `agent/add-deepwiki-badge` - which correctly reads as *not* merged, so the check can fail.
- `ruff check .` clean. Suite **4 failed, 1884 passed** - exactly the 4 known Windows
  failures (`testSecretKey.py::test_the_key_file_is_not_readable_by_others` and 3 in
  `testUserFilters.py`). Master's baseline is 4 failed, 235 passed.
- Resolution notes: `work/int3-notes.md`, 999 lines, committed. The earlier copy lived in
  the scratchpad only, which is a temp directory and does not survive.
- `origin/integration/all-68-wip` @ `7f6bfd1` is the 58-of-68 intermediate. Superseded;
  kept only because deleting a shared ref is not this campaign's call.

### What the pass caught that a green suite would not have

The reason this artifact exists is that the defects it hunts do not fail tests. Two did
show up:

- **The duplicated missing-dependency warning came back.** Last round I fixed it *on the
  integration branch* and tightened its test there too. An integration branch is rebuilt
  from its sources, so both evaporated and the defect returned with nothing left to catch
  it. The count assertion now lives on `fix/job-overview-500-on-deleted-dependency`, which
  owns the template, and merging that branch is what surfaced the duplicate.
  **A fix that exists only on the integration branch has a half-life of one rebuild.**
- **#7's rounding, silently reverted by #50 again** - #50 rewrites the result tables as
  macros written against master. Verified by hand: zero truncating `%3d` on a score, six
  `%3.0f`, divisors threaded through `famlib_row`, no raw `binweight` divisor.

Also mutation-checked directly: dropping `r"(?:-(?P<theme>dark))?"` from the diagram
filename grammar fails 16 tests. Brace balance 56/56 in `style.css`, both `.mcrit-diagram`
colours tokenised, no duplicate badge columns, `compare_function` guarded.

### If it ever needs rebuilding again

Worktree from `origin/master`, merge `work/merge_order_v3.txt` in order, expect heavy
conflicts, then check the four items above plus the classes in `work/int3-notes.md`:
two branches implementing the same visible thing without conflicting; a stray `@bp.route`
dragged in on a conflict tail; a filename regex meeting a filename change; a "keep both
sides" resolution rendering a block twice; a constant defined twice; ADR files renumbered
but their references not; and a dropped `}` in `style.css` that reparents every rule after
it into the dark-theme block. Several branches now ship tests that pin these across
branches - if one fails after a merge it is working. **Fix the tree, not the test.**

## Still owed by the user

Two tokens need revoking: the Malpedia API token pasted into the session transcript, and
the GitHub OAuth token from an earlier session (https://github.com/settings/tokens).
Neither can be rotated from here - mcritweb 1.4.8 has no token rotation (that is issue
#100 / PR #111), so the Malpedia one needs an admin on that instance.
