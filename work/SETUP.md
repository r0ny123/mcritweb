# SETUP — how to run and reproduce, in this environment

Recorded 2026-08-29. Everything below was actually executed; the outputs quoted are real.

## What is available and what is not

| layer | status |
|---|---|
| Python 3.11.15 | available |
| MCRITweb + deps (`requirements.txt`) | installed into `.venv` (see below) |
| offline test suite (`pytest`) | **239 passed** |
| `ruff check .` | **All checks passed!** |
| Flask dev server (`flask run`) | boots, serves `/register`, `/login` |
| **real MCRIT backend** (mcrit-server + worker + MongoDB) | **NOT available** |
| Docker daemon | **NOT available** — `docker info` → `failed to connect to the docker API at unix:///var/run/docker.sock` |
| MongoDB (`mongod`) | not installed |

So: anything that needs a live backend — real search timings, real matching, real job
execution — cannot be reproduced end to end here. That rules out measuring the
performance issues (#76, #77) and anything whose symptom only appears against a
populated Mongo collection. It does **not** rule out most of the backlog: MCRITweb
renders what the backend hands it, and the project ships a faithful offline stand-in.

## Install

The system pip cannot build `picblocks` (a transitive dep of `mcrit`) because Debian's
patched setuptools blows up with `AttributeError: install_layout` during the wheel
build. A venv with current setuptools builds it fine:

```bash
cd /home/user/mcritweb
python3 -m venv .venv
.venv/bin/pip install --upgrade pip setuptools wheel
.venv/bin/pip install -r requirements.txt
.venv/bin/pip install -e . --no-deps
.venv/bin/pip install pytest pytest-cov "ruff==0.16.0"   # ruff pinned as CI pins it
```

Resolved versions: Flask 3.1.3, Werkzeug 3.1.8, mcrit 1.8.1, smda 4.5.0, numpy 2.4.6.
Note `mcrit` resolves to **1.8.1** while `requirements.txt` floors it at `>=1.5.3`.

`.venv/` is covered by `.gitignore`? — no, it is not; it is left untracked and must
never be added. Same for `instance/`.

## What CI runs

```bash
.venv/bin/python -m pytest        # 239 passed
.venv/bin/python -m ruff check .  # All checks passed!
```

## Running the app standalone (no backend)

```bash
FLASK_APP=mcritweb FLASK_DEBUG=1 .venv/bin/flask init-db
FLASK_APP=mcritweb FLASK_DEBUG=1 .venv/bin/flask run
# http://127.0.0.1:5000/ -> 302 /register  (first visit, empty user table)
```

`FLASK_DEBUG=1` matters: `create_app` sets `SESSION_COOKIE_SECURE=not app.debug`, so
without it login over plain HTTP silently fails.

Only `/register`, `/login` and `/help` are useful this way — every other page goes
through `mcrit_server_required`, which probes the backend and redirects to the index.

## Running the app against the captured corpus — `work/harness/devserver.py`

This is the reproduction environment used for nearly everything in `work/STATE.md`.

The project already ships an offline backend for its tests: `CorpusMcritClient` in
`tests/fixtureData.py`, which serves the real captured reports in `tests/fixtures/`
(three malware families over seven samples plus six MSVC library samples, and one
finished job of each of the five report types). `create_app` exposes the seam it plugs
into — the `MCRIT_CLIENT_FACTORY` config key — and `MCRIT_SERVER_PROBE` stubs out the
reachability check. The harness wires those two together behind a normal HTTP server,
so pages can be walked with `curl` rather than only through `app.test_client()`.

```bash
.venv/bin/python work/harness/devserver.py --port 5001 --role admin &
# prints: instance=/tmp/mcritweb-harness-XXXX role=admin user_id=1 cookies=work/harness/cookies.txt
curl -s --noproxy '*' -b work/harness/cookies.txt http://127.0.0.1:5001/explore/samples
```

- `--role` seeds a single user at that role and writes a signed session cookie jar, so
  role-dependent behaviour can be exercised by restarting with `--role visitor` etc.
- `--noproxy '*'` is required: this environment has `HTTPS_PROXY`/`HTTP_PROXY` set and
  curl would otherwise send loopback requests through it.
- Each run gets a fresh temp instance dir (so `instance/cache/` is empty — the app
  never invalidates that cache, so a stale one will show you old output). Pass
  `--instance DIR` to keep one across runs.

Useful ids from the corpus (`.venv/bin/python -c` against `tests/fixtureData.py`):

```bash
cd tests && ../.venv/bin/python -c "import fixtureData as f; print({r: f.job_id_of(r) for r in f.REPORTS})"
```

### Limits of the harness

`CorpusMcritClient` models the *contract* the views depend on, not mcrit's
implementation: its search is a case-insensitive substring test over a handful of
fields, and its cursor is a fixture-local token, not mcrit's `MinimalSearchCursor`.
It raises `NotImplementedError` naming itself for any client method nobody taught it —
which is a feature (gaps are actionable) but means a page reaching a new backend method
fails loudly rather than rendering. Anything about mcrit's `field:value` query parser,
its sort/index behaviour or its timings needs a real backend and is marked "can't" in
`work/STATE.md`.
