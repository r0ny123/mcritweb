#!/usr/bin/python
"""A job method should be called the same thing everywhere it is named.

The queue identifies a job by its RPC entry point (`getMatchesForSample`). Four
different answers to "what is this job called" were reaching the user:

  * the job list wrote a human label, e.g. "Match 1vN"
  * the job overview printed `job_info.parameters`, e.g. `getMatchesForSample(0, 2)`
  * two result pages printed `job_info.method`, e.g. `getMatchesForSample`
  * four result pages printed `matching_result.method`, and `linkhunt.html` plus
    `result_maintenance.html` printed `job_info.job_parameters` - neither attribute
    exists, so six headings rendered as nothing at all

`test_no_template_reads_an_attribute_that_does_not_exist` is the ratchet for that last
class of bug, and it is the one that found the sixth site: five had been fixed by hand
and `linkhunt.html` was still reading `job_parameters`. A Jinja Undefined prints as the
empty string, so nothing else in the suite - or in a browser - says a word about it.

See issue #39.
"""

import collections
import logging
import pathlib
import re
import unittest

import pytest
from fixtureData import job_id_of
from mcrit.queue.LocalQueue import Job
from mcrit.storage.MatchingResult import MatchingResult

from mcritweb.jobnames import JOB_METHOD_NAMES, job_method_name

LOG = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)-15s %(message)s")
logging.disable(logging.CRITICAL)

TEMPLATE_ROOT = pathlib.Path(__file__).parent.parent / "mcritweb" / "templates"

# raised by the admin maintenance routes; not part of the queue's own method_types
MAINTENANCE_METHODS = ["rebuildIndex", "recalculatePicHashes", "recalculateMinHashes"]


@pytest.fixture
def fake_mcrit(corpus_mcrit):
    return corpus_mcrit


# --- the lookup itself ---------------------------------------------------------------


def test_every_job_method_the_backend_can_produce_has_a_name():
    """A ratchet. When mcrit grows a job type, this fails and someone picks a label,
    rather than the new type quietly showing up as a raw RPC name in the interface."""
    every_method = Job({"payload": {}}, None).method_types["all"] + MAINTENANCE_METHODS
    unnamed = [method for method in every_method if method not in JOB_METHOD_NAMES]
    assert unnamed == [], f"no display name for {unnamed}"


def test_an_unknown_method_is_shown_as_itself():
    """More use than a placeholder: a backend newer than this table is still readable."""
    assert job_method_name("getSomethingInvented") == "getSomethingInvented"


def test_a_job_with_no_method_still_has_something_to_show():
    assert job_method_name(None) == "Unknown job"
    assert job_method_name("") == "Unknown job"


# --- the templates -------------------------------------------------------------------


def _attributes_used(variable):
    used = collections.defaultdict(list)
    pattern = re.compile(rf"\b{variable}\.([A-Za-z_][A-Za-z0-9_]*)")
    for path in TEMPLATE_ROOT.rglob("*.html"):
        for match in pattern.finditer(path.read_text()):
            used[match.group(1)].append(path.name)
    return used


def _attributes_of(cls):
    return set(getattr(cls, "__annotations__", {})) | {n for n in dir(cls) if not n.startswith("__")}


@pytest.mark.parametrize(
    "variable,cls",
    [("matching_result", MatchingResult), ("job_info", Job), ("job", Job)],
)
def test_no_template_reads_an_attribute_that_does_not_exist(variable, cls):
    """Jinja renders a missing attribute as the empty string, so this kind of typo is
    invisible in a browser and in every render test that only checks a status code."""
    known = _attributes_of(cls)
    missing = {name: files for name, files in _attributes_used(variable).items() if name not in known}
    assert missing == {}, f"{variable}.<attr> not on {cls.__name__}: {missing}"


# --- the pages agree with each other --------------------------------------------------


def _heading(response):
    match = re.search(rb"<h1>([^<]*)</h1>", response.data)
    return match.group(1).decode().strip() if match else None


@pytest.mark.parametrize(
    "report,expected",
    [
        ("matches_for_sample", "Match 1vN"),
        ("matches_for_sample_vs", "Match 1v1"),
        ("matches_for_query", "Match Binary (mapped)"),
        ("cross_compare", "CrossCompare"),
    ],
)
def test_the_result_page_names_the_job(client, as_role, report, expected):
    as_role("visitor")
    response = client.get(f"/data/result/{job_id_of(report)}")
    assert response.status_code == 200
    assert _heading(response) == f"Results for Job: {expected}"


@pytest.mark.parametrize("report", ["matches_for_sample", "matches_for_sample_vs", "matches_for_query"])
def test_the_job_page_and_the_result_page_agree(client, as_role, report):
    as_role("visitor")
    job_id = job_id_of(report)
    on_the_job_page = _heading(client.get(f"/data/jobs/{job_id}"))
    on_the_result_page = _heading(client.get(f"/data/result/{job_id}"))

    assert on_the_job_page.startswith("Job overview: ")
    assert on_the_result_page.startswith("Results for Job: ")
    assert on_the_job_page.removeprefix("Job overview: ") == on_the_result_page.removeprefix("Results for Job: ")


@pytest.mark.parametrize(
    "report,expected",
    [("matches_for_sample", b"Match 1vN"), ("matches_for_sample_vs", b"Match 1v1")],
)
def test_the_job_list_calls_it_the_same_thing(client, as_role, report, expected):
    """The list is where these names came from, so this is really a check that the
    extraction did not change its wording."""
    as_role("visitor")
    response = client.get("/data/jobs")
    assert response.status_code == 200
    assert expected in response.data


def test_the_full_task_string_is_still_on_the_page(client, as_role):
    """The heading is a name now, not a call signature - but the arguments are useful
    and must not have been thrown away. job_column_table still shows them."""
    as_role("visitor")
    response = client.get(f"/data/jobs/{job_id_of('matches_for_sample')}")
    assert b"getMatchesForSample(0, 2)" in response.data


if __name__ == "__main__":
    unittest.main()
