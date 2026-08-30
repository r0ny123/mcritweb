#!/usr/bin/python
"""What the pages say when a search does not come back.

`McritClient.search_*` answers None when the call to the backend failed. A search
that simply matched nothing is a well-formed result with no rows - a different thing,
reported by the pages themselves since issue #54. The old message, "Ups, search for X
in MCRIT's samples failed!", was the same either way and told the reader nothing
actionable. Issue #79.

The SHA-256 case gets its own answer: someone pasting a hash is asking whether the
sample is known, and `getSampleBySha256` can still say so when the search endpoint
could not.
"""

import logging
import unittest

import pytest

LOG = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)-15s %(message)s")
logging.disable(logging.CRITICAL)

#: 64 hex characters, and deliberately not one the corpus holds
ABSENT_SHA256 = "f" * 64


@pytest.fixture
def fake_mcrit(corpus_mcrit):
    return corpus_mcrit


def _search_fails(monkeypatch, backend):
    for method in ("search_families", "search_samples", "search_functions"):
        monkeypatch.setattr(backend, method, lambda *args, **kwargs: None)


def test_a_failed_family_search_says_the_backend_did_not_answer(client, as_role, fake_mcrit, monkeypatch):
    as_role("visitor")
    _search_fails(monkeypatch, fake_mcrit)

    page = client.get("/explore/families?query=anything", follow_redirects=True).get_data(as_text=True)

    assert "the backend did not answer" in page
    assert "Ups" not in page, "the old wording is gone"


def test_a_failed_search_for_something_that_is_not_a_hash_says_so_plainly(client, as_role, fake_mcrit, monkeypatch):
    as_role("visitor")
    _search_fails(monkeypatch, fake_mcrit)

    page = client.get("/explore/samples?query=notahash", follow_redirects=True).get_data(as_text=True)

    assert "Could not search MCRIT&#39;s samples for &#39;notahash&#39;" in page
    assert "SHA-256" not in page, "no hash was involved"


def test_a_hash_that_is_not_in_the_collection_is_reported_as_absent(client, as_role, fake_mcrit, monkeypatch):
    """The answer issue #79 actually asks for."""
    as_role("visitor")
    _search_fails(monkeypatch, fake_mcrit)

    page = client.get(f"/explore/samples?query={ABSENT_SHA256}", follow_redirects=True).get_data(as_text=True)

    assert f"No sample with SHA-256 {ABSENT_SHA256} is in the collection." in page
    assert "did not answer" not in page, "this is an answer, not a failure"


def test_a_hash_that_is_in_the_collection_is_not_reported_as_absent(client, as_role, fake_mcrit, monkeypatch):
    """The lookup has to be able to say "yes" too, or it is just a nicer way to be
    wrong - and being told a sample is missing when it is there is the worse error."""
    as_role("visitor")
    known = next(iter(fake_mcrit._samples.values()))
    _search_fails(monkeypatch, fake_mcrit)

    page = client.get(f"/explore/samples?query={known.sha256}", follow_redirects=True).get_data(as_text=True)

    assert "is not in the collection" not in page
    assert f"does exist, as sample {known.sample_id}" in page


def test_the_page_survives_the_lookup_failing_as_well(client, as_role, fake_mcrit, monkeypatch):
    """The second opinion is best-effort. A backend that is down will fail both calls,
    and that must be a message rather than a 500."""
    as_role("visitor")
    _search_fails(monkeypatch, fake_mcrit)

    def unreachable(*args, **kwargs):
        raise ConnectionError("backend is down")

    monkeypatch.setattr(fake_mcrit, "getSampleBySha256", unreachable)

    response = client.get(f"/explore/samples?query={ABSENT_SHA256}", follow_redirects=True)

    assert response.status_code == 200
    assert "the backend did not answer" in response.get_data(as_text=True)


def test_the_combined_search_page_reports_a_failure_the_same_way(client, as_role, fake_mcrit, monkeypatch):
    """`explore.search` has its own copy of each of these branches."""
    as_role("visitor")
    _search_fails(monkeypatch, fake_mcrit)

    page = client.get(f"/explore/search?query={ABSENT_SHA256}", follow_redirects=True).get_data(as_text=True)

    assert f"No sample with SHA-256 {ABSENT_SHA256} is in the collection." in page
    assert "Ups" not in page


if __name__ == "__main__":
    unittest.main()
