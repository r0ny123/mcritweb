Title: Draw the match diagram with ImageDraw instead of per-pixel Python loops

## Summary
Fixes #188.

The stacked match diagram was filled one pixel at a time from Python. This PR moves both drawing primitives to `ImageDraw.rectangle`, and removes three smaller costs on the same path. The output is byte-for-byte identical.

## What changed
- `drawBlock` and `drawFrame` fill through `ImageDraw.rectangle` instead of nested Python loops.
  - `drawFrame` also wrote every exterior pixel twice with the same colour. That redundant second write is gone with the loop.
- `_calculateOutputMap` builds the reference sample and family sets once per render. Before, it built two singleton sets and a sorted list for every function.
  - The sample case only needs the size.
  - The family loop keeps its sorted order. The order in which families are first seen breaks ties between equally large clusters when the top clusters are picked.
- `processReport` computes the matchable and matched counts only when the debug record that uses them will be written.

## Why
Every 9×9 block cost 81 Python assignments, times three bands per instruction block, plus three frames the size of a whole band. All of that runs on the request path today, and after #145 it would still run in the background render.

Diagrams are cached by job id and never invalidated. The new renderer therefore has to produce exactly the old images, or old and new ones would sit side by side in the cache.

## Validation
- The new `tests/testMatchDiagramDrawing.py` pins the SHA-256 digests that master's renderer produced for:
  - every variant `data.py` draws (plain, famid, samid, funid) over the captured corpus;
  - the query report;
  - a synthetic 2500-function sample that wraps into many columns.
- The same file pins the full output map, and checks both primitives against the loops they replace.
- The primitive tests fail on master. The digest tests pass on both master and this branch by design.
- The full suite passes and `ruff check .` is clean.
- Live on a 13-sample instance (mcrit 1.9.0), jobs for samples 0, 3 and 7–12:
  - Direct `renderStackedDiagram`, master vs this branch on the same inputs: the PNG md5 is identical in all 30 variant renders. Render time is 16× to 123× faster, for example 437 → 7.8 ms, 328 → 20 ms, 219 → 6.1 ms.
  - `/data/result/<job>` with the diagram cache cleared before each request, over 23 job/variant pairs: the PNG md5 is identical in every case. Summed page time went from 21.1 s to 15.1 s, and the median from 1001 to 717 ms. No 500s.
- Live on a 66-sample instance (mcrit 1.9.0), every finished matching job: 61 1vN, 4 1v1 and 1 query job. With the diagram cache emptied before each request, 261 job/variant pages (plain, `famid`, `samid`, `funid`) produced PNGs byte-identical to master's. Summed page time went from 464.6 s to 250.8 s.
- The largest diagram there, the 1vN of an 11,598-function sample (2440×10043 px), renders in-process on the same inputs in 0.41-0.44 s instead of 7.0-7.3 s, for all four variants, with identical PNGs. Its page still takes 14.6 s cold, down from 21.8 s. Of that, 12.4 s is `getFunctionsBySampleId` fetching the 11,598 function entries, which #145 moves off the page request.

## Limitations
- Out-of-canvas behaviour of the two primitives changed: a block past the right or bottom edge is now clipped instead of raising `IndexError`, a negative x is clipped instead of wrapping, and a block size of 0 or less raises instead of drawing nothing. No caller reaches any of these. The layout keeps every block inside the canvas, and a review checked this over 208 synthetic renders at column-boundary sizes, plus all 52 live job/variant renders, all pixel-identical to master.
- The `getFunctionsBySampleId` call and rendering off the request are left to #145 and follow-ups. This PR is limited to the drawing and output-map code so the two merge cleanly (checked with `git merge-tree` against #145's head).

## Merge conflicts
- **#160, `MatchReportRenderer.drawFamilyLegend`.** #160 takes the border colour from `self.frame_color`, and this PR draws through `ImageDraw` instead of the pixel access object. Keep both. With that resolution, this PR's pinned digests and #160's own tests all pass on the merge: #160's default palette draws what master drew.
- #145 merges cleanly.
