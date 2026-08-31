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

## The one thing that was in flight

A rebuild of the integration branch across **68 branches** - the 60 originals (which now
carry their fixes) plus the 8 new master-based ones. It is a *verification artifact*: it
proves the set still integrates. No landed branch or PR depends on it.

State when this was written:

- **58 of 68 merged.** Saved as `origin/integration/all-68-wip` @ `44a16bd`.
- It was mid-merge on `fix/70-tokenise-the-palette` with 19 unmerged paths. **That merge
  is not in the saved commit** - it was uncommitted working-tree state and is gone.
- Resolution notes: `scratchpad/int3-notes.md`, ~746 lines. **Scratchpad only.** If the
  temp directory is gone, so are the notes; the merge commits themselves carry the
  resolutions, so this costs the reasoning, not the work.

### Which 10 remain

    fix/70-tokenise-the-palette
    fix/60-pagination-spinner
    fix/jobs-500-when-the-queue-cannot-be-read
    fix/pagination-reserved-query-args
    fix/submit-metadata-into-the-query-string
    fix/sample-filtered-result-pagination-count
    fix/stop-printing-match-reports
    fix/state-the-real-python-floor
    fix/import-rejected-is-not-malformed
    fix/autocomplete-escapes-suggestions

Do not trust a remembered count. Recompute it, and make sure the check can fail:

```
git worktree add <dir> origin/integration/all-68-wip
# for each name N in merge_order_v3.txt:
git merge-base --is-ancestor origin/$N HEAD    # rc 0 = already in
# control: origin/agent/add-deepwiki-badge must NOT read as merged
```

Counting merge commits gives the wrong answer - a fast-forward leaves none. That
undercount already happened once here.

The order lives in `scratchpad/merge_order_v3.txt` (68 lines). If that is gone, it is the
60 lines of `merge_order.txt` with the numeric prefixes stripped, then the 8 above in the
order listed. Reconstructable from `git branch -r` in any case.

## Finishing it

1. Worktree from `origin/integration/all-68-wip`, merge the remaining 10 in order.
2. Expect heavy conflicts: these touch files the other 58 have already rewritten.
3. `ruff check .` clean, and the suite showing **exactly** the 4 known Windows failures
   (`testSecretKey.py::test_the_key_file_is_not_readable_by_others` and 3 in
   `testUserFilters.py`). Anything else is a real failure.
4. Push as `integration/all-68`.

### Do not stop at a green suite

The defect this pass exists to catch produced a completely green suite last time: #50
replaced the result tables with macros written against master and silently reverted #7's
rounding, and the tests moved with the macros so nothing failed. Compare the rendered
result tables cell by cell against the individual branches.

Other classes that have actually bitten here: two branches implementing the same visible
thing without conflicting; a stray `@bp.route` dragged in on a conflict tail; a filename
regex meeting a filename change; a "keep both sides" resolution rendering a block twice; a
constant defined twice; ADR files renumbered but their references not; and a dropped `}`
in `style.css` that reparented every rule after it into the dark-theme block. Several
branches now ship tests that pin these across branches - if one fails after a merge it is
working. Fix the tree, not the test.

## Still owed by the user

Two tokens need revoking: the Malpedia API token pasted into the session transcript, and
the GitHub OAuth token from an earlier session (https://github.com/settings/tokens).
Neither can be rotated from here - mcritweb 1.4.8 has no token rotation (that is issue
#100 / PR #111), so the Malpedia one needs an admin on that instance.
