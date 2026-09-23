Where this stands:

- #214 replaces the job page's meta refresh with polling a small status endpoint. While a job runs, the page reads only the job itself, and reloads only when something it shows has changed. Measured in Chromium against mcrit 1.9.0, with a 66-sample cross compare and a 1vN queued behind it: 1,230 backend calls on master, 850 with #214. The 1vN page went from 12 loads to 3 loads and 11 polls.
- The missing `not in families_by_id` guard on the family loops in `data.jobs` and `data.job_by_id` is in #145, so #214 leaves it alone.

With both merged, nothing in this issue is left, and it can be closed.
