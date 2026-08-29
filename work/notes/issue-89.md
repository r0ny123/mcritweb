# Issue #89 — `mcrit_server_required` probes the backend on every request

**Not fixed, deliberately.** The issue asks a design question and says whose it is.

## Confirmed by code read

`mcritweb/views/utility.py`:

```python
def mcrit_server_required(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        probe = current_app.config.get("MCRIT_SERVER_PROBE", default_server_probe)
        try:
            if not probe():
                flash('Connected to MCRIT server but could not authenticate - ...', category='error')
                return redirect(url_for('index'))
        except Exception:
            flash('No connection to the MCRIT server', category='error')
            return redirect(url_for('index'))
        return view(**kwargs)
    return wrapped_view
```

36 routes carry the decorator — `analyze.py` 10, `data.py` 12, `explore.py` 13,
`api.py` 1 (`grep -c "@mcrit_server_required" mcritweb/views/*.py`). Each one makes a
blocking `requests.get` to the backend root before doing its own work, and the result
is not cached anywhere.

The two prior fixes the issue names are both in place: the probe has a
`(3.05, 10)` connect/read timeout, and authorization decorators run before it.

## Why nothing shipped

The issue closes with:

> the decision belongs to whoever owns the error-handling story, not to a drive-by
> change

and it is right to. Both options it lists are behaviour changes with real costs:

- **A TTL cache** means a backend that just went down keeps looking up for the length
  of the TTL, and a backend that just came back keeps looking down. In the reference
  deployment the cache is per worker, so two browser tabs can disagree. The user
  picking a TTL is picking how long the app is allowed to lie.
- **Removing the probe** and handling failures at the call sites is the better answer
  and is a much larger change — it is paired with #43 in the issue for exactly that
  reason, and #43 is itself unresolved ("make McritClient throw meaningful exceptions"
  vs "test for `result is None` everywhere" is an open fork in the road).

Neither is something to choose on a maintainer's behalf overnight.

## What is cheap and safe, if it helps

`MCRIT_SERVER_PROBE` is already a config key (added for the test suite), so an operator
or an experiment can substitute a caching probe **without touching the decorator at
all**:

```python
# instance/config.py
import time, requests
_cached = {"at": 0.0, "up": False}
def MCRIT_SERVER_PROBE():
    now = time.monotonic()
    if now - _cached["at"] > 10:
        _cached["up"] = requests.get(..., timeout=(3.05, 10)).status_code == 200
        _cached["at"] = now
    return _cached["up"]
```

That is the whole of option 1, available today, reversible, and per-deployment — which
seems a better place for a staleness trade-off than a hardcoded default.

Measuring the actual cost needs a real backend, which this environment does not have
(`work/SETUP.md`), so the "hundreds of ms" figure in the issue is not something I can
confirm or refute.
