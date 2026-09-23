I checked both halves. Neither needs a PR of its own.

**DataTables.** The initializer in `templates/jobs.html` (lines 14-15 at e4bfa55) selects `#job-table`. But the page renders its table with the selected method as its id (`job_table(jobs, table_id=active, ...)`, line 161), so it never matched anything. #126 removes it, along with the DataTables assets.

**Per-row click bindings.** They don't cost enough to change:
- No table gains rows after `$(document).ready` on master.
- Page sizes are capped at 250 rows (`cursor_pagination.py:167` and `pagination.py:82` at e4bfa55).
- Measured in Chromium against master at 250 rows a page, median of 5 navigations:

| page | rows | load, ms | ready handlers, ms | share |
|---|---:|---:|---:|---:|
| `/explore/functions?limit=250` | 250 | 187.3 | 0.20 | 0.11% |
| `/explore/samples/23?limit=250` | 250 | 304.8 | 0.50 | 0.16% |
| `/explore/samples?limit=250` | 66 | 281.5 | 0.20 | 0.07% |
| `/explore/families?limit=250` | 16 | 151.9 | 0.10 | 0.07% |
| `/data/jobs?l=250` | ~250 | 246.7 | 0.30 | 0.12% |

A synthetic page of 11,598 rows, sample 23's full function count, which no page can show, binds in 28.6 ms directly and in 0.3 ms delegated.

`docs/adr/0014-no-htmx-for-table-reloads.md` lists delegating these handlers as the precondition for partial table reloads, which it declined. So nothing needs it today.

I'd close this once #126 is merged.
