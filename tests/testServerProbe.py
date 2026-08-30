#!/usr/bin/python
"""The backend reachability probe, and how often it actually runs.

`mcrit_server_required` is on 36 routes and made a blocking HTTP round-trip to the
backend on every request to each of them, with the answer thrown away afterwards.
Issue #89. It is now reused for MCRIT_SERVER_PROBE_TTL seconds.

The trade the TTL buys is staleness, in both directions, per worker process - so
these tests pin the edges of it rather than only the happy path.
"""

import logging
import threading
import time
import unittest

import pytest

from mcritweb.views import utility

LOG = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)-15s %(message)s")
logging.disable(logging.CRITICAL)


class CountingProbe:
    def __init__(self, answer=True):
        self.calls = 0
        self.answer = answer

    def __call__(self):
        self.calls += 1
        if isinstance(self.answer, Exception):
            raise self.answer
        return self.answer


@pytest.fixture(autouse=True)
def _clean_cache():
    utility.forget_server_probe()
    yield
    utility.forget_server_probe()


def test_a_zero_ttl_probes_every_time():
    """The behaviour of every version before this one, still available as a config."""
    probe = CountingProbe()

    for _ in range(3):
        assert utility.probe_server(probe, 0, "http://backend") is True

    assert probe.calls == 3


def test_the_answer_is_reused_within_the_ttl():
    probe = CountingProbe()

    for _ in range(5):
        assert utility.probe_server(probe, 60, "http://backend") is True

    assert probe.calls == 1


def test_a_down_backend_is_cached_too():
    """Not caching "down" would leave the pathological case - an unreachable backend -
    paying full price on every request, which is the case that hurts most."""
    probe = CountingProbe(answer=False)

    for _ in range(3):
        assert utility.probe_server(probe, 60, "http://backend") is False

    assert probe.calls == 1


def test_a_different_backend_url_is_probed_again():
    probe = CountingProbe()

    utility.probe_server(probe, 60, "http://one")
    utility.probe_server(probe, 60, "http://two")

    assert probe.calls == 2


def test_a_raise_is_not_cached():
    """A connection error is the answer most likely to change on its own, and the
    caller turns it into a different message than up-or-down. Caching it would make a
    backend that has just come back look down for the rest of the TTL."""
    probe = CountingProbe(answer=ConnectionError("down"))

    for _ in range(3):
        with pytest.raises(ConnectionError):
            utility.probe_server(probe, 60, "http://backend")

    assert probe.calls == 3


def test_forgetting_makes_the_next_call_probe():
    """What an operator gets after correcting the server URL or token."""
    probe = CountingProbe()
    utility.probe_server(probe, 60, "http://backend")

    utility.forget_server_probe()
    utility.probe_server(probe, 60, "http://backend")

    assert probe.calls == 2


def test_the_ttl_expires():
    probe = CountingProbe()
    utility.probe_server(probe, 60, "http://backend")

    # a TTL of 0 would take the no-cache path, so age the entry instead
    with utility._probe_cache_lock:
        cached = utility._probe_cache
        utility._probe_cache = cached._replace(answered_at=cached.answered_at - 61)
    utility.probe_server(probe, 60, "http://backend")

    assert probe.calls == 2


# --- through the decorator ---------------------------------------------------

def test_a_page_load_does_not_probe_once_per_request(app, client, as_role):
    probe = CountingProbe()
    app.config["MCRIT_SERVER_PROBE"] = probe
    as_role("visitor")

    for _ in range(4):
        client.get("/explore/families")

    assert probe.calls == 1, "four requests, one round-trip"


def test_the_check_still_refuses_when_the_backend_is_down(app, client, as_role):
    """The cache must not turn the gate off. This is the guarantee testFixtures.py
    asserts for the un-cached path, restated for the cached one."""
    app.config["MCRIT_SERVER_PROBE"] = CountingProbe(answer=False)
    as_role("visitor")

    response = client.get("/explore/families")

    assert response.status_code == 302
    assert response.headers["Location"] in ("/", "http://localhost/")


def test_creating_an_app_forgets_any_earlier_answer(tmp_path):
    """The cache is a module global, so it outlives an application object.

    A fresh app has no prior knowledge of the backend and must not inherit the last
    one's answer - which is also what stops one test's cached answer leaking into the
    next, as it did the first time this was written.
    """
    from mcritweb import create_app

    utility.probe_server(CountingProbe(answer=True), 60, "http://backend")
    assert utility._probe_cache is not None, "the cache is primed"

    instance_path = tmp_path / "instance"
    instance_path.mkdir()
    create_app(
        {"DATABASE": str(tmp_path / "db.sqlite"), "TESTING": True, "SECRET_KEY": "x"},
        instance_path=str(instance_path),
    )

    assert utility._probe_cache is None


if __name__ == "__main__":
    unittest.main()


# --- concurrency -------------------------------------------------------------
#
# The lock is deliberately not held across the probe, so two requests can be probing at
# once and a third can be invalidating in between. These are the three orderings that
# can produce a wrong stored answer, and each one was reachable before the generation
# counter and the start-time comparison were added.

def test_a_probe_in_flight_does_not_undo_an_invalidation():
    """The one that matters operationally.

    An admin corrects a bad token; change_server calls forget_server_probe. A probe
    that went out against the *old* token then lands and, without the generation guard,
    writes its stale `False` straight over the invalidation - so the admin keeps seeing
    "could not authenticate" for up to the full TTL after fixing it. The probe runs on
    36 routes, so one is nearly always in flight when the settings are saved.
    """
    utility.forget_server_probe()
    started = threading.Event()
    may_finish = threading.Event()

    def slow_probe_against_the_old_token():
        started.set()
        may_finish.wait(5)
        return False

    answers = []
    worker = threading.Thread(target=lambda: answers.append(
        utility.probe_server(slow_probe_against_the_old_token, 60, "http://backend")))
    worker.start()
    started.wait(5)

    utility.forget_server_probe()   # the admin saves the corrected token
    may_finish.set()
    worker.join(5)

    assert answers == [False], "the in-flight probe should still return its own answer"
    assert utility._probe_cache is None, "the stale answer was written over the invalidation"


def test_an_older_answer_does_not_overwrite_a_newer_one():
    """A probe that started before an outage returns True; one that started after it
    returns False and finishes first. Completion order says the True is newer. It is
    not - it observed an earlier state, and a false "up" is not cosmetic: the gate
    passes and the view then talks to a dead backend.
    """
    utility.forget_server_probe()
    may_finish = threading.Event()

    def slow_probe_from_before_the_outage():
        may_finish.wait(5)
        return True

    worker = threading.Thread(target=lambda: utility.probe_server(
        slow_probe_from_before_the_outage, 60, "http://backend"))
    worker.start()
    time.sleep(0.05)

    utility.probe_server(lambda: False, 60, "http://backend")   # started later, finishes first
    may_finish.set()
    worker.join(5)

    assert utility._probe_cache.was_up is False, "the earlier probe's answer won"


def test_the_ttl_is_measured_from_when_the_probe_came_back():
    """Taking the timestamp before the call makes every entry probe_duration seconds old
    at birth, so a slow backend - exactly the case a per-request round-trip hurts most -
    gets little or no caching. With a 0.3s TTL and a 0.4s probe the cache never hits."""
    utility.forget_server_probe()
    probe = CountingProbe()

    def slow_probe():
        time.sleep(0.4)
        return probe()

    for _ in range(3):
        utility.probe_server(slow_probe, 0.3, "http://backend")

    assert probe.calls == 1, "the entry was already expired by the time it was written"
