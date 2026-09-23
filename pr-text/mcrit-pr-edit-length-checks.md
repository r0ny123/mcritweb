Title: Accept the empty and one-character values the edit messages allow

## Summary
Fixes #EDITS.

`PUT /samples/<id>` and `PUT /families/<id>` refused `""` and every one-character family name, although their messages allow 0-64 characters. They now accept what the messages describe, and they no longer let values with a trailing newline through.

**This must merge after #RENAMEPR, or together with it.** Once `""` is accepted, `PUT /families/0` with `family_name: ""` becomes possible. That is a rename of family 0 to its own name, which doubles family 0's counters until #RENAMEPR is in.

## What changed
- `SampleResource.on_put` and `FamilyResource.on_put`, `family_name`: `^(?![\-_.])(?!.*[\-_.]{2})(?!.*[\-_.]\Z)[a-zA-Z0-9._\-]{0,64}\Z`. It is one rule per lookahead: no separator first, none doubled, none last, over 0-64 characters from the same set as before.
- `SampleResource.on_put`, `version` and `component`: `^[ -~]{0,64}\Z` instead of `^[ -~]{1,64}$`.
- The messages are unchanged: they already said 0-64.
- New `tests/testEditChecks.py`, in the style of `tests/testJobResource.py`, drives both responders with a mocked index:
  - every value the messages allow is accepted and reaches `modifySample` / `modifyFamily` unchanged;
  - the values they rule out answer 400 and reach neither: separators first, last or doubled, a lone separator, a space, non-ASCII, 65 characters, a trailing newline;
  - an emptied version and component sent form-encoded, the way `McritClient.modifySample` sends them, arrive as `""` and are accepted.

## Why
- The family pattern ended in `[^\-_.].*[^\-_.]`, which needs a first and a last character, so it refused `""` and every single character, while its lookahead and its message allowed 0-64.
- The version and component patterns required `{1,64}` under a message saying 0-64.

What that blocked:
- `""` is what a sample submitted without a version or component carries. Once either was set, it could not be cleared again; MCRITweb's edit form sends an emptied field as `""` and got a 400.
- `""` is the name of family 0, so no sample could be moved into the unnamed family, nor a family merged into it.
- Submitting takes any family name, so a sample could be submitted into a family named `x` that no sample could be moved into afterwards.

The new patterns end in `\Z` rather than `$`, because in Python `$` also matches before a trailing newline. With `{0,64}`, `$` would let a lone `"\n"` pass as an empty value. Today it already lets `"ab\n"` pass as a family name and `"1.0\n"` as a version.

I kept the patterns inline where they were, rather than sharing one constant between the two resources, to keep the diff to the four lines that change.

## Validation
- Without the change, 12 of the 58 subtests fail: the 8 `""` and one-character values the messages allow, and the 4 trailing-newline values the old patterns let through. The form-encoded test fails with a 400.
- The new patterns against the old ones, over 37,210 generated strings of every length from 0 to 69 (letters, digits, separators, spaces, tabs, newlines, non-ASCII): the new ones accept exactly what the old ones did, plus `""` and single alphanumeric characters, minus values ending in a newline. A lone `-`, `_` or `.` stays refused, since separators only go between characters.
- Full suite against MongoDB 8.0: 324 passed, 107 subtests (main at 2ac8d7b: 319 passed, 49 subtests). `ruff format --check`, `ruff check` and `ty check` are clean.
- Live, through a server on this branch in front of a 1.9.0 corpus of 66 samples and its worker. Each step was checked on the sample or family afterwards, then undone:
  - clearing sample 16's version, and restoring it;
  - `component: ""` on a sample that already has none;
  - moving the sample into family 0 with `family_name: ""` (family 0 went to 1 sample and 1,059 functions, and fastlist to 1 sample and 951 functions), and back;
  - moving it into a new family `x`, and back; `x` was removed once empty;
  - moving it into a throwaway family, then merging that family into family 0 with `PUT /families/<id>` and `family_name: ""`; the family was gone and the sample in family 0; then back.
  - `-`, `ab\n`, `1.0\n` and a 65-character component still answered 400.
  - The sample and all 16 families ended identical to how they began.

## Limitations
- Submitting a binary still takes `family` and `version` unchecked. Checking them there would change what `mcrit client submit` accepts, which is a separate decision.

## Changelog
A proposed `[Unreleased]` entry. It isn't in the branch, so that this PR and the other open ones don't conflict in the same section:

> ### Fixed
> - `PUT /samples/<id>` and `PUT /families/<id>` refused `""` and one-character family names although their messages allow 0-64 characters, so a version or component could not be cleared once set, and no sample could be moved into family 0. A value ending in a newline, which `$` let through, is now refused ([#EDITS]).

## Merge conflicts
- None of its own. Against the 22 open PRs, it has only the conflicts main (2ac8d7b) already has since #163 and #169 were merged: #177 and #206 in `tests/testClientErrors.py`, and #183 in `mcrit/client/McritClient.py`. It merges with #177's and #178's changes to `SampleResource.py` and `FamilyResource.py`, and with #183's docstrings for both responders.
- In meaning: see the note on #RENAMEPR above. And #183's new docstring for `SampleResource.on_put` gives `version` and `component` as 1-64 printable characters; with this change it should say 0-64.
