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
import inspect
import json
import logging
import pathlib
import re
import unittest

import pytest
from fixtureData import job_id_of
from mcrit.queue.LocalQueue import Job
from mcrit.storage.MatchingResult import MatchingResult
from mcrit.Worker import Worker

from mcritweb.jobnames import JOB_METHOD_NAMES, job_method_name

LOG = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)-15s %(message)s")
logging.disable(logging.CRITICAL)

TEMPLATE_ROOT = pathlib.Path(__file__).parent.parent / "mcritweb" / "templates"

def every_queued_method():
    """Every method the backend can put a job in the queue for.

    Taken from the `@Remote` decorator, which sets `remote = True` on the function it
    wraps, rather than from `Job.method_types["all"]`. That list is hand-maintained in
    mcrit and is **incomplete**: it omits `getMatchesForSampleVsGroup` (queued by
    `MinHashIndex.getMatchesCross` when `sample_group_only` is set), `doDbCleanup`, and
    the two `recalculate*` methods the admin maintenance page submits. A ratchet built
    on it therefore ratchets against the wrong list and passes while jobs go unnamed -
    which is how `getMatchesForSampleVsGroup` was missing from the table below.
    """
    return sorted(
        name for name, function in inspect.getmembers(Worker, predicate=inspect.isfunction)
        if getattr(function, "remote", False)
    )


@pytest.fixture
def fake_mcrit(corpus_mcrit):
    return corpus_mcrit


# --- the lookup itself ---------------------------------------------------------------


def test_every_job_method_the_backend_can_produce_has_a_name():
    """A ratchet. When mcrit grows a job type, this fails and someone picks a label,
    rather than the new type quietly showing up as a raw RPC name in the interface."""
    unnamed = [method for method in every_queued_method() if method not in JOB_METHOD_NAMES]
    assert unnamed == [], f"no display name for {unnamed}"


def test_every_method_in_the_captured_queue_has_a_name():
    """A second ratchet, grounded in real captured data rather than in a declaration.

    The queue fixture holds five `getMatchesForSampleVsGroup` jobs - the children of the
    captured cross compare - so this method is not hypothetical: mcritweb submits cross
    compares that produce it, and its headings were rendering as the raw RPC name. The
    check above should have caught that and did not, because it ratcheted against a list
    mcrit maintains by hand. This one cannot drift from reality the same way: it reads
    what the backend actually put in the queue.
    """
    queue = json.loads((pathlib.Path(__file__).parent / "fixtures" / "queue.json").read_text())
    documents = queue if isinstance(queue, list) else queue.get("data", [])
    methods = {document.get("payload", {}).get("method") for document in documents}
    methods.discard(None)

    assert methods, "the queue fixture holds no jobs, so this proves nothing"
    assert [method for method in sorted(methods) if method not in JOB_METHOD_NAMES] == []


def test_the_ratchet_is_wider_than_the_queue_own_list():
    """Guards the guard. If mcrit ever fills `method_types["all"]` in, this test starts
    failing and can simply go - but until then, an assertion that the two agree would be
    the assertion that let the gap through."""
    queue_own_list = Job({"payload": {}}, None).method_types["all"]
    missing_from_the_queue_list = [m for m in every_queued_method() if m not in queue_own_list]

    assert "getMatchesForSampleVsGroup" in missing_from_the_queue_list
    assert set(missing_from_the_queue_list) < set(every_queued_method())


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
    "category,expected",
    [("getMatchesForSample", b"Match 1vN"), ("getMatchesForSampleVs", b"Match 1v1")],
)
def test_the_job_list_calls_it_the_same_thing(client, as_role, category, expected):
    """The list is where these names came from, so this is really a check that the
    extraction did not change its wording.

    The category is named in the URL because issue #36 made the jobs page one tab at a
    time: a bare /data/jobs redirects to whichever category the queue happens to report
    first, so asking for "the list" without saying which list only ever exercised one
    of these two.
    """
    as_role("visitor")
    response = client.get(f"/data/jobs?active={category}", follow_redirects=True)
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
