#!/usr/bin/python
"""Long job descriptions have somewhere to break. Issue #41.

The description column of the jobs table can hold a token with no spaces in it - the
filename of an upload, a SHA-256, or the raw `job.parameters` string that
`job_description` falls back to for a method it does not recognise. Without an
`overflow-wrap`, that token cannot be broken, so it widens the column and pushes the
whole table past the edge of the viewport.

CSS is not renderable here, so these pin the two things that rot: the cell carrying
the class the rule targets, and the rule being there and staying scoped.
"""

import logging
import pathlib
import re
import unittest

import pytest
from fixtureData import job_id_of

LOG = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)-15s %(message)s")
logging.disable(logging.CRITICAL)

STYLESHEET = pathlib.Path(__file__).resolve().parents[1] / "mcritweb" / "static" / "style.css"
JOB_ROW = pathlib.Path(__file__).resolve().parents[1] / "mcritweb" / "templates" / "table" / "job_row.html"


@pytest.fixture
def fake_mcrit(corpus_mcrit):
    return corpus_mcrit


def test_every_description_cell_can_break_a_long_token():
    """job_row renders the description in two places - the per-method table and the
    "all jobs" one - and both need the class."""
    markup = JOB_ROW.read_text()

    rendering_cells = [line for line in markup.splitlines() if "job_description(job," in line and "<td" in line]
    assert len(rendering_cells) == 2, "job_row renders the description twice"
    for cell in rendering_cells:
        assert "job-description" in cell


def test_the_stylesheet_lets_that_cell_break():
    css = STYLESHEET.read_text()

    rule = re.search(r"table\.table td\.job-description\s*\{([^}]*)\}", css)
    assert rule is not None, "no rule for the description cell"
    assert "overflow-wrap" in rule.group(1)
    assert "anywhere" in rule.group(1), "break-word will not break a token alone on its line"


def test_the_class_reaches_a_rendered_jobs_page(client, as_role):
    as_role("visitor")

    page = client.get("/data/jobs").get_data(as_text=True)

    assert "job-description" in page
    assert "job-cell job-description" in page, "the click handler's class is still there"


def test_an_unrecognised_job_method_still_renders_its_raw_parameters(client, as_role, fake_mcrit, monkeypatch):
    """The fallback branch is where the longest strings come from, so it is the one
    the wrapping is for. It must also still be reachable."""
    import copy

    from mcrit.queue.LocalQueue import Job

    as_role("visitor")
    job_data = copy.deepcopy(fake_mcrit.getJobData(job_id_of("matches_for_sample"))._data)
    job_data["payload"]["method"] = "someFutureMethodWithAVeryLongNameIndeed"
    monkeypatch.setattr(fake_mcrit, "getQueueData", lambda *args, **kwargs: [Job(job_data, None)])

    page = client.get("/data/jobs").get_data(as_text=True)

    assert "someFutureMethodWithAVeryLongNameIndeed" in page
    assert "job-description" in page


if __name__ == "__main__":
    unittest.main()
