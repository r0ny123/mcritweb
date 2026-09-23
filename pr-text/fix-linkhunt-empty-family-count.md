Title: Default the link hunt's family count when the form leaves it empty

## Summary
Fixes #NNN (the issue in `pr-text/issue-new-linkhunt-family-count.md`, once it is filed).

A link hunt filter submitted with "Unpenalized family count" left empty was a 500. The count now defaults to 2, the value both of the page's presets use.

## What changed
- `data.linkhunt_for_sample_or_query`: after the two presets, a `None` count becomes 2, with a comment saying why.
- New `tests/testLinkHuntFilters.py`, three tests:
  - two filters submitted with the count empty (`filter_link_score`, `filter_min_score`): the page renders, and the form shows 2;
  - a count that is given is kept.

## Why
The form sends every field, and an empty one parses to `None`. mcrit's `getLinkHuntResults` compares this count to an int (`MatchingResult.py:530`), so `None` raised a `TypeError`. The other numeric fields can be empty: the "clear" preset already sends `None` for every one of them.

## Validation
- The two empty-count tests fail on master with that `TypeError` and pass here. The given-count test passes on both.
- Full suite and `ruff check .` pass.
- Live against mcrit 1.9.0, on the 11.6k-function sample's 1vN job:
  - `filter_link_score=5` with the count empty: master 500, this branch 200;
  - `filter_min_score=70` with the count empty: master 500, this branch 200.

  Six other link hunt pages are byte-identical to master once CSRF tokens are blanked:
  - a 1vN job and a query job, each on the default filters and cleared;
  - the 1vN job with a count of 3 and with a count of 2.
- Merges cleanly with every open PR.
