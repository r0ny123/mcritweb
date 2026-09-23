Title: Memoize function comparisons by the content they are computed from

## Summary
Fixes #186.

The function comparison page (`/data/matches/function/<a>/<b>`) ran all four block-matching layers on every view, including the two `getSampleById` calls of the ad-hoc PicBlockHash layer. The combined graph (`/explore/fetchCombinedDotGraph/<a>/<b>`) ran the whole comparison once more, even right after the page had done so. A comparison is now memoized per server process, under a key that reflects the content it is computed from, and the combined graph reuses it. Within one comparison, each instruction is now escaped once instead of two or three times.

## What changed
- `mcritweb/views/memo.py` (new): the shared bounded memo. `BoundedMemo` is a least-recently-used store bounded by weight and guarded by a lock. `app_memo(app, name, bound, weigh=...)` returns a named memo kept per app, and `clear_app_memos(app)` empties all of them. The branches for #184 and #187 carry this file byte for byte, and `tests/testMemo.py` too, so the three PRs merge in any order.
- `mcritweb/views/functiondiff.py`:
  - The computation moves to `_compute_function_diff`, unchanged apart from the escaping below. `get_function_diff` keeps its name and signature, so `data.py` does not change.
  - `get_function_diff` is now the memoized entry point. It always returns the same four keys: `node_colors`, `node_matches`, `pairs`, and `combined_dot` (None until the combined graph is drawn). Without both xcfgs all of them are empty and nothing is memoized.
  - The memo is `app_memo(current_app, "function_diff", 64 MiB, weigh=_estimated_size)`. An entry holds the colours, the matches, the pairs and, once requested, the combined dot graph. It never holds function entries or xcfgs.
  - The key (`_memo_key`) is the backend URL, the two function ids, and a sha256 of each function's xcfg and of its stored PicBlockHashes. Both are serialised with `json.dumps(..., sort_keys=True)`.
  - A comparison is looked up only when both entries carry their xcfg; otherwise the result is empty, as before.
  - `get_combined_dot_graph` fetches both entries with their xcfg to take the key. When the page already memoized the comparison, it draws the graph from those colours, with no diff and no sample fetches. Afterwards it serves the graph from the memo.
  - `_escaped_blocks` escapes every instruction once per comparison. Layer 1, layer 4 and the combined graph's "does B differ" check read from it. Layer 4 keeps the unescaped mnemonic it always used, so a jz and a jnz still differ there and the colours don't change.
- `mcritweb/views/administration.py`: `reset_server` calls `clear_app_memos`, which replaces the old TODO. This is the same hook as in #184 and #187.

## Why the key is what it is
The colours are computed from three things:
- the two xcfgs
- the PicBlockHashes the backend stores (layer 3)
- each function's sample base address and size (layer 2)

Each of these can change under an id, or can't, as follows (mcrit 1.9.0's MongoDbStorage):
- `recalculateAllPicHashes` rewrites the stored PicBlockHashes in place, and the admin page schedules it.
- `clearStorage` (a reset) restarts the id counters, so the same id can name another function afterwards. This is true even when the reset was done by another worker, mcrit's own client, or a second front-end.
- Most functions store no PicBlockHashes (1785 of the 2732 on the test instance). For those, only the xcfg tells the old function from the new.

So the key carries a digest of both, and it reflects the content of the two entries. An entry for a function that has since changed under its id is not found, rather than served. `reset_server` clearing the memo frees that worker's memory early; correctness doesn't depend on it.

A sample's base address and size are never rewritten, and they are not in the function entries. The ids stand in for them.

Function names and labels can change, so they are not memoized; the page reads them from the backend on every view.

## Validation
- Tests in `tests/testFunctionPages.py`, plus the shared `tests/testMemo.py`:
  - Fail on master, pinning the fix: a repeated comparison makes no `getSampleById`/`getFunctionById` calls; the combined graph after the page fetches only the two entries and draws the same graph; `reset_server` clears the function diff memo.
  - Guards that pass on master and would catch an unsafe memo:
    - Recalculated PicBlockHashes give fresh colours.
    - A reused id, with empty PicBlockHashes and another function swapped in under it, gets fresh colours and a fresh combined graph.
    - A dropped disassembly makes the combined graph answer empty and the page render empty colours.
    - Function names are not memoized.
    - The memo is per backend.
    - An empty comparison is not kept.

    The PicBlockHash test fails if its digest is taken out of the key, and the reused-id test fails if the xcfg digest is.
  - Also added: a two-block jz vs jnz test pinning layer 4's raw-mnemonic behaviour, and one showing that a drawn combined graph weighs more in the memo. `test_an_a_block_without_a_partner_is_drawn_a_only_in_red` now calls `_compute_function_diff`, since it needs the smda functions. These error on master only because they import helpers that are new here.
  - The full suite passes and `ruff check .` is clean. `git merge-tree` with #145 is clean.
- Live, against the coreutils 1vs1 job (ls vs cp), with a counting proxy between mcritweb and the backend. Timings are from 3 alternating rounds on freshly started servers, repeat = median of 9, on 4 shared CPUs:

  | | master | this branch |
  |---|---|---|
  | page, backend calls, repeat view | 8 | 6 (no `getSampleById`) |
  | page repeat, 1179/1589 (~370 blocks each) | 199-264 ms | 112-160 ms |
  | page repeat, smaller pairs | 87-147 ms | 50-92 ms |
  | combined, backend calls | 7 every time | 5 (the two xcfg entries, ~192 KB for 1179/1589; no samples, no diff) |
  | combined repeat, 1179/1589 | 252-294 ms | 57-100 ms |
  | combined repeat, smaller pairs | 68-149 ms | 33-80 ms |
  | cold first page view | unchanged within noise | |

  - The digests computed from `getMatchFunctionVs`'s entries and from `getFunctionById(..., with_xcfg=True)` agree for all 33 matched pairs, so both routes take the same key. The combined graph after the page runs no diff.
  - The xcfg digest costs about 1 ms for the largest functions here.
  - In process, the comparison of 1179/1589 went from 155 to 130 ms, or 216 to 148 ms with its combined graph, from the single escaping pass.
  - Page colours and matches, combined graphs and both side-pane graphs are byte-identical to master for five pairs (40 responses).
  - In process, `_compute_function_diff` and the combined graph are identical to master's for 103 pairs, reversed ones included.
  - In Chromium, both panes and the combined view render with the same fills on repeat loads, with no JS errors.
- Memory: the estimate charges 160 bytes per block, match or pair, plus the dot graph. That is deliberately conservative: tracemalloc put the real cost at 85-100 bytes per item, about half. The largest pair here is charged about 0.9 MB, so the 64 MiB bound holds at least 70 comparisons of that size per process, or several thousand small ones, and real use stays well under it.

## Limitations
- The trade-off is modest. The memo saves about 0.05-0.2 s per repeat view on the largest functions here, and less on small ones. It costs about 150 added lines in `functiondiff.py` plus the shared memo module. The single escaping pass (`_escaped_blocks`) stands on its own and speeds up every first view too. It could be taken without the memo if the memo is judged not worth it.
- The combined route still fetches both functions with their xcfg on every call, since the key is taken from them and a dropped disassembly must be noticed. It saves the diff, the two sample fetches and the drawing, not those two downloads.
- The two side panes (`explore.fetchDotGraph`) still fetch their function's xcfg on every page load. They don't use the comparison and are shared with the single-function page, so they are left for a follow-up.
- The key doesn't cover the sample's base address and size. A function under a reused id with a byte-identical xcfg but a sample loaded at another base could be served the old ad-hoc PicBlockHash colours.
- The memo is per process, and each worker fills its own.
- Two concurrent first views of the same pair both compute it.
- The byte weight is an estimate, and the 64 MiB bound is a module constant.

## Merge conflicts
Merges cleanly with every open PR.
