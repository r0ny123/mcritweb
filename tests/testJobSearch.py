#!/usr/bin/python
"""Searching the job list.

The jobs page had a search box that was commented out in the template, and a view
that read `request.form['Search']` into a variable it never used - so the feature
looked half-present and did nothing. Issue #51.

`McritClient.getQueueData` takes a `filter` string, which the backend applies as a
substring test against each job's parameters. Passing the term through is what makes
the box work.
"""

import logging
import unittest

import pytest

LOG = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)-15s %(message)s")
logging.disable(logging.CRITICAL)


@pytest.fixture
def fake_mcrit(corpus_mcrit):
    return corpus_mcrit


def queue_filters(backend):
    """The `filter` argument of every getQueueData call the request made."""
    return [kwargs.get("filter") for name, args, kwargs in backend.calls if name == "getQueueData"]


def test_the_jobs_page_offers_a_search_box(client, as_role):
    as_role("visitor")
    page = client.get("/data/jobs").get_data(as_text=True)

    assert 'name="Search"' in page
    assert 'placeholder="Search jobs"' in page


def test_a_search_term_reaches_the_backend_as_a_filter(client, as_role, fake_mcrit):
    """The whole bug: the term used to stop at the view."""
    as_role("visitor")

    client.get("/data/jobs?Search=getMatchesForSample")

    assert "getMatchesForSample" in queue_filters(fake_mcrit)


def test_no_search_term_means_no_filter(client, as_role, fake_mcrit):
    """An empty box must not narrow anything - `filter=""` would be a substring test
    that happens to match everything today, but saying None is what we mean."""
    as_role("visitor")

    client.get("/data/jobs")

    assert queue_filters(fake_mcrit) == [None]


def test_whitespace_only_is_treated_as_no_search(client, as_role, fake_mcrit):
    as_role("visitor")

    client.get("/data/jobs?Search=%20%20")

    assert queue_filters(fake_mcrit) == [None]


def test_the_page_says_what_it_searched_for(client, as_role):
    as_role("visitor")
    page = client.get("/data/jobs?Search=combineMatchesToCross").get_data(as_text=True)

    assert 'Results for "combineMatchesToCross"' in page


def test_the_search_term_is_escaped(client, as_role):
    """It is echoed into both a value= attribute and the page body, and it is whatever
    somebody typed."""
    as_role("visitor")

    page = client.get("/data/jobs?Search=%22%3E%3Cimg+src%3Dx+onerror%3Dalert(1)%3E").get_data(as_text=True)

    assert '"><img src=x onerror=alert(1)>' not in page
    assert "&lt;img src=x onerror=alert(1)&gt;" in page


def test_searching_keeps_the_category_you_were_looking_at(client, as_role):
    """Otherwise typing in the box silently throws away the tab you had open."""
    as_role("visitor")

    page = client.get("/data/jobs?active=getMatchesForSample").get_data(as_text=True)

    assert '<input type="hidden" name="active" value="getMatchesForSample">' in page


def test_searching_keeps_the_sort_order_you_had(client, as_role):
    """Same reasoning as the category above - searching should narrow the list, not
    quietly reset how it is arranged."""
    as_role("visitor")

    page = client.get("/data/jobs?ascending=true").get_data(as_text=True)

    assert '<input type="hidden" name="ascending" value="true">' in page


def test_the_jobs_page_no_longer_accepts_a_post(client, as_role):
    """A search is a read. The POST branch it used to have raised BadRequestKeyError
    on `request.form['Search']` for any POST that did not carry the field."""
    as_role("visitor")

    assert client.post("/data/jobs", data={"Search": "anything"}).status_code == 405


if __name__ == "__main__":
    unittest.main()
