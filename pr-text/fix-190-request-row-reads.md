Title: Stop re-reading rows a request has already loaded

## Summary

Fixes #190.

Request hooks and views kept reading SQLite rows that an earlier step of the same request had already loaded. The worst one read the whole user table on every request. This PR removes those repeat reads and leaves the request/response behaviour unchanged.

## What changed

- **`db.is_first_user()`** now runs `SELECT 1 FROM user LIMIT 1`. Before, it ran `SELECT * FROM user` and `fetchall()`. The index route reads `g.first_user`, which the hook has already set, and no longer asks a second time.
- **`db.get_server_info()`** (new) reads the `server` row once per request and memoises it on `g`. The operation-mode hook, `register()`, `admin.server`, `admin.change_server` and `get_server_url()`/`get_server_token()` all use it.
  - `ServerInfo.saveToDb()` drops the memo before it writes. A request that changes the settings then reads its own write: that covers `change_server` and first-user registration, which saves a `ServerInfo` it built itself.
  - At the start of each request, `set_operation_mode` drops both the memo and `g.mcrit_client`, the client built from those settings. In production every request already gets a fresh `g`. This only matters when a request runs inside an app context that is already pushed, as tests do: Flask then shares that context's `g` with the request.
- **`settings`** uses `g.user`, which `load_logged_in_user` has already loaded and `login_required` has already checked. That makes the old `user_info is not None` guard on `can_use_api` dead, so it is removed.
- **The admin server pages** show `current_app.config['MCRITWEB_VERSION']` and no longer re-open and regex-scan `setup.py`. `create_app` fills that key by calling the same `get_mcritweb_version_from_setup()`, and `instance/config.py` can't override it because it is set after `from_pyfile`. The value only differs if `setup.py` is edited while the app is running, and then the config value is the correct one because it matches the running code. `register()` already used the config key. `get_mcritweb_version_from_setup()` stays, because `create_app` still uses it.
- **`params.parseBaseAddrAndBitnessFromFilename()`** replaces the two helpers that ran the same `_0x…` search one after the other. `request_filename_info` was their only caller. As a side effect, "no base address recognized" is logged once per filename instead of twice.
- **`get_stored_password_hash_method()` is deliberately not cached.** I added a docstring paragraph that says why. It picks the method for the dummy hash that keeps an absent username as slow as a wrong password (#101), so a stale answer would reopen that timing gap without any error. To stay correct, a cache would have to be invalidated by every write to the password column: registration, rehash on login, password change and user deletion. It would also have to see writes this process never observes, such as a second worker, `flask init-db` or a restored database file. A per-request memo gains nothing, because the function runs at most once per request. There is a cost, and it falls on exactly the path the dummy hash disguises. The query runs only when the username is absent, so on a large user table it adds a small, repeatable delay that a wrong password doesn't have: about 2 ms at 5,000 users. That is still far below the 66–150 ms hash check it precedes, and the login throttle limits how often anyone can ask.

## Why

On master, an ordinary explore page read the `server` row five times: once in the hook, twice in the reachability probe and twice in the client factory. Every request, including `/login`, scanned the whole user table and pulled every password hash into Python. That scan grows with the user table.

## Validation

**Tests**
- New file `tests/testRequestReads.py`. It traces SQL through sqlite3's trace callback on the connection `get_db` opens. It asserts:
  - no page reads the whole user table, and the first-user check sends no such statement;
  - the index checks for users once;
  - `/`, `/explore/samples` and `/admin/server` read the server row once, with a probe and client factory that read the settings the way the real ones do;
  - a `ServerInfo.saveToDb()` in the request is what the rest of that request reads;
  - `change_server` builds its client from the new settings;
  - a write between two requests that share an app context reaches both the probe and the client of the second request;
  - first-user registration still saves the server row and the user can log in;
  - `/settings` loads the user row once;
  - the admin server pages show the configured version;
  - the absent-user hash method follows a table change made outside the process.
- `tests/testUpload.py` gains tests for a 32-bit dump filename, a dump filename with no address, and a check that a filename with no address logs "No base address recognized" once rather than twice.
- On master, 14 of the new tests fail. The rest pin invariants that master already meets and that a memo could break. I removed each of the three resets in turn (the memo drop in `saveToDb`, and the memo drop and the client drop in the hook), and each time the matching test failed.
- The full suite passes: 983 passed, 23 skipped. `ruff check .` is clean.

**Live**, against mcrit 1.9.0. Each column is a fresh instance on the same port. SQL statements were counted per request with a trace callback.

| request | master SELECTs (server-row / full user scans) | this branch |
|---|---|---|
| `GET /` on an empty instance | 2 (0 / 2) | 1 (0 / 0) |
| `GET /login` (anon) | 2 (1 / 1) | 2 (1 / 0) |
| `GET /` (admin) | 6 (3 / 2) | 3 (1 / 0) |
| `GET /explore/samples` | 9 (5 / 1) | 5 (1 / 0) |
| `GET /settings` | 7 (1 / 1) | 6 (1 / 0) |
| `GET /admin/server` | 6 (4 / 1) | 3 (1 / 0) |
| `POST /admin/change_server` | 7 (5 / 1) | 5 (3 / 0)* |

\* On this branch those three are the hook's read, the row check inside `saveToDb`, and the re-read after it.

- Median `/login` time rose from 8.0 ms to 25.0 ms on master once 5,000 extra users were in the table. On this branch it went from 3.5 ms to 4.5 ms.
- Other things I checked:
  - First-user registration on a fresh instance works, and the first user can log in afterwards.
  - Changing the server URL to `http://localhost:8000` rendered the new URL and a backend version of 1.9.0 in the same response. `/explore/samples` still listed the samples afterwards. I then changed the URL back.
  - A wrong username and a wrong password both produced the same message.
  - The flask log showed no 500s.

## Limitations

- `saveToDb` doesn't drop `g.mcrit_client`. A view that built a client and then saved new settings would keep the old client for the rest of that request. `change_server` doesn't do that, because it builds its client after the save. Having `db.py` reach into the client seam from #88 seemed the wrong direction.
- `administration.py`'s `change_username`, `change_password` and `regenerate_apitoken` still load the user by id again, which the issue also lists. They are left out on purpose, because #206's fix is in progress there.

**Checked again on a second instance** (mcrit 1.9.0, 66 samples). SQL statements per request, traced in process:

| Request | master | this branch |
|---|---|---|
| `GET /` | 6 | 3 |
| `GET /explore/samples` | 8 | 4 |
| `GET /admin/server` | 6 | 3 |
| `GET /settings` | 6 | 5 |
| `GET /admin/users/` | 6 | 6 |

- The only full user-table scan left is the one `/admin/users/` renders.
- Every page rendered identically to master, for an admin and for a newly registered visitor.
- A changed default filter, column setting and username each took effect on the next request.
- The merged filename parser returned what master's two did for all 7 filenames tried, and logged a filename with no address once.

## Merge conflicts
- **#114, #130, #160**: import lines in `administration.py`, `utility.py` and `authentication.py`. Keep both sides.
- **#176**: its import line, and the two lines that read the running version. #176 makes `pyproject.toml` the version source through `get_mcritweb_version()`. Keep that source and have this PR's pages read whatever #176 establishes.
- **#133, #141** (`data.py`, `params.py`): this PR merges `parseBaseAddrFromFilename` and `parseBitnessFromFilename` into one helper. #133's import list and #141's new `parse_base_addr_form_param` sit next to them. Keep both, importing the merged helper.
- Every other open PR merges cleanly.
