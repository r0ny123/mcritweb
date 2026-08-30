#!/usr/bin/python
"""What a table says when it has no rows. Issue #65.

Every table used to hard-code one sentence per type, so a sample with no functions
was told to "upload your first sample" and the cross-compare tab of a job list full
of other jobs was told to create "your first job". The message is now the caller's to
choose, with the old text as the fallback.
"""

import logging
import unittest

import pytest

LOG = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)-15s %(message)s")
logging.disable(logging.CRITICAL)

GENERIC_SAMPLE_PROMPT = "Click here to upload your first sample"
GENERIC_JOB_PROMPT = "Click here to create your first job"


@pytest.fixture
def fake_mcrit(corpus_mcrit):
    return corpus_mcrit


class EmptyBackend:
    """A reachable backend that holds nothing, so every table renders its empty state."""

    def __init__(self, corpus):
        self._corpus = corpus

    def __getattr__(self, name):
        return getattr(self._corpus, name)

    @staticmethod
    def _empty_search():
        return {"search_results": {}, "cursor": {"forward": None, "backward": None},
                "id_match": None, "sha_match": None}

    def search_samples(self, *args, **kwargs):
        return self._empty_search()

    def search_families(self, *args, **kwargs):
        return self._empty_search()

    def search_functions(self, *args, **kwargs):
        return self._empty_search()

    def getFunctionsBySampleId(self, *args, **kwargs):
        return []

    def getQueueData(self, *args, **kwargs):
        return []


@pytest.fixture
def empty_mcrit(corpus_mcrit):
    return EmptyBackend(corpus_mcrit)


# --- the collection listings keep the first-run prompt ---------------------------

def test_an_empty_collection_still_invites_a_first_upload(client, as_role, app, empty_mcrit):
    """The generic message is right exactly once, and this is when."""
    app.config["MCRIT_CLIENT_FACTORY"] = lambda **kwargs: empty_mcrit
    as_role("visitor")

    page = client.get("/explore/samples").get_data(as_text=True)

    assert GENERIC_SAMPLE_PROMPT in page


def test_a_search_that_matched_nothing_does_not_blame_an_empty_collection(client, as_role, app, empty_mcrit):
    app.config["MCRIT_CLIENT_FACTORY"] = lambda **kwargs: empty_mcrit
    as_role("visitor")

    page = client.get("/explore/samples?query=nothinghere").get_data(as_text=True)

    # Jinja escapes the quotes it renders; the browser shows them as quotes
    assert "No samples match &#34;nothinghere&#34;." in page
    assert GENERIC_SAMPLE_PROMPT not in page


@pytest.mark.parametrize("path,noun", [
    ("/explore/families", "families"),
    ("/explore/functions", "functions"),
])
def test_the_other_listings_do_the_same(client, as_role, app, empty_mcrit, path, noun):
    app.config["MCRIT_CLIENT_FACTORY"] = lambda **kwargs: empty_mcrit
    as_role("visitor")

    page = client.get(f"{path}?query=nothinghere").get_data(as_text=True)

    assert f"No {noun} match &#34;nothinghere&#34;." in page


# --- the detail pages ------------------------------------------------------------

def test_a_sample_with_no_functions_does_not_ask_you_to_upload_one(client, as_role, app, empty_mcrit, corpus_mcrit):
    """The sample is right there. Telling its page to upload a first sample is absurd."""
    app.config["MCRIT_CLIENT_FACTORY"] = lambda **kwargs: empty_mcrit
    as_role("visitor")
    sample = next(iter(corpus_mcrit._samples.values()))

    page = client.get(f"/explore/samples/{sample.sample_id}").get_data(as_text=True)

    assert "This sample has no functions on record." in page
    assert GENERIC_SAMPLE_PROMPT not in page


def test_a_family_with_no_samples_says_so(client, as_role, app, empty_mcrit, corpus_mcrit):
    app.config["MCRIT_CLIENT_FACTORY"] = lambda **kwargs: empty_mcrit
    as_role("visitor")
    family = next(iter(corpus_mcrit._families.values()))

    page = client.get(f"/explore/families/{family.family_id}").get_data(as_text=True)

    assert "This family has no samples." in page
    assert GENERIC_SAMPLE_PROMPT not in page


# --- the job list, which is what the issue names ---------------------------------

@pytest.mark.parametrize("category,expected", [
    ("combineMatchesToCross", "No cross compare jobs yet."),
    ("getMatchesForSampleVs", "No 1 vs 1 matching jobs yet."),
    ("getMatchesForSample", "No 1 vs N matching jobs yet."),
    ("getUniqueBlocks", "No unique blocks jobs yet."),
])
def test_each_job_category_says_what_it_is_missing(client, as_role, app, empty_mcrit, category, expected):
    app.config["MCRIT_CLIENT_FACTORY"] = lambda **kwargs: empty_mcrit
    as_role("visitor")

    page = client.get(f"/data/jobs?active={category}").get_data(as_text=True)

    assert expected in page
    assert GENERIC_JOB_PROMPT not in page


def test_a_state_filter_reports_the_state(client, as_role, app, empty_mcrit):
    """Filtering to "failed" and seeing none is not an empty queue."""
    app.config["MCRIT_CLIENT_FACTORY"] = lambda **kwargs: empty_mcrit
    as_role("visitor")

    page = client.get("/data/jobs?state=failed").get_data(as_text=True)

    assert "No jobs are in state &#34;failed&#34;." in page


def test_a_category_with_nowhere_to_start_one_offers_no_link(client, as_role, app, empty_mcrit):
    """A dead link is worse than no link. Unique blocks are started from a row, so
    there is no page to send anyone to."""
    app.config["MCRIT_CLIENT_FACTORY"] = lambda **kwargs: empty_mcrit
    as_role("visitor")

    page = client.get("/data/jobs?active=getUniqueBlocks").get_data(as_text=True)

    assert "They are started from a family or sample row." in page


def test_the_message_is_escaped(client, as_role, app, empty_mcrit):
    """The search term reaches the empty state, and a search term is whatever
    somebody typed."""
    app.config["MCRIT_CLIENT_FACTORY"] = lambda **kwargs: empty_mcrit
    as_role("visitor")

    page = client.get("/explore/samples?query=%3Cimg+src%3Dx+onerror%3Dalert(1)%3E").get_data(as_text=True)

    assert "<img src=x onerror=alert(1)>" not in page
    assert "&lt;img src=x onerror=alert(1)&gt;" in page


if __name__ == "__main__":
    unittest.main()


# --- tables that sit under a search box --------------------------------------
#
# These three were missed on the first pass, and they are the worst offenders: each has
# a search field immediately above it, so "No samples available. Click here to upload
# your first sample" is shown to someone whose *search* missed on a full collection. The
# message is not merely unhelpful there, it is false.

@pytest.mark.parametrize(
    "path,query_param",
    [
        ("/analyze/compare", "query"),
        ("/analyze/compare_versus", "query_a"),
        ("/analyze/compare_versus", "query_b"),
    ],
)
def test_a_selection_page_search_that_missed_does_not_blame_an_empty_collection(client, as_role, path, query_param):
    as_role("visitor")

    page = client.get(f"{path}?{query_param}=zzznothingmatchesthis").get_data(as_text=True)

    assert "upload your first sample" not in page
    assert "No sample matches &#34;zzznothingmatchesthis&#34;." in page


@pytest.mark.parametrize("path", ["/analyze/compare", "/analyze/compare_versus"])
def test_the_same_page_without_a_search_still_offers_the_upload(client, as_role, path, monkeypatch, fake_mcrit):
    """The old message is right when the collection really is empty - the point is to
    stop saying it when it is not."""
    as_role("visitor")
    # a plain dict, not hasattr(fake_mcrit, ...): the strict fake's catch-all
    # __getattr__ raises rather than answering False
    monkeypatch.setattr(fake_mcrit, "search_samples", lambda *args, **kwargs: {
        "search_results": {}, "cursor": {"forward": None, "backward": None},
        "id_match": None, "sha_match": None,
    })

    page = client.get(path).get_data(as_text=True)

    assert "upload your first sample" in page


def test_paging_past_the_end_of_a_search_says_so(client, as_role, fake_mcrit, monkeypatch):
    """A search section renders whenever the request carried a cursor, whether or not
    the slice behind it has rows - so the "next" link on the last page lands on empty
    tables under live headings."""
    as_role("visitor")
    monkeypatch.setattr(fake_mcrit, "search_samples", lambda *args, **kwargs: {
        "search_results": {}, "cursor": {"current": "c", "forward": None, "backward": "b"},
        "id_match": None, "sha_match": None,
    })

    page = client.get("/explore/search?query=citadel&type=sample&sample_cursor=c").get_data(as_text=True)

    assert "upload your first sample" not in page
    assert "No more samples match &#34;citadel&#34; on this page." in page


# --- an invitation a reader cannot accept is worse than no invitation ----------------
#
# `data.submit` is contributor-only; the navbar has always hidden "Submit binary" from a
# visitor for that reason. An empty table telling a visitor to "click here to upload
# your first sample" and then answering 403 is a worse experience than one that simply
# says the table is empty - so the message stays and the link goes.

SUBMIT_LINK = 'href="/data/submit"'


def test_a_visitor_is_invited_but_not_linked_to_a_page_they_cannot_open(client, as_role, app, empty_mcrit):
    app.config["MCRIT_CLIENT_FACTORY"] = lambda **kwargs: empty_mcrit
    as_role("visitor")

    page = client.get("/explore/samples").get_data(as_text=True)

    assert GENERIC_SAMPLE_PROMPT in page, "the message itself is still worth saying"
    assert SUBMIT_LINK not in page, "offered a visitor a link that answers 403"


@pytest.mark.parametrize("role", ["contributor", "admin"])
def test_someone_who_can_submit_still_gets_the_link(client, as_role, app, empty_mcrit, role):
    app.config["MCRIT_CLIENT_FACTORY"] = lambda **kwargs: empty_mcrit
    as_role(role)

    page = client.get("/explore/samples").get_data(as_text=True)

    assert SUBMIT_LINK in page


def test_the_link_a_visitor_is_denied_really_would_have_been_denied(client, as_role):
    """Pins the premise rather than trusting it: if `data.submit` ever opened up to
    visitors, the gate above becomes wrong and this test says so."""
    as_role("visitor")

    assert client.get("/data/submit").status_code == 403


@pytest.mark.parametrize("path", ["/explore/families", "/explore/functions", "/analyze/compare"])
def test_every_other_empty_state_hides_it_too(client, as_role, app, empty_mcrit, path):
    """The gate is in `_empty_state`, not at the call sites, so this holds for all of
    them - including the ones that were already there before issue #65."""
    app.config["MCRIT_CLIENT_FACTORY"] = lambda **kwargs: empty_mcrit
    as_role("visitor")

    assert SUBMIT_LINK not in client.get(path).get_data(as_text=True)
