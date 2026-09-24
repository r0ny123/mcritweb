# MCRIT live testbed

The local MCRIT and MCRITweb stack that the familiary/mcritweb and danielplohmann/mcrit PRs of
September 2026 were verified against, and the scripts that bring it back on a fresh machine.
This branch shares no history with MCRITweb; it can be pushed as it is to any repository.

| path | what |
|---|---|
| `data/mcrit-db.archive.gz` | the `mcrit` database, from `mongodump --archive --gzip` (mcrit 1.9.0, MongoDB 8.0; 44.6 MB) |
| `setup-live-stack.sh` | one-time setup: MongoDB with the corpus restored, a venv with mcrit and MCRITweb's requirements, a MCRITweb instance |
| `start-live-stack.sh`, `stop-live-stack.sh` | start and stop MongoDB, the mcrit server and worker, and MCRITweb |
| `make_instance.py` | create a MCRITweb instance folder: schema, server entry, test login |
| `tools/` | the scripts the live checks used |

## The corpus
- **66 samples in 16 families, 26,436 functions**: setuptools, distlib and installer launchers,
  pnpm's fastlist, clipboardy, windows-kill, mcrit's own SMDA test reports, 40 overlay variants
  (families `variants-0` to `variants-3`), ripgrep for Windows (11,598 functions), and a few
  samples submitted during checks.
- **428 jobs of every kind**: 1vN and 1v1 matches, cross compares of 40 and 66 samples
  (`6ab3b88c78ce0e8f2efec521`, `6ab3e4b03b24190e88fed7c9`), a binary query, unique blocks, and
  the three 1.9.0 repairs. One failed `updateMinHashes` job has no attempts left, so a worker
  leaves it alone.
- Family 0, the unnamed family, is empty.

`tools/check_corpus.py` checks the counts, and that every family's counters equal its samples
and functions.

## Quick start
```
git clone --depth 1 --branch live-testbed https://github.com/r0ny123/mcritweb testbed
git clone https://github.com/familiary/mcritweb          # or the checkout under test
testbed/setup-live-stack.sh mcritweb                     # once per machine, a few minutes
testbed/start-live-stack.sh mcritweb
```
- MongoDB on 127.0.0.1:27017, mcrit on http://127.0.0.1:8000, MCRITweb on http://127.0.0.1:5000.
- Login `analyst1` / `Passw0rd-live!` (admin). A local test login only; everything binds to
  127.0.0.1.
- Everything lives in `$LIVE`, by default `~/live-stack`: `db`, `logs`, `venv`, `pids`.
- MongoDB comes from a `mongod` and `mongorestore` on `PATH` if there are any. Otherwise it runs
  as the official `mongo:8.0` image through Docker, with host networking, and the setup starts
  `dockerd` when it isn't running. Some environments' network policy refuses
  `fastdl.mongodb.org`; Docker Hub and PyPI have been reachable.
- `start-live-stack.sh` runs MCRITweb with `FLASK_DEBUG=1`: otherwise its session cookie is
  `Secure`, and a login over plain http never sticks.
- To run a mcrit branch, e.g. one with new client methods, set `PYTHONPATH` to its checkout for
  `start-live-stack.sh`, or pass it to `tools/lw.sh`.

## Comparing a branch with its base
```
testbed/tools/lw.sh <base checkout> 5001 7811                       # base, behind a counting proxy
testbed/tools/lw.sh <branch checkout> 5002 7812 [8000] [mcrit checkout]
$LIVE/venv/bin/python testbed/tools/live_follow.py 5002 7812 / /explore/samples /data/jobs/6ab3e4b03b24190e88fed7c9
```
Per page, `live_follow.py` prints the backend calls the view made, counted by the proxies; the
median of 3 warm loads; and whether the HTML equals the base's, with CSRF tokens, nonces, timings
and ports taken out. Set `BASE_PORT` and `BASE_PROXY` for another base.

The other tools:
- `tools/crawl.py urls`, then `tools/crawl.py <base url> <tag>`: every listing, detail, result,
  download, link-hunt, CFG and admin page for this corpus, as `analyst1`; status codes go to
  `$LIVE/crawl/crawl_<tag>.json`. On familiary/mcritweb master (e4bfa55), 1,695 of the 1,849
  pages answer 200 and five answer 500. Two are GET `/admin/change_password` and
  `/admin/change_username`, rendering a documented 400 in debug mode. Three are the result pages
  of the 1.9.0 repair jobs, where `data.result()` falls off its end.
- `tools/check_corpus.py`: counts and family counters, read-only; exits nonzero if they changed.
- `tools/selector_live.py`: the `/jobs` selectors of danielplohmann/mcrit#214, against a server
  running that branch.
- `tools/web.py` (log in, read CSRF tokens) and `tools/countproxy.py` (the counting proxy).

## Care
- **Never point mcrit's test suite at 27017.** Its tests drop and rewrite their databases. Run a
  second MongoDB on another port for `TEST_MONGODB`.
- **Writes through the live API change the corpus**: a PUT, a submission, a DELETE, and any job the
  worker runs. Run `tools/check_corpus.py` afterwards. To go back, restore again:
  `docker exec -i mcrit-mongo mongorestore --archive --gzip --drop < data/mcrit-db.archive.gz`,
  or the same with a local `mongorestore --archive=data/mcrit-db.archive.gz`.
- **A storage object built from `McritConfig()` defaults writes to this corpus**: the default is
  MongoDB on 27017. Give scripts their own database name or port.
- **Stop processes by their pid files** in `$LIVE/pids`, or with a `pgrep`/`pkill` pattern
  anchored at `^`. An unanchored `pkill -f` pattern also matches the shell that runs it, when that
  shell's command line contains the pattern.
- Stop the worker (`$LIVE/pids/mcrit-worker.pid`) while comparing results that must not change.

## Moving it to another repository
The branch has its own history, so it moves as it is:
`git push https://github.com/<owner>/mcritweb live-testbed`.
