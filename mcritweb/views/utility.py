"""Server, session and local-path plumbing shared across the view modules.

Request-parameter parsing lives in params.py; the function-diff block comparison
lives in functiondiff.py. See issue #88.
"""

import collections
import functools
import os
import re
import shutil
import threading
import time

import requests
from flask import Response, current_app, flash, g, redirect, session, url_for

from mcritweb import backend_errors, db
from mcritweb.db import ServerInfo, UserColumnSettings


def get_server_url():
    server_info = ServerInfo.fromDb()
    return server_info.url


def get_server_token():
    server_info = ServerInfo.fromDb()
    return server_info.server_token


# (connect, read) seconds for the reachability probe. Without a timeout, requests
# waits indefinitely, so an unresponsive backend hangs the page until the WSGI or
# NGINX timeout fires - 300s in the docker-mcrit deployment.
SERVER_PROBE_TIMEOUT = (3.05, 10)


def default_server_probe():
    """True if the configured MCRIT server answers and accepts our token.

    NOTE: this is a blocking HTTP round-trip, performed on every request to a route
    decorated with mcrit_server_required.
    """
    result = requests.get(
        f"{get_server_url()}/",
        headers={"username":"mcritweb", "apitoken": get_server_token()},
        timeout=SERVER_PROBE_TIMEOUT,
    )
    return result.status_code != 401


#: The last probe answer. Module-level, so it is per worker process - two workers can
#: briefly disagree, which is the cost of not making this round-trip on every request
#: to all 36 decorated routes. See issue #89.
#:
#: Two timestamps, because they answer different questions. `answered_at` is when the
#: probe came back, and it is what the TTL is measured from: taking it before the call
#: would make every entry `probe_duration` seconds old at birth, so a slow backend -
#: precisely the case where a per-request round-trip hurts - would get little or no
#: caching. `started_at` is when the probe went out, and it is what decides which of two
#: concurrent answers to keep: the probe that *started* later observed the more recent
#: state, even if it finished first.
_ProbeAnswer = collections.namedtuple("_ProbeAnswer", "server_url started_at answered_at was_up")
_probe_cache = None
_probe_cache_lock = threading.Lock()

#: Bumped by forget_server_probe. A probe that was already in flight when the settings
#: changed carries the old generation and its answer is discarded rather than written
#: over the invalidation - without this, an admin who has just corrected a bad token
#: keeps seeing the failure for up to the full TTL, which is the one thing
#: forget_server_probe exists to prevent. The probe runs on 36 routes, so on a busy
#: instance one is nearly always in flight when the settings are saved.
_probe_generation = 0


def forget_server_probe():
    """Drop the cached answer. Called when the server settings change, so an operator
    who has just fixed the URL or token does not wait out the TTL to see it work."""
    global _probe_cache, _probe_generation
    with _probe_cache_lock:
        _probe_cache = None
        _probe_generation += 1


def probe_server(probe, ttl, server_url):
    """`probe()`, but at most once per `ttl` seconds per backend URL.

    A raise is not cached: a connection error is the answer most likely to change on
    its own, and the caller turns it into a different message than "up" or "down".
    Keyed by URL so pointing the instance at another backend re-probes immediately;
    every other settings change - a token correction, say - calls forget_server_probe().

    The lock is not held across the probe. Serialising every request on all 36 decorated
    routes behind one HTTP call with a 13-second timeout would be worse than the problem
    this cache is solving. Two threads arriving on a cold cache both probe; the write is
    reconciled under the lock afterwards, against both the generation and the incumbent's
    start time, so neither a concurrent invalidation nor an older answer is lost.
    """
    global _probe_cache
    if ttl <= 0:
        return probe()
    with _probe_cache_lock:
        cached = _probe_cache
        generation = _probe_generation
    if cached is not None and cached.server_url == server_url and time.monotonic() - cached.answered_at < ttl:
        return cached.was_up

    started_at = time.monotonic()
    answer = probe()
    fresh = _ProbeAnswer(server_url, started_at, time.monotonic(), answer)
    with _probe_cache_lock:
        if generation == _probe_generation and (_probe_cache is None or _probe_cache.started_at <= fresh.started_at):
            _probe_cache = fresh
    return answer


def mcrit_server_required(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        # resolved from config so tests can substitute it, in the same way the
        # backend client itself is substituted via MCRIT_CLIENT_FACTORY (issue #88)
        probe = current_app.config.get("MCRIT_SERVER_PROBE", default_server_probe)
        ttl = current_app.config.get("MCRIT_SERVER_PROBE_TTL", 0)
        try:
            if not probe_server(probe, ttl, get_server_url() if ttl > 0 else None):
                # reached the backend and it refused our token: from an API caller's
                # side that is still an upstream failure, so it gets a status rather
                # than a redirect to a page it cannot read. See issue #43.
                if backend_errors.wants_a_status_code():
                    return Response(status=502)
                flash('Connected to MCRIT server but could not authenticate - Did you configure a token in the server settings?', category='error')
                return redirect(url_for('index'))
        except Exception as error:
            if backend_errors.wants_a_status_code():
                return Response(status=backend_errors.status_for(error))
            flash('No connection to the MCRIT server', category='error')
            return redirect(url_for('index'))
        return view(**kwargs)
    return wrapped_view


def get_session_user_id():
    try:
        user_id = int(session['user_id'])
        if user_id > 0:
            return user_id
    except Exception:
        return None


def get_username(request=None):
    username = "guest"
    if g.user is not None:
        username =  g.user.username
    elif request and "apitoken" in request.headers:
        provided_token = request.headers.get("apitoken", "")
        username_by_token = db.get_username_by_apitoken(provided_token)
        if username_by_token is not None:
            username = username_by_token
    elif request and "username" in request.headers:
        username = request.headers.get("username")
    return username


def get_user_column_setup(table_type:str):
    if table_type not in UserColumnSettings._default_settings.keys():
        raise Exception(f"Unknown table type for user column settings: {table_type}")
    # load user column setup from database
    user_id = get_session_user_id()
    user_column_settings = UserColumnSettings.fromDb(user_id)
    # if we don't have them yet, create them
    if user_column_settings is None:
        user_column_settings = UserColumnSettings(user_id)
        user_column_settings.saveToDb()
    ucs_dict = user_column_settings.toUserColumnSettings()
    return ucs_dict[table_type]["active"]

def ensure_local_data_paths(app, clear_data=False):
    # nuke both cache and temp folders
    nuke_paths = [
        app.instance_path + os.sep + "cache",
        app.instance_path + os.sep + "temp"
    ]
    # ensure the instance and cache folders exists
    ensure_paths = [
        app.instance_path + os.sep + "cache" + os.sep + "diagrams",
        app.instance_path + os.sep + "cache" + os.sep + "results",
        # write_atomically parks a cache file here until it is complete - deliberately
        # beside the two cache directories rather than inside either, because
        # data.diagram_file serves every name under cache/diagrams
        app.instance_path + os.sep + "cache" + os.sep + "incomplete",
        app.instance_path + os.sep + "temp" + os.sep + "reports",
        app.instance_path + os.sep + "temp" + os.sep + "diagrams",
        app.instance_path + os.sep + "temp" + os.sep + "uploads",
    ]
    if clear_data:
        for path in nuke_paths:
            shutil.rmtree(path)
    for path in ensure_paths:
        try:
            os.makedirs(path)
        except FileExistsError:
            pass


def get_mcritweb_version_from_setup():
    this_file_path = str(os.path.abspath(__file__))
    project_root = str(os.path.abspath(os.sep.join([this_file_path, "..", "..", ".."])))
    setup_path = os.path.abspath(os.sep.join([project_root, "setup.py"]))
    mcritweb_version = None
    with open(setup_path) as fin:
        for line in fin.readlines():
            line = line.strip()
            match = re.search(r'version="(?P<version_str>\d+\.\d+\.\d+)",', line)
            if match:
                mcritweb_version = match.group("version_str")
    return mcritweb_version
