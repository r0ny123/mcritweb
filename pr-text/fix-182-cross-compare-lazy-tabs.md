Title: Render only the visible cross compare matrix, fill the other tabs on first click

## Summary

Fixes #182.

The cross compare result page used to render all six N×N matrices and hide five of them. It now renders only the tab shown on load and fills each other tab in the browser the first time it is opened. The data for those tabs is sent with the page, so opening a tab costs no request to mcritweb or to the backend.

- **N=130 samples:** the page goes from 39.0 MB to 7.4 MB, and server time from 6.0 s to 1.2 s.
- **N=13 samples:** 519,588 → 123,455 bytes. Gzipped, 26.4 KB → 13.3 KB.

## What changed

- `mcritweb/views/cross_compare.py`: new `lazy_cross_panes()`. For every method except the rendered one it builds:
  - the sample order;
  - per cell, in that order: the score to two decimals, the match count, and the colour as an index into a small shared palette.
  
  The colour is still chosen by `score_to_color` from the unrounded score, on the server. So JS has no copy of the colour logic, and a cell just under a threshold keeps its colour.
- `mcritweb/views/data.py`: `rendered_method` is `unweighted` if the result has it, otherwise the result's first method. The view passes it and `lazy_panes` to the template.
- `mcritweb/templates/result_cross.html`:
  - Only `rendered_method` goes through `cross_table`. The other panes are empty and marked with `data-lazy-method`.
  - The tab buttons are one loop over the six methods, and the active one is `rendered_method`. The sample count and the drag-and-drop list also use `rendered_method` instead of a hard-coded `unweighted`.
  - The data travels as `<script type="application/json">{{ lazy_panes|tojson }}</script>` and is parsed on the first click.
  - A `show.bs.tab` handler fills a pane by cloning the rendered pane's rows and cells, matched by sample id so that a different order works. It then patches in the order, the fifth-index header, each cell's colour, the score line of each tooltip, and the edit button ids.
  - The `td.clickable` row handler is delegated from `document` so that it reaches cloned rows. Cloned clipboard buttons get their tooltips.
  - The script returns early when there is no rendered matrix, and ignores a tab whose method the result does not have.
- `AGENTS.md`: the note that row-click handlers are bound directly now names this delegated handler as the one exception.
- `tests/testCrossLazyPanes.py`: new, 16 tests (see Validation).

## Why

All six matrices were rendered while only one was visible, so the page grew with methods × N² whether another tab was ever opened or not.

Cloning from the rendered pane keeps links, the edit modal's data and the sample half of each tooltip in one place, the `cross_table` macro, instead of repeating that markup in JS. Only what really differs between methods is sent, at about 11 bytes per cell against about 485 bytes per rendered cell.

A small endpoint that serves the other panes was the alternative. It would have to fetch the job and every sample from the backend again on each first click. It would also hand back markup to swap into the page, which docs/adr/0014-no-htmx-for-table-reloads.md (ADR-0014) declined.

## Validation

- **Tests:** `tests/testCrossLazyPanes.py` has 16 tests. They check that:
  - only N² cells are rendered;
  - the other panes are empty but still targeted by their tabs;
  - per method and per cell, the sent data matches the report: the formatted score, the match count, and `score_to_color` of the unrounded score;
  - the rendered method is not sent twice;
  - `?custom=` reaches the lazy panes;
  - a method with its own shuffled `clustered_sequence` is sent in that order;
  - a result without `unweighted` renders and activates its first method;
  - the rendered matrix still has the shape the script clones from: `tr.sample-row`, `td.id`, the `td[align]` header cells, a fixed number of leading cells, and a tooltip whose first line ends at the first newline.
  
  On master, 15 of the 16 fail. The shape test passes there, as it should, because it pins the unchanged macro. The full suite and `ruff check .` pass.
- **Live, cross compare over 13 samples:** 519,588 → 123,455 bytes (gzip 26.4 KB → 13.3 KB). Tooltip cells in the HTML: 1,014 → 169.
- **Playwright:**
  - It clicked every tab and compared each cell's text, tooltip, computed colour, link and edit button data against master's rendering of all six matrices. 0 differences over 2,086 cells, in both the default order and a `?custom=` order.
  - Two methods were given a different order than the rendered pane, and compared with master's render of that order: 596 cells, 0 differences.
  - On a filled pane, the edit modal, clipboard tooltip, row link and cell link work. There are no JS errors.
  - A result with only `score_weighted` and `frequency_weighted` renders `score_weighted`, fills `frequency_weighted` on click, and shows no JS errors when the tabs of missing methods are clicked.
- **N=130 samples:** 39.0 MB → 7.4 MB, and server time 6.0 s → 1.2 s. (The live backend has 13 samples. N=130 was made by repeating the ids ten times in `?custom=`, on the same live cross job, master against this branch.)

## Limitations

- The per-cell tooltip is left as it is and now dominates the page; that is #198. The per-method scores are now in the page, which a tooltip built on hover can reuse. If the cell markup changes there, the one-line patch in the fill script has to follow; a comment in the macro points to it.
- Opening a tab of a very large job clones N² cells in the browser, once.
- Filling a tab needs JavaScript, as the tabs themselves already do.
- #159 conflicts with this only on the `cross_compare` import line in `data.py`. Its named orderings feed the same per-method sample lists and carry over to the lazy panes.

## Merge conflicts
- **#159** (`result_cross.html`, `data.py`): the "Cross Comparison of N samples" line and the `cross_compare` import line. Keep both changes: #159's wording with this PR's `samples[rendered_method]`.
- **#160** (`result_cross.html`): the function-count cell's colour and the comment line after it. Keep both.
- **#210** (`AGENTS.md`): both edit the "Tables reload by navigating" bullet. Keep both edits.
- Every other open PR merges cleanly.
