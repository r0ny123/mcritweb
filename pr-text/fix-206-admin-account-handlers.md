Title: Short-circuit the username and password handlers, and accept only POST

## Summary
Fixes #206.

The username and password forms on the settings page ran every check whatever an earlier one had found, re-read the caller's row, and accepted GET. They now stop at the first failing check, use `g.user`, and accept only POST.

## What changed
- `change_username` checks the format, then the password, then whether the name is taken, as an `if/elif` chain. The password check is deliberately placed ahead of the cheaper "taken" lookup, so that a caller who doesn't know the password can't learn whether a name exists.
- `change_password` checks that the two new passwords match before it checks the old one.
- `change_username`, `change_password` and `regenerate_apitoken` use `g.user` instead of reading the row again with `UserInfo.fromDb(user_id=...)`. `load_logged_in_user` has already run that same query for this request, and `login_required` guarantees the row exists. That also retires the handlers' own session-id validation.
- `change_username` and `change_password` are `methods=('POST',)`. Their only callers are the two POST forms in `settings.html`, and both carry CSRF tokens. `regenerate_apitoken` was POST-only already.
- `tests/routePolicy.py`: the rows are unchanged; the stale "GET raises 400" comments are gone.
- `tests/testSettingsPages.py`:
  - GET → 405 for both routes;
  - the check order;
  - the successful paths;
  - a guard that a session whose user row was deleted can't write through any of the three handlers.

## Why
- `check_password_hash` is deliberately slow: one scrypt check costs about 100–200 ms. A malformed username or a mismatched confirmation paid for it anyway.
- With independent `if`s, the last failing check won. So a caller with the wrong password was still told "Username is already taken!", which confirmed that a name exists without proving who they were.
- A GET indexed `request.form` and ended in a 400, shown as a 500 with a traceback under `FLASK_DEBUG`. AGENTS.md asks that writing routes be POST-only. The issue suggests a redirect instead; 405 is what the other POST-only routes answer, and what the existing POST_ONLY tests expect.

## User-visible changes
Two flash messages change, both when more than one check fails:
- A taken name submitted with a wrong password now says "Incorrect Password!" instead of "Username is already taken!". This is the point of the change.
- A malformed name submitted with a wrong password now says "Username has invalid format." instead of "Incorrect Password!".

`change_password`'s messages are unchanged in all four combinations. There is still one flash per request, and the redirect targets are the same.

## Validation
- Five of the new tests fail on master and pass here:
  - GET → 405 on both routes;
  - a malformed name never reaches `check_password_hash` or the name lookup;
  - a wrong password never reaches the "taken" lookup;
  - mismatched new passwords never hash.

  The successful-path and deleted-user tests pass on both, as regression guards.
- Full suite: 997 passed with Playwright's Chromium present. Without Chromium, 23 browser tests skip. `ruff check .` is clean. `git merge-tree` shows the branch merges cleanly with every open PR.
- Live against mcrit 1.9.0, for a contributor and for the admin renaming themself:
  - renaming, then renaming back;
  - changing the password and logging in with each password;
  - rotating the API token;
  - every error path.

  All other columns of the user row were unchanged, including the UTC timestamps, the role and the token. GET, and HEAD, now answer 405.
- Median round trip over 15 interleaved requests on a loaded 4-core host:

  | Request | master | this branch |
  |---|---|---|
  | malformed username | about 140 ms | 5 ms |
  | mismatched new passwords | about 130 ms | 5 ms |
  | wrong password | one hash | one hash, unchanged |

## Limitations
- The password check on these forms is still unthrottled, as it was before. It needs its own change.
- Choosing the name you already have still says "already taken", as before.
- The settings view in `authentication.py` re-reads the row too. That one is #190's, which lists the same three re-reads here plus the settings view.
- Pre-existing, and not changed here:
  - The templates hide these forms from visitors and pending accounts, but the routes are `login_required` only.
  - `change_username` accepts names that `/register` reserves.
  - A save through `g.user` writes back the whole row. That is the same lost-update window master has.
