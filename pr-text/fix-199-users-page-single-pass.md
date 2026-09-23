Title: Group the users page by role once instead of filtering the list per tab

## Summary
Fixes #199.

`templates/users.html` looped over `g.all_users` once per tab: pending, contributor, admin, visitor and all. That is five passes over the same list in one response, and four of them filtered on `user.role` inside the loop. Only the "all" tab needs every row.

## What changed
- `group_users_by_role()` in `views/administration.py` is called once from the `users()` view. It splits `g.all_users` into one list per role in `KNOWN_ROLES` (`g.users_by_role`) and keeps each role's existing order.
- Each of the four role tabs iterates its own list, and the `{% if user.role == ... %}` inside those loops is gone. The "all" tab still iterates `g.all_users`.
- A user with a role outside `KNOWN_ROLES` (which nothing should write since #95) is still listed under "all" only.
- New `tests/testUsersPage.py`: one page test, run on `/admin/users/` and on a tab URL. It creates one user per role plus one with an unknown role, and asserts the exact rows in every pane.

## Why
The issue asked whether the five loops are five views of the same rows. Four of them are, so the filtering belongs in the view, done once, rather than repeated per tab in the template.

## Validation
- The new test passes on master and here, as it should for a change that keeps the output.
- Full suite and `ruff check .` pass.
- Every tab URL, with 11 users covering the four roles plus unknown ones (`blocked`, `''`, `Admin`): the rows in each pane are identical to master:
  - `/`, `/all`, `/pending`, `/visitors`, `/contributors`, `/admins`;
  - `/admin`, where the admins pane's delete button sends you;
  - an unknown tab.

  The HTML differs only in whitespace. Master wrote a whitespace-only line for each user a role tab skipped, so the page is 2-4% smaller here: 42,670 bytes on master and 41,878 on this branch, with 11 users.
- Merges cleanly with every open PR.

## Limitations
This is a cleanup rather than a speedup. The loop work it removes is about 0.5 µs per user per request: 0.05 ms at 100 users, 0.5 ms at 1,000. Whole-request medians are indistinguishable at both sizes. Two per-user costs on this page are much larger, and neither is changed here:
- rendering about two table rows per user, roughly 90 µs per user;
- `get_all_user_info` in `mcritweb/db.py`, which runs `SELECT *` and then one `UserInfo.fromDb` query per user, about 32 µs per user.
