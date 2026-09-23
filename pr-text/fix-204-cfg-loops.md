Title: Stop rescanning the whole CFG per block and per back edge

## Summary
Fixes #204.

The issue names four spots in the CFG helpers. I measured each on the largest functions of the ripgrep sample (11,598 functions, up to 971 blocks and 86 loop back edges) before changing anything:
- `fetchDotGraph`'s per-block `replace()` loop: 42-181 ms. Now one pass.
- `getNodes` reversing the graph once per back edge: ~500 ms of `collect_loops`'s 667 ms on the biggest function. Now once per request.
- `collect_loops`'s comment claims a pool that never existed. The comment is corrected: running the work on a thread pool measured slower.
- `addParentInfo` is quadratic in the number of loops, but costs under 2 ms at the most any function of the ripgrep, fastlist and clipboardy samples has (86 loops). Left alone.

Both endpoints answer byte for byte as before.

## What changed
- **`mcritweb/views/explore.py`**: `fetchDotGraph` adds each block's picblockhash comment in one `re.sub()` over the graph text (`BLOCK_LABEL_RX`), instead of one `dot_graph.replace()` per block that rescanned the whole, already grown, string each time.
  - `smda`'s `SmdaFunction.toDotGraph` writes `,label="<offset>` exactly once per block node. The graph's own label has no leading comma, API references sit inside the instruction text, and edges carry no label. So the pattern matches each block once, and the offset it captures is the block's own.
- **`mcritweb/views/cfg_explorer_detector.py`**:
  - `collect_loops` reverses the graph once and passes the reversed copy to every back edge's `getNodes`, which used to build its own.
  - `getNodes` leaves the loop header out with `networkx.subgraph_view` instead of `remove_node`, so the shared copy is never changed by one back edge's search. Called without the reversed graph, it builds one as before.
  - `collect_loops`'s docstring no longer says the work is farmed out to a pool.
- **Tests**: `tests/testCfgLoopDetection.py` (new), with five real functions in `tests/fixtures/cfg_loop_functions.json` (21 KB, new). `tests/fixtures/README.md` notes that this file is not part of the corpus `regenerate.py` manages.

## Why
Each `replace()` rescans the whole graph text, so the old loop was O(blocks x graph size) per panel request. `graph.reverse()` copies the whole graph, and the copy does not depend on which back edge is being resolved, so building it per back edge repeated the same work up to 86 times.

## Validation
**Pure Python**, this branch's code imported directly, median of 5:

| function | blocks | back edges | label loop (master) | `collect_loops` (master) | `collect_loops` (this branch) |
|---|---|---|---|---|---|
| 9344 | 971 | 86 | 145.5 ms | 667.5 ms | 23.8 ms |
| 7642 | 951 | 9 | 180.9 ms | 61.7 ms | |
| 17689 | 890 | 25 | 125.3 ms | 152.2 ms | |
| 17888 | 782 | 40 | 86.5 ms | 207.7 ms | |
| 17356 | 765 | 47 | 94.6 ms | 179.6 ms | |
| 15293 | 523 | 9 | 42.2 ms | 31.4 ms | |

One `graph.reverse()` of the 971-block graph costs ~5.8 ms, so 86 of them were ~500 ms of the 667.

**Live**, against mcrit 1.9.0, master and this branch side by side, median of 5 requests:

| function | blocks | `fetchDotGraph` master | this branch | `findLoops` master | this branch |
|---|---|---|---|---|---|
| 9344 | 971 | 249.6 ms | 76.9 ms | 1574.5 ms | 1061.7 ms |
| 7642 | 951 | 242.4 ms | 84.7 ms | 538.4 ms | 482.7 ms |
| 17689 | 890 | 190.2 ms | 56.3 ms | 860.0 ms | 668.7 ms |
| 17888 | 782 | 156.4 ms | 47.5 ms | 589.0 ms | 364.7 ms |
| 17356 | 765 | 165.3 ms | 74.2 ms | 776.6 ms | 657.4 ms |
| 15293 | 523 | 92.0 ms | 62.5 ms | 266.0 ms | 226.8 ms |

- What `findLoops` still spends is almost all `dominanators`, which the issue does not name (see Limitations).
- Backend calls are unchanged: `fetchDotGraph` still makes one `getFunctionById`, and `findLoops` none.
- Other test runs shared the machine, so a repeat run was noisier, e.g. 335 → 86 ms for function 9344's `fetchDotGraph`. The direction held throughout.

**Same output**:
- `tests/testCfgLoopDetection.py` checks both endpoints against the previous algorithms, kept in the test as a reference, over five real functions: one without loops, one with a self-loop, and one with three back edges, one nested in another. All carry picblockhashes.
- Two of its tests pin the fix by counting calls, not by timing. `test_dot_graph_fixup_scans_the_graph_once_per_request` asserts one `sub()` per request, and `test_find_loops_reverses_the_graph_once_per_request` one `reverse()`. Both fail on master.
- `getNodes` is checked both with the shared reversed graph and without one, against the previous answer.
- The equivalence tests catch a deliberate mutation of either fix: one node dropped from `getNodes`'s answer, or an offset parsed one off.
- Live, master's and this branch's servers answered both endpoints identically for 949 real functions spread over all 66 samples, 728 loops among them, including the six in the tables. Imported directly, the same held for 240 functions from samples 23, 16, 17 and 19, with 1,669 loops between them.
- The function page and the function comparison page render identically. `tests/testFunctionVsBrowser.py`, which draws the loop highlighting in Chromium, passes.

**Suite**: 992 passed with Chromium available, and `ruff check .` is clean.

**Not adopted**: running `collect_loops` on a `ThreadPoolExecutor` sharing the one reversed graph took 28.5, 29.6 and 38.7 ms with 2, 4 and 8 workers, against 23.8 ms sequentially. The work is pure Python, so the threads only contend for the GIL.

## Limitations
- **`dominanators`** is O(n²) and the largest cost left in `findLoops`: 936 ms of 1,736 ms on the 971-block function. Replacing it with a near-linear dominator algorithm is a larger change than this issue asks for.
- **`addParentInfo`** is left as it is. With the loop count scaled up synthetically, it takes 4 ms at 200 loops, 123 ms at 1,000 and 4.2 s at 5,000, while no function of the ripgrep, fastlist and clipboardy samples has more than 86. If one ever does, this is the next place to look.
- **Offsets that share a hex prefix**: in a function whose block offsets share a hex prefix, such as 0x1000 and 0x10000, the old loop's `replace()` for the shorter offset also matched the longer block's label. That label got two `comment` attributes, the first carrying the other block's hash. Graphviz keeps the last attribute, so the page showed the same thing, but the text now carries one comment per block.
- **networkx**: `requirements.txt` still sets no floor for networkx. `subgraph_view` is in every networkx that installs on the Python 3.11 this project requires, 2.8 and later.
- **Traversal order**: the equivalence relies on `networkx` walking a filtered view in the same order as a graph with the node removed. That holds, since the view iterates the same underlying dicts, and it held on every function checked. No test pins networkx's own iteration order.

## Merge conflicts
- **#142** (`tests/fixtures/README.md`): #142 rewrites the file's last paragraph, and this PR appends a section after it. Keep #142's paragraph, then this PR's section.
- The other 28 open PRs merge cleanly, and so does every other branch of this set. None of them touches `cfg_explorer_detector.py`. #130, #173 and #210 change lines just above `fetchDotGraph`, without overlapping.
