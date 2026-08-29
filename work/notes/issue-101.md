# Issue #101 — what is left after the enumeration fix

The PR on the fork closes the account-enumeration half. The rate limiting the issue is
titled for is **not** done, deliberately. This is what a fix would have to settle, so
whoever picks it up does not start from the issue body alone.

## What shipped

`mcritweb/views/authentication.py`:

- one message (`Incorrect username or password.`) for both failure branches
- an absent username now costs a real `check_password_hash` against a hash of a random
  secret, because skipping it was measurable: **~101 ms** for an existing account vs
  **~1.8 ms** for an absent one, on this machine, median of 15 attempts. The timing said
  what the message no longer does.

## What did not, and why

The issue leaves the central question open in its own words:

> Determine if lockout applies per-account (enabling deliberate user denial-of-service)
> or per-IP only

That is not a detail — it is the design. Both answers are defensible and they have
different failure modes:

- **Per-account lockout** hands anyone who knows a username a denial-of-service against
  that account. On an instance whose usernames are now *harder* to enumerate but not
  secret, that is a real trade, not a theoretical one.
- **Per-IP** is trivially evaded by a distributed attacker and punishes everyone behind
  one NAT — which, for an internal malware-analysis instance behind a corporate
  gateway, may be the whole team.

Two more things a real fix has to answer, neither mentioned in the issue:

1. **Where the counter lives.** The issue proposes SQLite. MCRITweb is deployed behind
   NGINX with a WSGI server running several workers (`docker-mcrit`), and they share the
   SQLite file — so that part works — but every failed attempt then becomes a write to
   the same database that serves every page, on an unauthenticated route. That is a new
   write amplification on the one endpoint an attacker controls the rate of. It needs a
   cap and a pruning story, or a different store.
2. **What the client IP actually is.** Behind NGINX, `request.remote_addr` is the
   proxy. Reading `X-Forwarded-For` without a configured trusted-proxy count means the
   attacker picks their own bucket key and the limit does nothing. Werkzeug ships
   `ProxyFix` for this, but how many proxies to trust is deployment configuration that
   MCRITweb does not currently have.

## Cheap things adjacent to it, not done

- `authentication.register` still answers `"User {username} is already registered."`,
  which is the same oracle by another door. Unlike login it is arguably load-bearing —
  a person choosing a username needs to know it is taken — and `@multi_user` plus an
  optional registration token already gate the route. Worth a decision, not a drive-by.
- Failed attempts are not logged at all, so an operator cannot see an attack in
  progress. The issue asks for this (`current_app.logger`) and it is genuinely cheap and
  carries no design question. It was left out only to keep the shipped PR to one claim.

## Suggested shape, if someone wants a starting point

Per-IP **and** per-username counters, both in memory with a bounded dict and a
time-window sweep, backed by SQLite only if it has to survive a restart; a delay rather
than a lockout at the first threshold, so there is no denial-of-service to hand out; and
`ProxyFix` wired from a new config key defaulting to "no proxies trusted". That is a
day's work with a real test suite behind it, and it is a maintainer's call, not a
drive-by change while they are asleep.
