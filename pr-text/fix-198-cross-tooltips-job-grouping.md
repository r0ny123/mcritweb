Title: Build cross compare tooltips on hover, and group a job's samples in one pass

## Summary
Fixes #198.

**This PR is stacked on #182.** Its base is `fix/182-cross-compare-lazy-tabs`, the branch of #182, because both change how the cross compare matrix is written, and #182's tab filling has to know the new tooltip form. Please merge #182 first. This PR's base then becomes `master`: GitHub switches it by itself if #182's branch is deleted on merge, and otherwise it can be switched with Edit. The diff shown here is this PR's alone.

The cross compare result page wrote both samples' full description into the tooltip of every cell of every matrix. A cell now carries only its score line, each row carries the line naming its sample, and a small script joins them the first time the pointer reaches a cell. The text a user sees on hover is unchanged, character for character, in every cell of every tab. With #182, the 66-sample result page goes from 2,090,824 to 1,452,755 bytes, and its response from 465-470 ms to 366 ms.

The jobs table's cross compare row now groups the job's samples by appending to each family's list instead of rebuilding it, and a dead inner loop is gone.

## What changed
- **`templates/result_cross.html`**:
  - A cell's `data-hint` keeps only its first line, `MCRIT: <score>% (<n> matches) `.
  - Each `<tr class="sample-row">` gets `data-hint-sample`, the line naming its sample. It is written with the same template expression the cells used, so it is escaped and decoded exactly as before.
  - A delegated `mouseover` handler, bound on `document` in the head and limited to the matrices' cells, completes a cell's `data-hint` the first time the pointer reaches it. The cell's own row names the first sample, and the row at the cell's column names the second, since rows and columns come in the same order.
  - #182's tab filling now writes the score line alone into each cloned cell, where it used to keep everything after the cloned hint's first line. The rows it clones carry `data-hint-sample`, so the handler completes those cells too.
  - Click-through (`onclick`), colours and all other markup are unchanged.
- **`templates/table/job_row.html`**, in the cross compare branch of `job_description`:
  - `grouped_samples.update({fid: grouped_samples.get(fid, []) + [sid]})` becomes `grouped_samples.setdefault(fid, []).append(sid)`.
  - The empty `{% for family_id, sample_ids in grouped_samples.items() %}{% endfor %}` inside the loop over the families is removed.
- **Tests**: `tests/testCrossTooltips.py` and `tests/testCrossJobRow.py` (new). #182's `test_the_rendered_matrix_has_the_shape_the_script_clones_from` now checks that a cell's hint is exactly its score line.

## Why
**Tooltips.** hint.css shows `data-hint` through `content: attr(data-hint)` with `white-space: pre`. That makes the blank lines and the 12-space indentation, which leaked into the attribute from the template's own indentation, part of the visible text. The handler therefore rebuilds exactly `score line + "\n" + "\n" + 12 spaces + sample A + "\n" + 12 spaces + "\nvs.\n" + "\n" + 12 spaces + sample B`.

The handler runs inside the `mouseover` dispatch, and the browser paints only after that, so a tooltip should never show partly built. That is inferred from the event loop; the browser tests read the text after the pointer has moved, not the first painted frame.

I chose a per-row attribute over a JSON table of samples:
- **The text matches by construction.** The sample line goes through the same Jinja expression, HTML escaping and attribute decoding as before. A JSON table would decode a carriage return or NUL in a family name differently from the HTML parser, which turns CR into LF and NUL into U+FFFD in an attribute.
- **No id lookup is needed.**
- **#182 already clones the rows**, so their attributes travel with them.

The cost is one attribute per row: 25,692 bytes on the 66-sample page on master, against 3,835,656 bytes of sample text removed from the cells.

The score line stays in the cell. It differs per cell anyway, without JavaScript the tooltip still shows it, and it is exactly what #182's tab filling writes. The column's sample is found by position, which costs nothing per cell. A `data-` id per cell would cost about 15 bytes × n² × 6, roughly 390 KB for 66 samples.

**Job rows.** At live scale this cannot be measured in a page view: 66 samples in 16 families take 0.56 ms before and 0.49 ms after, the median of 7 renders over two rounds. It shows for large jobs, measured on synthetic `Job` objects rendered through the macro, since the corpus has no cross compare that large:
- 1,000 samples in 500 families go from 26 ms and 1.43 MB of output, mostly the dead loop's whitespace, to 10 ms and 181 KB;
- 4,000 samples in one family go from 34-35 ms to 17-21 ms.

The new code is shorter than the old.

## Validation
On the live backend (66 samples, 16 families), each column served side by side. Responses are medians of 5, interleaved; this shared machine varies by 10-20% between passes.

| /data/result/<job> | master | #182 | #182 and this PR |
|---|---|---|---|
| 15 samples, bytes | 709,070 | 159,294 | 126,104 |
| 40 samples, bytes | 4,122,075 | 807,383 | 583,154 |
| 66 samples, bytes | 10,930,771 | 2,090,824 | 1,452,755 |
| 66 samples, gzip -6 | 281,159 | 67,366 | 46,119 |
| 40 samples, response | 554-616 ms | 210-214 ms | 176 ms |
| 66 samples, response | 1207-1308 ms | 465-470 ms | 366 ms |

- **Backend calls** are unchanged: 34, 84 and 136 per request for the three jobs.
- **This change on its own**, on master without #182:
  - bytes 709,070 → 503,495, 4,122,075 → 2,770,266, and 10,930,771 → 7,095,922;
  - per-cell tooltip text drops from 35-41% of the page to 7-9%, the score lines;
  - Chromium's `load` event goes from 2288-2313 to 1209-1408 ms for 66 samples.

**Tooltips in Chromium**, compared with master for every cell of every tab of all 16 live cross compares and a custom order: 48,762 cells on 17 pages.
- Every cell reads master's `data-hint`, computed `::after` content, background colour and `onclick`, including the cells of tabs filled on click.
- This holds both when the first tab is hovered before the others are opened and when every tab is opened before any cell is hovered.
- Up to 25 cells per tab were hovered with the real pointer, and the rest received a dispatched `mouseover`; both give the same result.
- No page errors occurred.

**HTML**: for all 16 live cross compares and two `?custom=` orders, the page on master with only this change applied equals master's page with exactly the intended edits, and nothing else. On master, column j of every matrix names row j's sample, which the handler relies on.

**Job rows**, 112 pages: every job category with `plimit=250`, every state with `l=250`, all 66 `/explore/samples/<id>` pages, every cross compare's `/data/jobs/<id>`, `/` and `/data/jobs`.
- 108 are byte-identical to master.
- The other 4, the pages that list cross compares, differ only by the 520 whitespace-only lines (2,600 bytes over 16 rows) the dead loop printed.
- Chromium reports the same `innerText` and row heights for every job row.

**Tests**:
- `tests/testCrossTooltips.py`:
  - Offline, three tests: every cell carries only its score line; every row carries its sample's line; a family and version with `&<>"'\` and non-ASCII are escaped in the new attribute and decode back. All three fail against master's template.
  - In Chromium, skipped where Playwright is missing, as in CI: every tab is opened first, then the pointer moves over every cell, in clustered and in custom order, and the attribute and computed `::after` content are compared with the tooltip the old template wrote. These pass against master's template too, which shows the expected text is master's own.
  - They catch four deliberate breakages: no handler, the wrong column, row and column swapped, and one space less of indentation.
- `tests/testCrossJobRow.py`:
  - The grouping reads as before: families in order of first appearance, samples in job order, deleted samples left out.
  - The lines from one family to the next no longer grow with the number of families, 8 lines with 2 families and 46 with 40 on master. This test fails on master.
  - No list is concatenated in the cross compare branch. It reads the template's Jinja AST, since the output cannot show it, and fails on master.
- The full suite passes, 1009 passed, and `ruff check .` is clean.

## Limitations
- **Samples of family 0** are left out of a cross compare's job row. That bug predates this PR and is unchanged: `{% if sample_entry.family_id %}` is false for family 0, the unnamed family. Changing it changes the rows, so it is left for its own issue.
- **The tooltip is completed by script.** Without JavaScript, a cell shows its score line only. The handler is bound on `document` from the head, before the matrix is parsed, so there is no window in which a hover misses it.
- **The column's sample is found by position.** The handler assumes the matrix is the last n cells of a row, with columns in row order. #182's tab filling assumes the same, and `test_a_cell_carries_only_its_score_line` pins that order.
- **The tooltip keeps its odd layout,** with blank lines and a 12-space indent, since this change was meant to be invisible.
- **Compression shrinks the gain on the wire.** Behind a compressing proxy, the saving for 66 samples is 67,366 → 46,119 bytes gzipped, though parsing and DOM costs do not change with compression.
- **Leftover whitespace in the job row.** The per-sample loop in `job_description` still prints about nine whitespace-only lines per sample from the template's indentation. That is linear, predates this PR and is left alone.

## Merge conflicts
- **Carried from #182:** until #182 is merged, this branch carries #182's changes, and with them #182's conflicts with #159, #160, #210 and the #191 branch. #182's PR says how to resolve each.
- **#160** (`result_cross.html`): this PR adds one conflict of its own there. Both sides change the `<tr class="sample-row" ...>` line. Keep #160's `solid currentColor` and this PR's `data-hint-sample`:

  ```
        <tr class="sample-row" style="border: 0px solid currentColor; line-height: 0.7em;" data-hint-sample="{{ sample.sample_id }}: {{sample.sha256[:8]}} -- {{ sample.family }} {{ sample.version }} -- ({{sample.statistics['num_functions']}} func)">
  ```
- **#115, #117, #122, #126, #172 and #212**, which touch the same templates, merge cleanly.
  - #126 defers Bootstrap but keeps jQuery a plain script in the head, which the handler needs at parse time.
  - #159's ordering buttons carry their own `data-hint` outside `tr.sample-row`, so the handler ignores them.
- **Every other open PR** merges cleanly with this PR's own changes.
