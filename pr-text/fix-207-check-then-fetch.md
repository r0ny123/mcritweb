Title: Drop the existence probe in front of fetches that already answer for an unknown id

## Summary
Addresses #207.

Three of the check-then-fetch pairs in #207 were a second round trip to learn something the fetch that follows already reports. Each fetch answers `None` for an unknown id, so the probe added nothing.

## What changed
- `data.match_functions`: calls `getMatchFunctionVs` directly and branches on `None`. Before, it asked `isFunctionId(a) and isFunctionId(b)` first, and mcrit's `MatchResource.on_get_function_vs` runs those same checks again server-side.
- `data.result_matches_for_sample_or_query`: the `samid` filter now reads the sample once with `getSampleById` and keeps the entry. Before, it called `isSampleId` and then `getSampleById` two lines later.
- `MatchReportRenderer.processReport`: calls `getFunctionsBySampleId` for the reference sample directly, and falls back to `{}` when it answers `None`. That is the same fallback the `isSampleId` guard selected.
- New test `test_the_comparison_page_reports_an_unknown_function_id_instead_of_500ing`: an unknown function id still lands on the friendly flash.

## Why
Every one of these pairs asked the backend the same question twice, back to back, on pages that are already backend-bound.

## Validation
- Full offline suite and `ruff check .` pass.
- Live against mcrit 1.9.0 (64 samples, including an 8.5k-function sample). Backend calls per page view, counted from the server's request log:

  | Page | master | this branch |
  |---|---|---|
  | `/data/matches/function/357/358` | 8 | 6 |
  | `/data/matches/function/357/999999` (unknown id) | 3 | 2, same flash |
  | a 1vN query result with `?samid=8` | 7 | 5 |

- The rendered HTML is identical to master on both function-compare pages and on these result pages:
  - a 1vN query result, plain and with `samid=8`;
  - an 8.5k-function 1vN result, plain and with `samid=8`;
  - a 1vN result with `samid=12`, and with an unknown `samid=99999`.

  The query result has a negative sample id. I compared everything after blanking CSRF tokens.
- I cleared and regenerated the match diagrams for those jobs; their PNGs are md5-identical to master's.

## Limitations
- The single-sample export branch (`specific_export`) is left alone. Its `getSampleById` is not only an existence check: when it returns `None`, the route calls `getExportData([])`, which asks the backend for `/export/` and gets back the whole corpus. That is a separate bug, filed on its own. Collapsing the round trip there needs that fix first.
- `unique_blocks`' per-id `isSampleId` validation is deliberate, as the issue says. It stays.
- **Conflict with #145, `data.py`, the `samid` branch.** #145 drops that branch's `create_match_diagram` call and this PR drops its second `getSampleById`. Whichever lands second deletes both lines and keeps this PR's walrus lookup.
- **Conflict with #130, `data.py`, `match_functions`.** #130 wraps `getMatchFunctionVs` in `require_result(...)`, which turns a `None` into its backend-failure page. Here `None` means "unknown id", so a plain merge would show the failure page for a mistyped id. The mcrit 1.9.0 client answers `None` for a 404 and a 500 alike (its `handle_response`); only a connection error raises. If #130 lands first, keep the `isFunctionId` pre-check in `match_functions` and take only the other two changes from this PR.
