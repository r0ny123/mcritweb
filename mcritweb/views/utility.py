"""Server, session and local-path plumbing shared across the view modules.

Request-parameter parsing lives in params.py; the function-diff block comparison
lives in functiondiff.py. See issue #88.
"""

import functools
import os
import re
import shutil
import threading
import time

import requests
from flask import current_app, flash, g, redirect, session, url_for

from mcritweb import db
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


#: The last probe answer, as (server_url, answered_at, was_up). Module-level, so it is
#: per worker process - two workers can briefly disagree, which is the cost of not
#: making this round-trip on every request to all 36 decorated routes. See issue #89.
_probe_cache = None
_probe_cache_lock = threading.Lock()


def forget_server_probe():
    """Drop the cached answer. Called when the server settings change, so an operator
    who has just fixed the URL or token does not wait out the TTL to see it work."""
    global _probe_cache
    with _probe_cache_lock:
        _probe_cache = None


def probe_server(probe, ttl, server_url):
    """`probe()`, but at most once per `ttl` seconds per backend URL.

    A raise is not cached: a connection error is the answer most likely to change on
    its own, and the caller turns it into a different message than "up" or "down".
    Keyed by URL so pointing the instance at another backend re-probes immediately;
    every other settings change calls forget_server_probe().

    The lock covers the write, not the read-then-probe: two threads arriving on a cold
    cache both probe, and the later answer wins. That costs one extra round-trip and
    cannot produce a wrong answer, which is a better trade than holding a lock across
    an HTTP call with a 13-second timeout.
    """
    global _probe_cache
    if ttl <= 0:
        return probe()
    now = time.monotonic()
    cached = _probe_cache
    if cached is not None and cached[0] == server_url and now - cached[1] < ttl:
        return cached[2]
    answer = probe()
    with _probe_cache_lock:
        _probe_cache = (server_url, now, answer)
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
                flash('Connected to MCRIT server but could not authenticate - Did you configure a token in the server settings?', category='error')
                return redirect(url_for('index'))
        except Exception:
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
