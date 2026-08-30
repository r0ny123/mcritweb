#!/usr/bin/python
"""The two pages that report on the backend itself, and the fake's fidelity to it.

`/explore/statistics` rendered an *empty table* under this suite while working in
production, because `CorpusMcritClient.getStatus` unwrapped `{"status": {...}}` once
more than the real client does. A page that renders nothing still answers 200, so
every existing test of it passed and the page was effectively untested.

Fixing that fidelity gap surfaced a second, real defect: `getVersion` answers with a
dict too, and the admin server page rendered it verbatim as `{'version': '1.4.3'}`.
The fake had been hiding it by handing back a bare string no real backend sends.

The shapes are not guesswork - they are read off mcrit's own source:
`MinHashIndex.getStatus` builds `{"status": {...}}` and `getVersion` builds
`{"version": ...}`; `StatusResource` puts each under `"data"`; `handle_response`
returns `"data"` untouched.
"""

import logging
import re
import unittest

import pytest
from fixtureData import load

LOG = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)-15s %(message)s")
logging.disable(logging.CRITICAL)


@pytest.fixture
def fake_mcrit(corpus_mcrit):
    return corpus_mcrit


def cell_after(page, label):
    """The cell a two-column row puts next to `label`.

    Tolerant about the closing tag of the label cell: statistics.html writes its key
    in a `<th>` and closes it with `</td>`, which browsers accept and which is not
    this change's to fix.
    """
    match = re.search(re.escape(label) + r"\s*</t[dh]>\s*<td[^>]*>([^<]*)</td>", " ".join(page.split()))
    return match.group(1).strip() if match else None


# --- the fake answers in the shape the real client answers in ---------------------

def test_the_fake_reports_status_in_the_shape_the_real_client_returns(corpus_mcrit):
    """mcrit's MinHashIndex.getStatus returns {"status": {...}}, StatusResource puts
    that under "data", and handle_response returns "data" - so the client's caller
    sees the wrapper. A fake that unwraps it is a fake of a backend that does not
    exist, and every test written against it tests the wrong contract."""
    status = corpus_mcrit.getStatus()

    assert set(status) == {"status"}, "the wrapper is part of what the client returns"
    assert status["status"]["num_samples"] == 13


def test_the_fake_reports_version_in_the_shape_the_real_client_returns(corpus_mcrit):
    """Same for getVersion: MinHashIndex.getVersion returns {"version": ...}."""
    version = corpus_mcrit.getVersion()

    assert version == {"version": load("version")["version"]}
    assert not isinstance(version, str), "a bare string is not what any backend sends"


# --- the statistics page actually renders the statistics --------------------------

def test_the_statistics_page_renders_the_numbers_it_was_given(client, as_role):
    """This is the test that could not have passed before: the page rendered an empty
    table, and its 200 said nothing."""
    as_role("visitor")
    expected = load("status")["status"]

    page = client.get("/explore/statistics").get_data(as_text=True)

    # one value cell per statistic; the key goes in a <th>
    assert page.count("<td") >= len(expected), "the statistics table came out empty"
    for key, value in expected.items():
        assert cell_after(page, key) == str(value), f"{key} is not on the page"


# --- the admin page shows a version, not a dict -----------------------------------

def test_the_admin_page_shows_the_backend_version_as_a_version(client, as_role):
    """`{'version': '1.4.3'}` is what this rendered once the fake stopped lying about
    the shape. The row is meant to show a version number."""
    as_role("admin")

    page = client.get("/admin/server").get_data(as_text=True)

    shown = cell_after(page, "Running MCRIT Backend Version:")
    assert shown == load("version")["version"]
    assert "{" not in shown and "version'" not in shown


@pytest.mark.parametrize(
    "answer, expected",
    [
        ({"version": "1.4.3"}, "1.4.3"),
        # handle_response maps an unreachable or refusing backend to None
        (None, "unknown"),
        ({}, "unknown"),
        ({"version": None}, "unknown"),
        ({"version": ""}, "unknown"),
        # a future backend that answers with a bare string is still readable
        ("1.5.0", "1.5.0"),
    ],
    ids=["a dict", "None", "an empty dict", "a null version", "an empty version", "a bare string"],
)
def test_a_version_that_cannot_be_read_says_so_rather_than_rendering_a_shape(app, answer, expected):
    """The row must never show a Python repr. `None` is the case that matters: it is
    what the client answers for a backend that could not be reached."""
    from mcritweb.views.administration import backend_version

    class Answering:
        def getVersion(self):
            return answer

    with app.app_context():
        assert backend_version(Answering()) == expected


if __name__ == "__main__":
    unittest.main()
