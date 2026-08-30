"""What to say when a call to the MCRIT backend does not complete.

Issue #43 asks how to handle "all kinds of errors coming from McritClient", and
offers two options: have mcrit raise semantically meaningful exceptions, or test
every result for None and guess. This module covers the case neither option
reaches - the request never completes at all, so there is no result to test and no
guessing required. `requests` raises for that, and until now nothing caught it, so
it escaped the view as an unhandled exception and the page became an HTTP 500.

There is exactly one thing a `requests` exception can mean here: talking to the
backend failed. `views/utility.default_server_probe` is the only other outbound HTTP
call this application makes, and `mcrit_server_required` already wraps it in its own
try/except - so anything reaching these handlers came out of `McritClient`.

Deliberately narrow. It catches `requests.RequestException` and nothing wider: a
handler broad enough to swallow a TypeError in a template would turn every bug in
this application into a false report about someone else's server, and would hide it
from the logs that would otherwise show it.

One boundary worth naming: `requests.HTTPError` is also a RequestException, and it
would be reported here as a connection failure, which it is not - it means the
backend answered with an error status. That is unreachable today, because
`raise_for_status` appears nowhere in mcrit; every status it sees goes through
`handle_response` instead. If that ever changes, this is the place that needs a
branch for it.
"""

import requests
from flask import current_app, render_template


def is_timeout(error):
    """A backend that answered too slowly, as opposed to one that did not answer.

    Timeout covers ConnectTimeout and ReadTimeout both; the first means the backend
    never accepted the connection, the second that it accepted and then stopped
    talking. Neither is "the server is down", and saying so would send an operator
    looking in the wrong place.
    """
    return isinstance(error, requests.exceptions.Timeout)


def message_for(error):
    """What to tell a person about a backend call that did not complete."""
    if is_timeout(error):
        return 'The MCRIT server did not respond in time'
    return 'No connection to the MCRIT server'


def status_for(error):
    """What to tell a program. mcritweb is a gateway to mcrit here, so it answers as
    one: 504 for a backend that ran out of time, 502 for one that could not be
    reached or answered unusably."""
    return 504 if is_timeout(error) else 502


def register(app):
    """Answer a failed backend call with a page rather than a stack trace.

    The API's own handler is registered on its blueprint at import time, in
    views/api.py - a blueprint takes handlers only before it is registered, and this
    factory runs once per app.
    """

    @app.errorhandler(requests.RequestException)
    def backend_unavailable(error):
        # Rendered rather than redirected, deliberately. `mcrit_server_required`
        # flashes and redirects to the index, which works because it runs *before* a
        # view and only when its own probe already failed. Doing that here would
        # loop: index() calls getFamily, getSampleById, getQueueData and
        # search_samples itself, so a backend that fails one of those fails the
        # redirect target too, forever. Rendering also keeps the URL the user was on
        # and lets the response carry a status that means what happened.
        current_app.logger.warning("MCRIT backend call failed: %r", error)
        return render_template("backend_unavailable.html", reason=message_for(error)), 503
