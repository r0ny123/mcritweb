Title: Drop id checks that repeat the fetch right after them

## Summary
Fixes #207.

Four places asked the backend whether an id exists and then fetched the entity. The fetch already answers None for an unknown id, so each check cost one extra request. This PR removes the checks and branches on the fetch's result. For the single-sample export the lookup also caused a bug. An unknown id left an empty selection, which the backend reads as "every sample", so the export button for a bad id downloaded the whole corpus. The family export had the same bug for a family without samples, and returned a 500 for a family the backend does not know.

## What changed
- `data.match_functions` (`/data/matches/function/<a>/<b>`): calls `getMatchFunctionVs` directly instead of calling `isFunctionId(a)` and `isFunctionId(b)` first. `MatchResource.on_get_function_vs` checks both ids itself and answers 404, which the client turns into None. That None now takes the existing "One of the function_ids is not valid." branch. Before, a None after both checks had passed, i.e. a backend error on the comparison itself, went on into `match_info["function_entry_a"]` and returned a 500.
- `data.result_matches_for_sample_or_query` (`?samid=`): made `isSampleId(id)` and then `getSampleById(id)`, two requests to the same `/samples/<id>`. One `getSampleById` is now bound in the `elif`. An unknown id still falls through to the next branch as before. `api.py` already uses `:=` in an `elif` chain.
- `MatchReportRenderer.processReport`: calls `getFunctionsBySampleId` without the `isSampleId` before it. `SampleResource.on_get_functions` runs the same `isSampleId` check and answers 404, so None is still the "unknown sample" answer, and a query report's negative id behaves as before.
- `data.specific_export`:
  - Both branches now accept only a plain number of 1 to 18 ASCII digits as the id (`re.fullmatch(r"[0-9]{1,18}", item_id)`). Anything else, such as `abc`, `-1`, `1,2`, fullwidth digits or a 5000-digit id, gets a flash and a redirect to the export page without reaching the backend. `str.isdecimal()` was not strict enough: it accepts fullwidth digits, and a 5000-digit id then fails in `int()` with a 500.
  - Single sample: passes the id straight to `getExportData([id])`. `MinHashIndex.getExportData` leaves out ids it does not know, so an export with `num_samples == 0` means there was no such sample. The route reports that with a flash ("… it may not exist, or MCRIT could not export it.") and a redirect to the export page, as it already does for an unknown export type. The wording also covers a real sample whose export hit `STORAGE_MAX_EXPORT_SIZE`.
  - Family: `getSamplesByFamilyId` answers `{}` for a family without samples, and `_deleteFamilyIfEmpty` never deletes family 0, so family 0 can be empty. An empty family used to reach `getExportData([])`, a full-corpus export. An unknown family answered None, and `.values()` raised a 500. Both, and a failed export, now get a flash and the redirect.
- `tests/conftest.py`: the `RecordingMcritClient` docstring explained its narrow `isSampleId` commitment with the `match_functions` TypeError this PR fixes. I shortened that paragraph.

Left alone:
- `analyze.unique_blocks` keeps its per-id `isSampleId`. mcrit 1.9.0 has no REST lookup for several sample ids at once: `getSamples` returns the whole collection, and `getSampleEntriesByIds` is storage-internal. That check also guards a submit rather than repeating a fetch, and its comment explains why a 500 must refuse the submit.
- `explore.fetchCombinedDotGraph` also calls `isFunctionId` twice before `get_function_diff` fetches both functions. There the check does change what happens next: it spares the two `with_xcfg` fetches for an unknown id, and `test_the_combined_graph_route_validates_the_ids` pins that.

## Why
Each removed check requested the same backend resource as the call after it, or a resource the next call validates itself on the server, so none of them gave any information the fetch did not. For the export, the lookup was also what turned an unknown id into a full-corpus download.

## Validation
- New tests, 18 of which fail on master:
  - `tests/testFunctionPages.py`:
    - the comparison page makes no `isFunctionId` call and one `getMatchFunctionVs` call;
    - a backend that knows both functions but fails the comparison gets the flash, not a 500.
    - An unknown-id test pins the flash. It passes on both master and this branch.
  - `tests/testResultPages.py`:
    - `?samid=` makes exactly one `getSampleById` and no `isSampleId`, for a sample report and a query report, with the diagram drawn on the same request;
    - an unknown `samid` still renders the whole report. This passes on both.
  - `tests/testSpecificExport.py` (new):
    - a known sample is exported with a single `getExportData([id])`;
    - an unknown id asks for `[9999]`, not `[]`, and flashes;
    - a family is exported with its sample ids; an empty family (0) and an unknown one (99) get a flash, with no `getExportData` call;
    - `abc`, `-1`, `1,2`, fullwidth digits and a 5000-digit id never reach the backend, for both branches.
- Full suite: 983 passed, 23 skipped. `ruff check .` is clean.
- Live, against the MCRIT 1.9.0 test instance, with a counting reverse proxy between mcritweb and the backend. The counts are backend requests per page view and include the reachability ping `mcrit_server_required` makes on every request. Result JSON was cached before the runs. The "fresh" rows cleared `instance/cache/diagrams` first. The query job is `getMatchesForSmdaReport` on mcrit's `tests/example_report.smda`, reference sample -1.

  | page | master | this branch |
  |---|---|---|
  | `/data/matches/function/1016/1486` (from the 7 vs 8 job) | 8 | 6 |
  | `/data/matches/function/1016/99999999` | 3, flash | 2, same flash |
  | `/data/result/…57a0?samid=8` | 7 | 5 |
  | `/data/result/…57a0?samid=9999` | 3 | 3 (falls through, as before) |
  | fresh diagram, 1vsN `…57a0` | 4 | 3 |
  | fresh diagram, 1vsN `…57a0?samid=8` | 7 | 5 |
  | fresh diagram, query job | 4 | 3 |
  | fresh diagram, query job `?samid=0` | 7 | 5 |
  | `/data/specific_export/samples/12` | 3 | 2 |
  | `/data/specific_export/samples/9999` | 3, **2,498,987-byte export of all 13 samples** | 2, redirect and flash |
  | `/data/specific_export/samples/abc` | 3, the same full export | 1, redirect and flash |
  | `/data/specific_export/family/1` (coreutils) | 3 (same calls as the branch, by reading the code) | 3, all 4 samples (1,386,619 bytes) |
  | `/data/specific_export/family/99` | 500 (reported in review) | 2, redirect and flash |
  | `/data/specific_export/family/abc`, `family/-1`, `samples/<5000 digits>`, `samples/１２` | | 1, redirect and flash |

  - Every HTML page is identical to master's apart from the per-session CSRF token.
  - The four diagram PNGs are byte-identical (sha256).
  - The export of sample 12 is identical once the compressed function blobs are decoded.
  - The flask log shows no tracebacks.
  - On this instance family 0 holds samples 0-6, so the empty-family case is covered by the tests, not live.

## Limitations
- The client's `handle_response` turns both a 404 and a 500 into None. On a backend error the comparison page therefore says "One of the function_ids is not valid." That is also what master said when the error hit one of the `isFunctionId` checks, and before this PR an error on the comparison itself was a 500. Telling the two apart needs the raw response, so it is left for another change.
- An export for an id the backend no longer has, or for an empty family, now answers with a flash instead of a file. Before, it answered with the whole corpus, so no working behaviour is lost.
- The `?samid=` hunk conflicts with #145, which removes the `create_match_diagram` line between the two lines changed here. To resolve it, drop both lines. Merges with #186 and #188 are clean, and their tests pass on the merged trees.

## Merge conflicts
- **#130** (`data.py`): #130 wraps `getMatchFunctionVs` in `require_result(...)` behind the `isFunctionId` pre-check, and `getSamplesByFamilyId` in the family export. Here a `None` from either is handled in the view: it means an unknown id as often as a backend error. Keep this PR's `match_functions` and `specific_export`. A message that names both possibilities is #130's to add.
- **#145**: the `samid` hunk, as described under Limitations.
- Every other open PR merges cleanly.
