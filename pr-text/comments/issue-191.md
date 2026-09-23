#221 does what MCRITweb can do on its own. It adds one per-request lookup helper, so no page asks for the same sample or family twice, or fetches an entry it already holds. The pages render the same HTML as before.

The rest needs the backend, because mcrit 1.9.0 has no way to ask for several entries in one request:

- **Samples and families.** The cross result page and the job page still make one request per sample, and one per family. danielplohmann/mcrit#BATCH asks for batch lookups, and danielplohmann/mcrit#BATCHPR implements them: `POST /samples/ids`, `POST /families/ids`, `McritClient.getSamplesByIds` and `getFamiliesByIds`.
- **Job dependencies.** `job_by_id` still makes one `getJobData` per dependency. danielplohmann/mcrit#SELECTOR / danielplohmann/mcrit#SELECTORPR let `GET /jobs` select jobs by id.

The MCRITweb side of both is ready as a draft, #F191PR, stacked on #221:
- `get_sample_entries` and `get_family_entries` send the ids they are missing in one request each;
- `job_by_id` reads its dependencies in one request.

Measured live against an mcrit server with both PRs, the job page of a 66-sample cross compare went from 134 backend requests to 4 (506 ms to 35 ms), and each page renders the same HTML as before. It raises the `mcrit` floor in `setup.py` and `requirements.txt`, so it stays a draft until that mcrit release. I'd keep this issue open until then.
