#!/usr/bin/python
"""The backend reachability probe, and how often it actually runs.

`mcrit_server_required` is on 36 routes and made a blocking HTTP round-trip to the
backend on every request to each of them, with the answer thrown away afterwards.
Issue #89. It is now reused for MCRIT_SERVER_PROBE_TTL seconds.

The trade the TTL buys is staleness, in both directions, per worker process - so
these tests pin the edges of it rather than only the happy path.
"""

import logging
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
        url, answered_at, answer = utility._probe_cache
        utility._probe_cache = (url, answered_at - 61, answer)
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
