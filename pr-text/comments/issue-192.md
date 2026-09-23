#222 fixes the submit form half. `/data/submit` no longer downloads the whole family table, and its family field uses the same bounded type-ahead as the listing pages: at most 10 suggestions, from `search_families`.

The queue half can't be bounded correctly from MCRITweb:
- `GET /jobs` has no way to select the jobs of the 25 samples on a page.
- A newest-N `limit` would silently undercount the badges, and drop the "Last 1:N Job" link for any sample whose jobs are older than the window.

Measured on a 1.9.0 instance with 214 matching jobs, each samples or family page view reads 159,714 bytes of queue data today.

danielplohmann/mcrit#SELECTOR asks for a `sample_ids` selector on `/jobs`, and danielplohmann/mcrit#SELECTORPR implements it. The MCRITweb side is ready as a draft, #F192PR, stacked on #222. `sample_row_job_collection` passes the page's sample ids with its two requests, and keeps `filterToSampleIds` as the exact check, so the badges and links stay as they are. Measured live, a two-sample family page's queue reads went from 159,714 bytes to 8,278, and the first 25-sample listing page's to 85,161, with the same HTML. It raises the `mcrit` floor, so it stays a draft until that mcrit release. I'd keep this issue open until then.
