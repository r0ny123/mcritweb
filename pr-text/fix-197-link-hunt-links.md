Title: Page the link hunt clusters and fold long clusters

## Summary
Fixes #197.

The link cluster table rendered every cluster, and every link of every cluster, on one page, with a WIP comment in the cell. This PR pages the cluster list and folds long clusters.

## What changed
- `views/data.py`: a `Pagination` for the cluster list (`clup`/`clul`, 10 per page), next to the existing `funp`/`funl` one for the individual links.
- `templates/linkhunt.html`:
  - The cluster loop renders only the current page, and ranks keep counting across pages.
  - A cluster shows its first eight links, in two lines of four as the cell already broke them. The rest sit behind `<details><summary>N more</summary>`, one click away and without any script.
  - The WIP comment that was repeated for every link is gone.
  - The pagination widget sits under the table, anchored to the "Link Clusters" heading.
  - The "Link Clusters" and "Individual Links" headings get their own ids. Both used to share `linkhunt-matches` with the "Results" heading, so the existing individual-links pager jumped to the top of the results instead of to its table.

## Why
AGENTS.md says in-memory lists are paged with `Pagination`, as the family, sample and library tables of a result already are. `<details>` gives the "first few plus a count, the rest on demand" shape with no new JavaScript. Link markup and order are unchanged.

## Validation
- `tests/testLinkHuntLinks.py` runs on the captured corpus, which has 16 clusters of 2–17 links. It checks that:
  - page 1 shows 10 clusters, and pages 1 and 2 together equal the full list with continuous ranks;
  - clusters of more than 8 links show 8 plus "N more", with all the rest inside `<details>`;
  - paging links keep the filters and `funp`.

  A fourth pins that each pager anchors to its own heading. All four fail on master, where three headings share one id.
- The full suite and `ruff check .` pass.
- Live, on the 1vsN jobs of samples 7 and 8 with 7 filter sets each:
  - cluster rows and every link are identical to master;
  - for sample 8 with the filters cleared, the 80-link cluster now shows 8 links plus "72 more". Its row is 82 px tall, and 471 px when expanded;
  - the cluster table shrinks from 38,987 to 33,498 B, and the page from 168,890 to 165,178 B;
  - there are no console errors.
- Repeated on a second instance, with 66 samples, where the paging is reached for real. Of its 61 finished 1vsN jobs, 7 have more than 10 clusters: 42, 37, 31, 30, and 28 three times. On the two largest, with three filter sets each:
  - every cluster's links, in order, are identical to master once the folding is ignored;
  - page 1 plus page 2 equals the full list (`clul=250`), with continuous ranks;
  - every cluster of more than 8 links shows 8 plus "N more" with the rest folded. The largest has 175 links: its row is 82 px tall folded and 989 px expanded;
  - the cluster pager keeps the filters and `funp`;
  - the page differs from master only in the cluster table and the two heading ids. Master gives three headings the same id `linkhunt-matches`;
  - a job with no clusters still renders.

## Limitations
- Folded links are still in the HTML. What bounds the page size is paging the clusters.
- Request time is unchanged; that is #187.

## Merge conflicts
Merges cleanly with every open PR.
